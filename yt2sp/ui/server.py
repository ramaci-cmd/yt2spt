"""Local Web UI Server untuk yt2sp (Zero Dependencies – Menggunakan Python Standard Library)."""
from __future__ import annotations

import gzip
import hashlib
import json
import logging
import mimetypes
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from yt2sp.config import load_config
from yt2sp.match.normalize import normalize_title
from yt2sp.store import db

logger = logging.getLogger(__name__)

# Task State untuk background jobs
_job_lock = threading.Lock()
_job_cancel_event = threading.Event()
_job_state: dict[str, Any] = {
    "running": False,
    "type": None,
    "current": 0,
    "total": 0,
    "message": "Siap",
    "error": None,
}

# In-Memory Server-Side API Cache (TTL Caching)
_api_cache_store: dict[str, tuple[float, Any]] = {}
_api_cache_lock = threading.Lock()


def _get_cached_api(key: str, ttl_seconds: float = 2.0) -> Any | None:
    now = time.monotonic()
    with _api_cache_lock:
        if key in _api_cache_store:
            ts, val = _api_cache_store[key]
            if now - ts < ttl_seconds:
                return val
            del _api_cache_store[key]
    return None


def _set_cached_api(key: str, val: Any) -> None:
    with _api_cache_lock:
        _api_cache_store[key] = (time.monotonic(), val)


def _invalidate_api_cache() -> None:
    with _api_cache_lock:
        _api_cache_store.clear()


def _clean_preview_query(text: str) -> str:
    cleaned = re.sub(r'【[^】]*】', ' ', text)
    cleaned = re.sub(r'\[[^\]]*\]', ' ', cleaned)
    cleaned = re.sub(r'\([^\)]*\)', ' ', cleaned)
    cleaned = re.sub(r'\|\s*.*$', ' ', cleaned)
    cleaned = re.sub(r'\b(cover|歌ってみた|mv|original song|official video|official music video|official audio|lyric video|lirik)\b', ' ', cleaned, flags=re.I)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def _fetch_preview_deezer(query_str: str) -> tuple[str, str, str] | None:
    try:
        url = f"https://api.deezer.com/search?q={urllib.parse.quote(query_str)}&limit=5"
        req = urllib.request.Request(url, headers={"User-Agent": "yt2sp/1.0"})
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for item in data.get("data", []):
                p = item.get("preview")
                if p:
                    return (p, item.get("title", ""), item.get("artist", {}).get("name", ""))
    except Exception:
        pass
    return None


def _fetch_preview_itunes(query_str: str) -> tuple[str, str, str] | None:
    try:
        url = f"https://itunes.apple.com/search?term={urllib.parse.quote(query_str)}&entity=song&limit=5"
        req = urllib.request.Request(url, headers={"User-Agent": "yt2sp/1.0"})
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for item in data.get("results", []):
                p = item.get("previewUrl")
                if p:
                    return (p, item.get("trackName", ""), item.get("artistName", ""))
    except Exception:
        pass
    return None


def _update_job(running: bool, job_type: str | None = None, current: int = 0, total: int = 0, message: str = "", error: str | None = None) -> None:
    with _job_lock:
        _job_state["running"] = running
        _job_state["type"] = job_type
        _job_state["current"] = current
        _job_state["total"] = total
        _job_state["message"] = message
        _job_state["error"] = error
    _invalidate_api_cache()


def _get_job_state() -> dict:
    with _job_lock:
        return dict(_job_state)


class UIHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        # Kurangi noise log server
        pass

    def _is_safe_origin(self) -> bool:
        """Cek apakah origin berasal dari localhost/127.0.0.1 untuk mencegah serangan CSRF dari web lain."""
        origin = self.headers.get("Origin")
        if not origin:
            return True  # Direct browser request / same-origin
        try:
            parsed = urllib.parse.urlparse(origin)
            return parsed.hostname in ("127.0.0.1", "localhost", "::1")
        except Exception:
            return False

    def _send_json(self, data: Any, status: int = 200, cache_control: str = "no-cache") -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        accept_encoding = self.headers.get("Accept-Encoding", "").lower()
        use_gzip = "gzip" in accept_encoding and len(raw) > 200

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        origin = self.headers.get("Origin")
        if origin and self._is_safe_origin():
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Cache-Control", cache_control)

        if use_gzip:
            compressed = gzip.compress(raw, compresslevel=6)
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(compressed)))
            self.end_headers()
            self.wfile.write(compressed)
        else:
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    def _send_file(self, file_path: Path) -> None:
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, "File Not Found")
            return
        mime_type, _ = mimetypes.guess_type(str(file_path))
        raw = file_path.read_bytes()
        etag = f'"{hashlib.md5(raw).hexdigest()}"'

        # Check Conditional ETag (HTTP 304 Not Modified)
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.end_headers()
            return

        is_static_asset = file_path.suffix in (".js", ".css", ".png", ".jpg", ".svg", ".woff2")
        cache_control = "public, max-age=3600" if is_static_asset else "no-cache"

        accept_encoding = self.headers.get("Accept-Encoding", "").lower()
        use_gzip = "gzip" in accept_encoding and len(raw) > 512 and (
            mime_type and ("text" in mime_type or "javascript" in mime_type or "json" in mime_type)
        )

        self.send_response(200)
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.send_header("ETag", etag)
        self.send_header("Cache-Control", cache_control)

        if use_gzip:
            compressed = gzip.compress(raw, compresslevel=6)
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(compressed)))
            self.end_headers()
            self.wfile.write(compressed)
        else:
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    def do_OPTIONS(self) -> None:
        if not self._is_safe_origin():
            self.send_error(403, "Forbidden Origin")
            return
        origin = self.headers.get("Origin") or "http://127.0.0.1:5000"
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # ── API Endpoints ──
        if path == "/api/version":
            from yt2sp import __version__, __engine__
            self._send_json({
                "version": f"v{__version__}",
                "engine": __engine__,
                "badge": f"v{__version__} • {__engine__}",
            })
            return

        elif path == "/api/status":
            cached = _get_cached_api("status", ttl_seconds=1.0)
            if cached is not None:
                self._send_json(cached)
                return
            db.init_db()
            summary = db.get_status_summary()
            summary["job"] = _get_job_state()
            from yt2sp import __version__, __engine__
            summary["version"] = f"v{__version__}"
            summary["engine"] = __engine__
            summary["version_badge"] = f"v{__version__} • {__engine__}"
            _set_cached_api("status", summary)
            self._send_json(summary)
            return

        elif path == "/api/playlists":
            cached = _get_cached_api("playlists", ttl_seconds=2.0)
            if cached is not None:
                self._send_json(cached)
                return
            db.init_db()
            pls = db.get_all_playlists()
            data = []
            for p in pls:
                genres = db.get_playlist_genres(p["id"])
                p_keys = p.keys()
                unavail = p["unavailable_count"] if "unavailable_count" in p_keys and p["unavailable_count"] else 0
                sample_vids = db.get_playlist_sample_video_ids(p["id"], limit=4)
                sample_thumbs = db.get_playlist_sample_thumbnails(p["id"], limit=4)
                src_p = (p["source_provider"] if "source_provider" in p_keys else "youtube") or "youtube"
                dest_p = (p["destination_provider"] if "destination_provider" in p_keys else "spotify") or "spotify"
                desc = (p["description"] if "description" in p_keys else "") or ""
                thumb = (p["thumbnail_url"] if "thumbnail_url" in p_keys else "") or ""
                data.append({
                    "id": p["id"],
                    "yt_playlist_id": p["yt_playlist_id"],
                    "title": p["title"],
                    "track_count": p["track_count"],
                    "unavailable_count": unavail,
                    "extracted_at": p["extracted_at"],
                    "source_provider": src_p,
                    "destination_provider": dest_p,
                    "description": desc,
                    "thumbnail_url": thumb,
                    "genres": [{"genre": g["genre"], "count": g["track_count"]} for g in genres],
                    "sample_video_ids": sample_vids,
                    "sample_thumbnails": sample_thumbs,
                })
            lib_genres = db.get_all_library_genres()
            total_lib_tracks = len(db.get_all_library_tracks())
            res_data = {
                "playlists": data,
                "library": {
                    "total_tracks": total_lib_tracks,
                    "genres": [{"genre": g["genre"], "count": g["track_count"]} for g in lib_genres]
                }
            }
            _set_cached_api("playlists", res_data)
            self._send_json(res_data)
            return

        elif path == "/api/tracks":
            playlist_id_str = query.get("playlist_id", ["all"])[0]
            genre = query.get("genre", [""])[0]
            status_filter = query.get("status", [""])[0]
            q_search = query.get("q", [""])[0].strip().lower()

            cache_key = f"tracks_{playlist_id_str}_{genre}_{status_filter}_{q_search}"
            cached = _get_cached_api(cache_key, ttl_seconds=2.0)
            if cached is not None:
                self._send_json(cached)
                return

            db.init_db()
            if playlist_id_str in ("all", "", "0", None):
                raw_tracks = db.get_all_library_tracks()
            else:
                try:
                    pl_id = int(playlist_id_str)
                    raw_tracks = db.get_playlist_tracks(pl_id)
                except ValueError:
                    raw_tracks = db.get_all_library_tracks()

            tracks = []
            for t in raw_tracks:
                t_status = t["status"] or "pending"
                t_genre = t["genre"] or "Uncategorized"

                if status_filter and t_status != status_filter:
                    continue
                if genre and t_genre.strip().lower() != genre.strip().lower():
                    continue

                artists = json.loads(t["artists"]) if t["artists"] else []
                t_title = t["title"] or ""
                t_album = t["album"] or ""
                in_playlists = t["in_playlists"] if "in_playlists" in t.keys() and t["in_playlists"] else ""

                if q_search:
                    joined_artists = " ".join(artists).lower()
                    if (q_search not in t_title.lower() and
                        q_search not in joined_artists and
                        q_search not in t_album.lower() and
                        q_search not in t_genre.lower()):
                        continue

                import unidecode
                t_ascii = unidecode.unidecode(t_title) if t_title else ""
                r_title = t["result_title"] if "result_title" in t.keys() and t["result_title"] else ""
                r_ascii = unidecode.unidecode(r_title) if r_title else ""

                dest_id_val = (t["dest_id"] if "dest_id" in t.keys() else None) or (t["spotify_id"] or "")
                res_thumb_val = (t["result_thumbnail"] if "result_thumbnail" in t.keys() else "") or ""
                if not res_thumb_val and dest_id_val and len(dest_id_val) == 11:
                    res_thumb_val = f"https://i.ytimg.com/vi/{dest_id_val}/mqdefault.jpg"

                tracks.append({
                    "video_id": t["video_id"],
                    "title": t_title,
                    "ascii_title": t_ascii,
                    "artists": artists,
                    "album": t_album,
                    "duration_s": round((t["duration_ms"] or 0) / 1000),
                    "genre": t_genre,
                    "status": t_status,
                    "score": t["score"],
                    "spotify_id": t["spotify_id"] or "",
                    "dest_id": dest_id_val,
                    "thumbnail_url": (t["thumbnail_url"] if "thumbnail_url" in t.keys() else "") or "",
                    "result_thumbnail": res_thumb_val,
                    "reason": t["reason"] or "",
                    "result_title": r_title,
                    "ascii_result": r_ascii,
                    "genre_source": t["genre_source"] if "genre_source" in t.keys() and t["genre_source"] else "",
                    "in_playlists": in_playlists,
                })
            res_tracks = {"tracks": tracks, "total": len(tracks)}
            _set_cached_api(cache_key, res_tracks)
            self._send_json(res_tracks)
            return

        elif path == "/api/uris":
            pl_id_str = query.get("playlist_id", ["all"])[0]
            genre = query.get("genre", [""])[0]
            chunk_size = int(query.get("chunk_size", ["50"])[0])
            cache_key = f"uris_{pl_id_str}_{genre}_{chunk_size}"
            cached = _get_cached_api(cache_key, ttl_seconds=5.0)
            if cached is not None:
                self._send_json(cached)
                return

            db.init_db()
            if pl_id_str in ("all", "", "0"):
                if genre:
                    raw_tracks = db.get_all_library_tracks_for_genre(genre)
                else:
                    raw_tracks = db.get_all_library_tracks()
            else:
                try:
                    pl_id = int(pl_id_str)
                    if genre:
                        raw_tracks = db.get_playlist_tracks_for_genre(pl_id, genre)
                    else:
                        raw_tracks = db.get_playlist_tracks(pl_id)
                except ValueError:
                    raw_tracks = db.get_all_library_tracks()

            uris = []
            for t in raw_tracks:
                if t["status"] in ("accepted", "resolved_auto") and t["spotify_id"]:
                    uris.append(f"spotify:track:{t['spotify_id']}")

            chunks = []
            for i, start in enumerate(range(0, len(uris), chunk_size), 1):
                part = uris[start : start + chunk_size]
                chunks.append({
                    "part": i,
                    "count": len(part),
                    "uris": part,
                    "text": "\n".join(part),
                })
            res_uris = {"total": len(uris), "uris": uris, "chunks": chunks}
            _set_cached_api(cache_key, res_uris)
            self._send_json(res_uris)
            return

        elif path == "/api/missing":
            pl_id_str = query.get("playlist_id", ["all"])[0]
            pl_id = None if pl_id_str in ("all", "", "0") else int(pl_id_str)
            cache_key = f"missing_{pl_id_str}"
            cached = _get_cached_api(cache_key, ttl_seconds=3.0)
            if cached is not None:
                self._send_json(cached)
                return

            db.init_db()
            raw_tracks = db.get_missing_tracks(pl_id)
            data = []
            for t in raw_tracks:
                artists = json.loads(t["artists"]) if t["artists"] else []
                data.append({
                    "video_id": t["video_id"],
                    "title": t["title"],
                    "artists": artists,
                    "album": t["album"] or "",
                    "duration_s": round((t["duration_ms"] or 0) / 1000),
                    "status": t["status"] or "pending",
                    "score": t["score"],
                    "reason": t["reason"] or "",
                    "result_title": t["result_title"] or "",
                    "result_artist": t["result_artist"] or "",
                })
            res_missing = {"missing": data}
            _set_cached_api(cache_key, res_missing)
            self._send_json(res_missing)
            return

        elif path == "/api/ytm-auth-status":
            from yt2sp.destinations.ytm_writer import check_ytm_auth
            auth_ok, auth_err = check_ytm_auth()
            self._send_json({
                "authenticated": auth_ok,
                "error": auth_err,
                "auth_file": "ytm_auth.json",
            })
            return

        elif path == "/api/alternatives":
            db.init_db()
            vid = query.get("video_id", [""])[0]
            if not vid:
                self._send_json({"alternatives": []})
                return
            conn = db._get_conn()
            row = conn.execute("SELECT * FROM tracks WHERE video_id=?", (vid,)).fetchone()
            if not row:
                self._send_json({"alternatives": []})
                return
            artists = json.loads(row["artists"]) if row["artists"] else []
            r_keys = row.keys()
            src_prov = (row["source_provider"] if "source_provider" in r_keys else None) or "youtube"

            if src_prov == "spotify":
                from yt2sp.destinations.ytm_resolver import find_ytm_alternative_versions
                alts = find_ytm_alternative_versions(row["title"], artists)
                for a in alts:
                    if "video_id" in a and "spotify_id" not in a:
                        a["spotify_id"] = a["video_id"]
            else:
                from yt2sp.resolve.spotify_resolver import find_alternative_versions
                alts = find_alternative_versions(row["title"], artists)
                for a in alts:
                    if "spotify_id" in a and "video_id" not in a:
                        a["video_id"] = a["spotify_id"]

            self._send_json({"video_id": vid, "title": row["title"], "artists": artists, "alternatives": alts})
            return

        elif path == "/api/preview":
            video_id = query.get("video_id", [""])[0].strip()
            q_param = query.get("q", [""])[0].strip()
            sp_id = query.get("spotify_id", [""])[0].strip()
            title_param = query.get("title", [""])[0].strip()
            artist_param = query.get("artist", [""])[0].strip()

            cache_key = f"preview_v_{video_id}_s_{sp_id}_q_{q_param}_t_{title_param}"
            cached = _get_cached_api(cache_key, ttl_seconds=86400.0)
            if cached is not None:
                self._send_json(cached)
                return

            db.init_db()
            conn = db._get_conn()

            candidates: list[str] = []

            # 1. Database match check (highest accuracy Spotify metadata)
            if video_id:
                m_row = conn.execute(
                    "SELECT result_title, result_artist, spotify_id FROM matches WHERE video_id=?",
                    (video_id,),
                ).fetchone()
                if m_row and m_row["result_title"]:
                    art = (m_row["result_artist"] or "").strip('[]"\'')
                    candidates.append(f"{art} {m_row['result_title']}".strip())
                    candidates.append(m_row["result_title"].strip())

            if sp_id and not candidates:
                row = conn.execute(
                    "SELECT result_title, result_artist FROM matches WHERE spotify_id=?",
                    (sp_id,),
                ).fetchone()
                if row and row["result_title"]:
                    art = (row["result_artist"] or "").strip('[]"\'')
                    candidates.append(f"{art} {row['result_title']}".strip())
                    candidates.append(row["result_title"].strip())

            # 2. Provided title & artist params
            if title_param:
                cleaned_tp = _clean_preview_query(title_param)
                if cleaned_tp:
                    candidates.append(cleaned_tp)
                if artist_param and artist_param.lower() not in (cleaned_tp or title_param).lower():
                    candidates.append(f"{artist_param} {cleaned_tp or title_param}".strip())
                candidates.append(title_param.strip())

            # 3. Track title directly from DB if video_id given
            if video_id:
                t_row = db.get_track(video_id)
                if t_row:
                    if "preview_url" in t_row.keys() and t_row["preview_url"]:
                        res_obj = {
                            "preview_url": t_row["preview_url"],
                            "title": t_row["title"] or "",
                            "artist": (json.loads(t_row["artists"])[0] if t_row["artists"] else "") if ("artists" in t_row.keys() and t_row["artists"]) else "",
                            "provider": "spotify",
                            "duration": 30,
                        }
                        _set_cached_api(cache_key, res_obj)
                        self._send_json(res_obj)
                        return
                    if t_row["title"]:
                        raw_title = t_row["title"].strip()
                        cleaned_db_title = _clean_preview_query(raw_title)
                        if cleaned_db_title:
                            candidates.append(cleaned_db_title)
                        try:
                            arts = json.loads(t_row["artists"]) if t_row["artists"] else []
                            art_str = arts[0] if arts else ""
                        except Exception:
                            art_str = ""
                        if art_str and art_str.lower() not in (cleaned_db_title or raw_title).lower():
                            candidates.append(f"{art_str} {cleaned_db_title or raw_title}".strip())
                        candidates.append(raw_title)

            # 4. Provided q_param
            if q_param:
                cleaned_q = _clean_preview_query(q_param)
                if cleaned_q:
                    candidates.append(cleaned_q)
                candidates.append(q_param)

            # 5. Normalized title variations
            extra_norm: list[str] = []
            for c in candidates[:]:
                try:
                    norm = normalize_title(c)
                    if norm:
                        extra_norm.append(norm)
                except Exception:
                    pass
            candidates.extend(extra_norm)

            # Deduplicate preserving order
            seen: set[str] = set()
            unique_candidates: list[str] = []
            for c in candidates:
                c_str = c.strip()
                if c_str and c_str.lower() not in seen:
                    seen.add(c_str.lower())
                    unique_candidates.append(c_str)

            preview_url = None
            track_name = ""
            artist_name = ""
            provider = ""

            for cand in unique_candidates:
                # Try Deezer
                d_res = _fetch_preview_deezer(cand)
                if d_res:
                    preview_url, track_name, artist_name = d_res
                    provider = "deezer"
                    break
                # Try iTunes fallback
                it_res = _fetch_preview_itunes(cand)
                if it_res:
                    preview_url, track_name, artist_name = it_res
                    provider = "itunes"
                    break

            res_obj = {
                "preview_url": preview_url,
                "title": track_name,
                "artist": artist_name,
                "provider": provider,
                "duration": 30 if preview_url else 0,
            }
            if preview_url:
                _set_cached_api(cache_key, res_obj)
            self._send_json(res_obj)
            return

        elif path == "/api/task-status":
            self._send_json(_get_job_state())
            return

        # ── Static Files ──
        ui_dir = Path(__file__).parent
        if path in ("/", "/index.html"):
            self._send_file(ui_dir / "index.html")
            return

        # Fallback static file serve
        requested = (ui_dir / path.lstrip("/")).resolve()
        if requested.is_file() and str(requested).startswith(str(ui_dir.resolve())):
            self._send_file(requested)
        else:
            self._send_file(ui_dir / "index.html")

    def do_POST(self) -> None:
        if not self._is_safe_origin():
            self._send_json({"error": "Akses ditolak: Permintaan lintas origin tidak diizinkan untuk keamanan."}, 403)
            return

        path = urllib.parse.urlparse(self.path).path
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        if path == "/api/cancel":
            _job_cancel_event.set()
            with _job_lock:
                was_running = _job_state["running"]
                job_type = _job_state["type"]
                curr = _job_state["current"]
                if was_running:
                    _job_state["running"] = False
                    _job_state["message"] = f"Pencocokan dibatalkan ({curr} lagu tersimpan)."
            _invalidate_api_cache()
            self._send_json({"status": "cancelled", "was_running": was_running})
            return

        if path == "/api/extract":
            _job_cancel_event.clear()
            with _job_lock:
                if _job_state["running"]:
                    self._send_json({"error": "Proses lain sedang berjalan"}, 400)
                    return
                _job_state["running"] = True
                _job_state["type"] = "extract"
                _job_state["current"] = 0
                _job_state["total"] = 0
                _job_state["message"] = "Menyiapkan ekstraksi playlist..."
                _job_state["error"] = None
            _invalidate_api_cache()

            raw_pl = payload.get("playlist_id", "").strip()
            liked = payload.get("liked", False)
            direction = (payload.get("direction") or "auto").strip().lower()

            def _run():
                try:
                    db.init_db()
                    from yt2sp.sources.spotify_extract import clean_spotify_playlist_id, extract_spotify_playlist
                    from yt2sp.ytm.extract import (
                        get_ytm, get_playlist_details, parse_track, get_liked_songs, clean_playlist_id
                    )

                    clean_sp_id = clean_spotify_playlist_id(raw_pl)
                    is_spotify_source = False
                    if direction == "sp_to_yt":
                        is_spotify_source = True
                    elif direction == "yt_to_sp":
                        is_spotify_source = False
                    else:
                        is_spotify_source = bool(clean_sp_id)

                    # ── Jalur A: Ekstraksi dari Spotify ──
                    if is_spotify_source:
                        _update_job(True, "extract", 0, 0, "Menghubungi Spotify...")
                        sp_id = clean_sp_id or clean_spotify_playlist_id(raw_pl)
                        if not sp_id:
                            raise ValueError("Link atau ID Playlist Spotify tidak valid!")
                        res = extract_spotify_playlist(sp_id)
                        pl_title = res.title
                        tracks_raw = res.tracks
                        unavail_count = res.unavailable_count
                        sp_pid = getattr(res, "playlist_id", None) or getattr(res, "id", sp_id)
                        total = len(tracks_raw)
                        if total == 0:
                            raise ValueError(f"Tidak ada lagu ditemukan di playlist Spotify '{pl_title}'. Pastikan playlist bersifat Publik.")

                        _update_job(True, "extract", 0, total, f"Menyimpan {total} lagu dari '{pl_title}'...")
                        cover_img = getattr(res, "cover_image", None) or getattr(res, "thumbnail_url", None)
                        db_pl_id = db.upsert_playlist(
                            sp_pid,
                            pl_title,
                            total,
                            unavailable_count=unavail_count,
                            source_provider="spotify",
                            destination_provider="ytm",
                            description=getattr(res, "description", "") or "",
                            thumbnail_url=cover_img,
                        )

                        saved = 0
                        for pos, tr in enumerate(tracks_raw):
                            if _job_cancel_event.is_set():
                                _update_job(False, "extract", saved, total, f"Ekstraksi dibatalkan ({saved} lagu tersimpan).")
                                return
                            display_title = str(tr.title)[:25]
                            db.upsert_track(
                                tr.track_id,
                                tr.title,
                                tr.artists,
                                tr.album,
                                tr.duration_ms,
                                "song",
                                thumbnail_url=tr.thumbnail_url,
                                preview_url=tr.preview_url,
                                isrc=tr.isrc,
                                source_provider="spotify",
                            )
                            db.upsert_playlist_track(db_pl_id, tr.track_id, pos)
                            saved += 1
                            _update_job(True, "extract", pos + 1, total, f"Menyimpan ({pos + 1}/{total}): {display_title}")

                        finish_msg = f"Selesai! {saved} lagu berhasil ditarik dari playlist Spotify '{pl_title}'."
                        if unavail_count > 0:
                            finish_msg += f" ({unavail_count} lagu tidak dapat dimuat)."
                        _update_job(False, "extract", saved, total, finish_msg)

                    # ── Jalur B: Ekstraksi dari YouTube Music ──
                    else:
                        _update_job(True, "extract", 0, 0, "Menghubungi YouTube Music...")
                        ytm = get_ytm()
                        if liked:
                            tracks_raw = get_liked_songs(ytm)
                            pl_title = "Liked Songs"
                            yt_pid = "LIKED_SONGS"
                            unavail_count = 0
                        else:
                            clean_yt_id = clean_playlist_id(raw_pl)
                            if not clean_yt_id:
                                raise ValueError("Link atau ID Playlist YouTube Music tidak valid!")
                            res_yt = get_playlist_details(ytm, clean_yt_id)
                            pl_title = res_yt.title
                            tracks_raw = res_yt.tracks
                            unavail_count = getattr(res_yt, "unavailable_count", 0)
                            yt_pid = clean_yt_id

                        total = len(tracks_raw)
                        if total == 0:
                            raise ValueError(f"Tidak ada lagu ditemukan di playlist '{pl_title}'.")

                        _update_job(True, "extract", 0, total, f"Menyimpan {total} lagu dari '{pl_title}'...")
                        db_pl_id = db.upsert_playlist(
                            yt_pid,
                            pl_title,
                            total,
                            unavailable_count=unavail_count,
                            source_provider="youtube",
                            destination_provider="spotify",
                        )

                        saved = 0
                        for pos, raw in enumerate(tracks_raw):
                            if _job_cancel_event.is_set():
                                _update_job(False, "extract", saved, total, f"Ekstraksi dibatalkan ({saved} lagu tersimpan).")
                                return
                            track = parse_track(raw)
                            raw_title = (track["title"] if track else (raw.get("title") or "")) or "Lagu"
                            display_title = str(raw_title)[:25]
                            if track:
                                db.upsert_track(
                                    track["video_id"],
                                    track["title"],
                                    track["artists"],
                                    track["album"],
                                    track["duration_ms"],
                                    track["video_type"],
                                    source_provider="youtube",
                                )
                                db.upsert_playlist_track(db_pl_id, track["video_id"], pos)
                                saved += 1
                            _update_job(True, "extract", pos + 1, total, f"Menyimpan ({pos + 1}/{total}): {display_title}")

                        finish_msg = f"Selesai! {saved} lagu berhasil ditarik dari '{pl_title}'."
                        _update_job(False, "extract", saved, total, finish_msg)
                except Exception as exc:
                    logger.exception("Extract error: %s", exc)
                    _update_job(False, "extract", 0, 0, f"Gagal: {str(exc)}", error=str(exc))

            threading.Thread(target=_run, daemon=True).start()
            self._send_json({"status": "started"})
            return

        elif path == "/api/resolve":
            _job_cancel_event.clear()
            with _job_lock:
                if _job_state["running"]:
                    self._send_json({"error": "Pencocokan sedang berjalan"}, 400)
                    return
                _job_state["running"] = True
                _job_state["type"] = "resolve"
                _job_state["current"] = 0
                _job_state["total"] = 0
                _job_state["message"] = "Menyiapkan daftar lagu untuk dicocokkan..."
                _job_state["error"] = None
            _invalidate_api_cache()

            pl_id_param = payload.get("playlist_id")
            force_rematch = payload.get("force", False)

            def _run():
                from yt2sp.resolve.pipeline import run_resolve
                try:
                    db.init_db()
                    cfg = load_config()

                    pl_id = None
                    if pl_id_param not in (None, "all", "", 0, "0"):
                        try:
                            pl_id = int(pl_id_param)
                        except (ValueError, TypeError):
                            pl_id = None

                    pending = db.get_pending_tracks(playlist_id=pl_id)

                    # Jika tidak ada pending lagu, periksa apakah ada failed / un-accepted untuk diulang
                    if len(pending) == 0:
                        reset_count = db.reset_unresolved_tracks_to_pending(playlist_id=pl_id, reset_all=force_rematch)
                        if reset_count > 0:
                            pending = db.get_pending_tracks(playlist_id=pl_id)

                    total = len(pending)

                    # Jika masih 0 (semua lagu di playlist sudah cocok / accepted)
                    if total == 0:
                        all_tracks = db.get_playlist_tracks(pl_id) if pl_id else db.get_all_library_tracks()
                        tot_count = max(len(all_tracks), 1)
                        _update_job(False, "resolve", tot_count, tot_count, f"Semua {tot_count} lagu sudah cocok! Siap diekspor.")
                        _invalidate_api_cache()
                        return

                    _update_job(True, "resolve", 0, total, f"Memulai pencarian untuk {total} lagu...")

                    def on_progress(vid: str, status: str, score: float):
                        curr = _get_job_state()["current"] + 1
                        tr = db.get_track(vid)
                        t_title = tr["title"] if tr and tr["title"] else vid[:10]
                        status_label = "Cocok" if status == "resolved_auto" else ("Review" if status == "needs_review" else ("Dilewati" if status == "skipped" else "Belum Ketemu"))
                        _update_job(True, "resolve", curr, total, f"Mencocokkan ({curr}/{total}): {t_title[:25]} [{status_label}]")

                    run_resolve(
                        playlist_id=pl_id,
                        rate_per_minute=cfg["resolve"]["rate_per_minute"],
                        auto_threshold=cfg["match"]["auto_accept_threshold"],
                        review_threshold=cfg["match"]["review_threshold"],
                        on_progress=on_progress,
                        stop_event=_job_cancel_event,
                    )
                    if _job_cancel_event.is_set():
                        curr = _get_job_state()["current"]
                        _update_job(False, "resolve", curr, total, f"Pencocokan dibatalkan ({curr} lagu tersimpan).")
                    else:
                        _update_job(False, "resolve", total, total, "Pencocokan selesai!")
                    _invalidate_api_cache()
                except Exception as exc:
                    logger.exception("Resolve error: %s", exc)
                    _update_job(False, "resolve", 0, 0, f"Error: {str(exc)[:150]}", error=str(exc))
                    _invalidate_api_cache()

            threading.Thread(target=_run, daemon=True).start()
            self._send_json({"status": "started"})
            return

        elif path == "/api/tag-genre":
            _job_cancel_event.clear()
            if _get_job_state()["running"]:
                self._send_json({"error": "Proses lain sedang berjalan"}, 400)
                return

            def _run():
                from yt2sp.resolve.genre import fetch_genre_validated
                try:
                    db.init_db()
                    missing = db.get_tracks_without_genre(include_uncategorized=True)
                    total = len(missing)
                    _update_job(True, "genre", 0, total, f"Mendeteksi & memvalidasi genre untuk {total} lagu...")

                    for idx, t in enumerate(missing, 1):
                        if _job_cancel_event.is_set():
                            _update_job(False, "genre", idx - 1, total, f"Deteksi genre dibatalkan ({idx - 1} lagu selesai).")
                            return
                        artists = json.loads(t["artists"]) if t["artists"] else []
                        r_title = t["result_title"] if "result_title" in t.keys() else None
                        r_artist = t["result_artist"] if "result_artist" in t.keys() else None
                        gres = fetch_genre_validated(
                            t["title"] or "",
                            artists,
                            result_title=r_title,
                            result_artist=r_artist,
                        )
                        db.update_track_genre(t["video_id"], gres.genre, source=gres.source)
                        _update_job(True, "genre", idx, total, f"Genre ({idx}/{total}): {gres.genre} [{gres.status}] - {t['title'][:20]}")

                    _update_job(False, "genre", total, total, "Validasi & deteksi genre selesai!")
                except Exception as exc:
                    logger.exception("Genre error: %s", exc)
                    _update_job(False, "genre", 0, 0, f"Error: {str(exc)[:150]}", error=str(exc))

            threading.Thread(target=_run, daemon=True).start()
            self._send_json({"status": "started"})
            return

        elif path == "/api/review":
            db.init_db()
            video_id = payload.get("video_id")
            action = payload.get("action")
            spotify_id = payload.get("spotify_id")

            if not video_id or action not in ("accept", "reject", "manual"):
                self._send_json({"error": "Payload tidak valid"}, 400)
                return

            if action in ("accept", "reject"):
                m = db.get_match(video_id)
                if not m:
                    self._send_json({"error": "Lagu belum memiliki data pencocokan"}, 404)
                    return

                if action == "accept":
                    db.set_match(
                        video_id,
                        spotify_id=m["spotify_id"],
                        tier=m["tier"] or "T1",
                        score=m["score"] or 1.0,
                        status="accepted",
                        result_title=m["result_title"] or "",
                        result_artist=m["result_artist"] or "",
                        decided_by="ui_human",
                        reason="Diterima lewat UI",
                    )
                elif action == "reject":
                    db.set_match(
                        video_id,
                        spotify_id=None,
                        tier=m["tier"] or "T1",
                        score=m["score"] or 0.0,
                        status="rejected",
                        decided_by="ui_human",
                        reason="Ditolak lewat UI",
                    )
            elif action == "manual":
                track = db.get_track(video_id)
                m = db.get_match(video_id)
                if not track and not m:
                    self._send_json({"error": "Lagu tidak ditemukan di database"}, 404)
                    return

                # Support YouTube Music / YouTube video link / ID atau Spotify format
                import re
                clean_input = (spotify_id or "").strip()
                final_id = None
                m_ytm = re.search(r"music\.youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})", clean_input)
                m_yt = re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})", clean_input)
                m_11 = re.search(r"^([a-zA-Z0-9_-]{11})$", clean_input)
                m_sp = re.search(r"(?:open\.spotify\.com/track/|spotify:track:)([A-Za-z0-9]{22})", clean_input)

                if m_ytm:
                    final_id = m_ytm.group(1)
                elif m_yt:
                    final_id = m_yt.group(1)
                elif m_11:
                    final_id = m_11.group(1)
                elif m_sp:
                    final_id = m_sp.group(1)

                if not final_id:
                    self._send_json({
                        "error": "Link atau Video ID YouTube Music tidak valid. Masukkan URL seperti https://music.youtube.com/watch?v=... atau Video ID 11 karakter."
                    }, 400)
                    return

                yt_title = ""
                yt_thumbnail = ""
                if len(final_id) == 11:
                    try:
                        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={final_id}&format=json"
                        req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(req, timeout=3) as r:
                            oembed_data = json.loads(r.read().decode("utf-8"))
                            yt_title = oembed_data.get("title", "")
                            yt_thumbnail = oembed_data.get("thumbnail_url", "")
                    except Exception:
                        pass
                else:
                    try:
                        oembed_url = f"https://open.spotify.com/oembed?url=https://open.spotify.com/track/{final_id}"
                        req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(req, timeout=3) as r:
                            oembed_data = json.loads(r.read().decode("utf-8"))
                            yt_title = oembed_data.get("title", "")
                            yt_thumbnail = oembed_data.get("thumbnail_url", "")
                    except Exception:
                        pass

                track_title = track["title"] if track else (m["result_title"] if m else "")
                artists_val = track["artists"] if track else (m["result_artist"] if m else "")

                db.set_match(
                    video_id,
                    spotify_id=final_id,
                    tier="manual",
                    score=1.0,
                    status="accepted",
                    result_title=yt_title or track_title or "YouTube Music Track",
                    result_artist=artists_val or "Manual Input",
                    decided_by="ui_manual",
                    reason="Diinput manual oleh pengguna lewat UI",
                    dest_id=final_id,
                    result_url=f"https://music.youtube.com/watch?v={final_id}" if len(final_id) == 11 else None,
                    result_thumbnail=yt_thumbnail or None,
                )

                _invalidate_api_cache()
                self._send_json({
                    "status": "ok",
                    "spotify_id": final_id,
                    "dest_id": final_id,
                    "title": yt_title or track_title,
                    "thumbnail_url": yt_thumbnail,
                })
                return

            _invalidate_api_cache()
            self._send_json({"status": "ok"})
            return

        elif path == "/api/choose-alternative":
            db.init_db()
            video_id = payload.get("video_id")
            spotify_id = payload.get("spotify_id")
            title = payload.get("title", "")
            artist = payload.get("artist", "")
            tag = payload.get("tag", "Penyanyi Berbeda (Cover)")

            if not video_id or not spotify_id:
                self._send_json({"error": "Payload tidak lengkap"}, 400)
                return

            db.set_match(
                video_id,
                spotify_id=spotify_id,
                tier="alternative",
                score=0.90,
                status="accepted",
                result_title=title,
                result_artist=artist,
                decided_by="user_alternative",
                reason=f"Dipilih pengguna: {tag} ({artist})",
            )
            _invalidate_api_cache()
            self._send_json({"status": "ok"})
            return

        elif path == "/api/reset":
            db.init_db()
            clear_cache = payload.get("clear_cache", False)
            delete_remote = payload.get("delete_remote", False)
            if delete_remote:
                try:
                    from yt2sp.destinations.ytm_writer import get_authenticated_ytm, check_ytm_auth
                    if check_ytm_auth():
                        ytm = get_authenticated_ytm()
                        remote_pls = db.get_all_exported_remote_playlists()
                        for r_pid in remote_pls:
                            try:
                                ytm.delete_playlist(r_pid)
                            except Exception as e:
                                logger.warning("Gagal hapus playlist remote YTM %s: %s", r_pid, e)
                except Exception as exc:
                    logger.warning("Error saat hapus remote playlist: %s", exc)

            db.reset_all_data(clear_cache=clear_cache)
            _invalidate_api_cache()
            _update_job(False, None, 0, 0, "Database berhasil dikosongkan. Siap mulai dari 0.")
            self._send_json({"status": "ok", "message": "Semua data berhasil direset ke 0."})
            return

        elif path == "/api/delete-playlist":
            db.init_db()
            playlist_ids = payload.get("playlist_ids")
            playlist_id = payload.get("playlist_id")
            delete_remote = payload.get("delete_remote", False)

            if delete_remote:
                try:
                    from yt2sp.destinations.ytm_writer import get_authenticated_ytm, check_ytm_auth
                    if check_ytm_auth():
                        ytm = get_authenticated_ytm()
                        target_pids = []
                        if playlist_ids and isinstance(playlist_ids, list):
                            target_pids.extend(playlist_ids)
                        elif playlist_id:
                            target_pids.append(playlist_id)
                        for pid in target_pids:
                            try:
                                p_row = db.get_playlist(int(pid))
                                if p_row:
                                    keys = p_row.keys()
                                    exp_id = p_row["exported_playlist_id"] if "exported_playlist_id" in keys else None
                                    yt_id = p_row["yt_playlist_id"] if "yt_playlist_id" in keys else None
                                    to_del = exp_id or (yt_id if yt_id and (yt_id.startswith("PL") or yt_id.startswith("RD")) else None)
                                    if to_del:
                                        ytm.delete_playlist(to_del)
                            except Exception as e:
                                logger.warning("Gagal hapus remote playlist: %s", e)
                except Exception as exc:
                    logger.warning("Error saat remote playlist delete: %s", exc)

            if playlist_ids and isinstance(playlist_ids, list):
                valid_ids = []
                for pid in playlist_ids:
                    try:
                        valid_ids.append(int(pid))
                    except (ValueError, TypeError):
                        pass
                if not valid_ids:
                    self._send_json({"error": "Daftar ID playlist tidak valid"}, 400)
                    return
                db.delete_playlists(valid_ids)
                _invalidate_api_cache()
                self._send_json({"status": "ok", "message": f"{len(valid_ids)} playlist berhasil dihapus."})
                return
            elif playlist_id:
                try:
                    pl_id = int(playlist_id)
                except (ValueError, TypeError):
                    self._send_json({"error": "ID playlist tidak valid"}, 400)
                    return
                db.delete_playlist(pl_id)
                _invalidate_api_cache()
                self._send_json({"status": "ok", "message": f"Playlist {pl_id} berhasil dihapus."})
                return
            else:
                self._send_json({"error": "ID playlist tidak diberikan"}, 400)
                return

        elif path == "/api/delete-track":
            db.init_db()
            video_ids = payload.get("video_ids")
            video_id = payload.get("video_id")
            playlist_id = payload.get("playlist_id")
            delete_remote = payload.get("delete_remote", False)
            pl_id = None
            if playlist_id not in (None, "all", "", 0, "0"):
                try:
                    pl_id = int(playlist_id)
                except (ValueError, TypeError):
                    pl_id = None

            if delete_remote and pl_id:
                try:
                    from yt2sp.destinations.ytm_writer import get_authenticated_ytm, check_ytm_auth
                    if check_ytm_auth():
                        p_row = db.get_playlist(pl_id)
                        if p_row and "exported_playlist_id" in p_row.keys() and p_row["exported_playlist_id"]:
                            ytm = get_authenticated_ytm()
                            r_pl = ytm.get_playlist(p_row["exported_playlist_id"])
                            to_remove = []
                            del_set = set([str(v) for v in video_ids] if video_ids else [str(video_id)])
                            for item in r_pl.get("tracks", []):
                                if item.get("videoId") in del_set and "setVideoId" in item:
                                    to_remove.append({"videoId": item["videoId"], "setVideoId": item["setVideoId"]})
                            if to_remove:
                                ytm.remove_playlist_items(p_row["exported_playlist_id"], to_remove)
                except Exception as e:
                    logger.warning("Gagal hapus lagu dari remote playlist YTM: %s", e)

            if video_ids and isinstance(video_ids, list):
                clean_vids = [str(v) for v in video_ids if v]
                if not clean_vids:
                    self._send_json({"error": "Daftar video ID kosong"}, 400)
                    return
                db.delete_tracks(clean_vids, pl_id)
                _invalidate_api_cache()
                self._send_json({"status": "ok", "message": f"{len(clean_vids)} lagu berhasil dihapus."})
                return
            elif video_id:
                db.delete_track(str(video_id), pl_id)
                _invalidate_api_cache()
                self._send_json({"status": "ok", "message": f"Lagu {video_id} berhasil dihapus."})
                return
            else:
                self._send_json({"error": "Video ID diperlukan"}, 400)
                return
                return

        elif path == "/api/create-grouped-playlist":
            db.init_db()
            groups = payload.get("groups", [])
            if not groups and "title" in payload:
                groups = [payload]

            if not groups:
                self._send_json({"error": "Daftar grup playlist kosong"}, 400)
                return

            import time
            conn = db._get_conn()
            created_results = []
            for g in groups:
                title = (g.get("title") or "Custom Group").strip()
                vids = g.get("video_ids", [])
                if not vids:
                    continue

                # Filter valid video IDs that exist in tracks table
                valid_vids = []
                for vid in vids:
                    row = conn.execute("SELECT 1 FROM tracks WHERE video_id=?", (str(vid),)).fetchone()
                    if row:
                        valid_vids.append(str(vid))

                if not valid_vids:
                    continue

                custom_pid = f"CUSTOM_{int(time.time()*1000)}_{abs(hash(title)) % 10000}"
                pl_id = db.upsert_playlist(custom_pid, title, len(valid_vids))
                for pos, vid in enumerate(valid_vids):
                    try:
                        db.upsert_playlist_track(pl_id, vid, pos)
                    except Exception:
                        pass
                created_results.append({"id": pl_id, "title": title, "track_count": len(valid_vids)})

            _invalidate_api_cache()
            self._send_json({"status": "ok", "created": created_results})
            return

        elif path in ("/api/export", "/api/export-ytm"):
            db.init_db()
            pl_id_param = payload.get("playlist_id")
            custom_title = (payload.get("title") or "").strip()
            custom_desc = (payload.get("description") or "").strip()
            privacy = (payload.get("privacy") or "PRIVATE").upper()
            if privacy not in ("PRIVATE", "PUBLIC", "UNLISTED"):
                privacy = "PRIVATE"

            pl_id = None
            if pl_id_param not in (None, "all", "", 0, "0"):
                try:
                    pl_id = int(pl_id_param)
                except (ValueError, TypeError):
                    pl_id = None

            pl_info = db.get_playlist(pl_id) if pl_id else None
            explicit_target = (payload.get("target") or payload.get("destination") or "").lower()

            if path == "/api/export-ytm" or explicit_target in ("ytm", "ytmusic", "youtube"):
                target_dest = "ytm"
            elif explicit_target in ("spotify", "sp"):
                target_dest = "spotify"
            elif pl_info and ("destination_provider" in pl_info.keys() and pl_info["destination_provider"] == "ytm"):
                target_dest = "ytm"
            elif pl_info and ("destination_provider" in pl_info.keys() and pl_info["destination_provider"] == "spotify"):
                target_dest = "spotify"
            else:
                target_dest = "ytm"

            if pl_id:
                raw_tracks = db.get_playlist_tracks(pl_id)
                default_title = (pl_info["title"] if pl_info else "Migrated Playlist")
            else:
                raw_tracks = db.get_all_library_tracks()
                default_title = "Migrated Library"

            final_title = custom_title or default_title

            # ── Export ke YouTube Music ──
            if target_dest == "ytm":
                from yt2sp.destinations.ytm_writer import create_and_populate_ytm_playlist, check_ytm_auth
                auth_ok, auth_err = check_ytm_auth()
                if not auth_ok:
                    self._send_json({
                        "error": f"Autentikasi YouTube Music belum siap: {auth_err}. Silakan setup akun di tab Accounts."
                    }, 401)
                    return

                track_ids = []
                for t in raw_tracks:
                    row = dict(t)
                    st = row.get("status")
                    dest_id = row.get("dest_id") or row.get("spotify_id")
                    if st in ("accepted", "resolved_auto") and dest_id:
                        track_ids.append(dest_id)

                if not track_ids:
                    self._send_json({
                        "error": "Tidak ada lagu yang sudah disetujui (accepted / auto) untuk diekspor ke YouTube Music."
                    }, 400)
                    return

                try:
                    res = create_and_populate_ytm_playlist(
                        title=f"{final_title} (Spotify2YTM)" if "Spotify2YTM" not in final_title else final_title,
                        track_ids=track_ids,
                        description=custom_desc or "Migrated using YT2SP Unified Migration Platform",
                        privacy_status=privacy,
                    )
                    if pl_id:
                        db.update_playlist_export(pl_id, res.playlist_id, res.playlist_url)
                    self._send_json({
                        "status": "ok",
                        "destination": "ytm",
                        "playlist_id": res.playlist_id,
                        "playlist_url": res.playlist_url,
                        "total_added": res.total_added,
                        "total_requested": res.total_requested,
                        "failed_count": len(res.failed_ids),
                        "title": final_title,
                    })
                except Exception as exc:
                    logger.exception("Export YTM error: %s", exc)
                    self._send_json({"error": f"Gagal mengekspor playlist ke YouTube Music: {str(exc)}"}, 500)
                return

            # ── Export ke Spotify (URI blocks + CSV report) ──
            else:
                from yt2sp.export.writer import write_uri_blocks
                from yt2sp.export.report import write_csv_report

                uris = []
                accepted_tracks = []
                for t in raw_tracks:
                    row = dict(t)
                    st = row.get("status")
                    sp_id = row.get("spotify_id") or row.get("dest_id")
                    if st in ("accepted", "resolved_auto") and sp_id:
                        uris.append(f"spotify:track:{sp_id}")
                        accepted_tracks.append(t)

                if not uris:
                    self._send_json({
                        "error": "Tidak ada lagu yang sudah disetujui (accepted / auto) untuk diekspor ke Spotify."
                    }, 400)
                    return

                out_dir = Path("output")
                chunk_size = int(payload.get("chunk_size", 50))
                files = write_uri_blocks(final_title, uris, out_dir / "uris", chunk_size=chunk_size)
                csv_path = write_csv_report(final_title, accepted_tracks, out_dir / "reports")

                self._send_json({
                    "status": "ok",
                    "destination": "spotify",
                    "total_uris": len(uris),
                    "files_created": [str(f) for f in files],
                    "report_file": str(csv_path),
                    "title": final_title,
                    "message": f"Export Spotify selesai. {len(uris)} URI tersimpan di {out_dir / 'uris'}.",
                })
                return

        elif path == "/api/save-ytm-auth":
            headers_raw = (payload.get("headers") or "").strip()
            if not headers_raw:
                self._send_json({"error": "Header/cURL tidak boleh kosong."}, 400)
                return
            try:
                from ytmusicapi import setup
                from yt2sp.destinations.ytm_writer import normalize_browser_headers
                normalized = normalize_browser_headers(headers_raw)
                setup(filepath="ytm_auth.json", headers_raw=normalized)
                _invalidate_api_cache()
                self._send_json({"status": "ok", "message": "Autentikasi YouTube Music berhasil disimpan!"})
            except Exception as exc:
                logger.exception("Save YTM auth error: %s", exc)
                self._send_json({"error": f"Gagal menyimpan autentikasi: {str(exc)}"}, 400)
            return

        self.send_error(404, "Endpoint Not Found")


def start_server(host: str = "127.0.0.1", port: int = 5000, open_browser: bool = True) -> None:
    """Jalankan local server Web UI dan buka browser."""
    db.init_db()
    server = ThreadingHTTPServer((host, port), UIHandler)
    url = f"http://{host}:{port}"
    print(f"\n[OK] yt2sp Web UI berjalan di: {url}")
    print("Tekan Ctrl+C di terminal ini untuk mematikan server.\n")

    if open_browser:
        import webbrowser
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nWeb UI dimatikan.")
        server.server_close()


if __name__ == "__main__":
    start_server()
