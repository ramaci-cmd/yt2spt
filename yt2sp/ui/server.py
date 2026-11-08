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
        if path == "/api/status":
            cached = _get_cached_api("status", ttl_seconds=1.0)
            if cached is not None:
                self._send_json(cached)
                return
            db.init_db()
            summary = db.get_status_summary()
            summary["job"] = _get_job_state()
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
                data.append({
                    "id": p["id"],
                    "yt_playlist_id": p["yt_playlist_id"],
                    "title": p["title"],
                    "track_count": p["track_count"],
                    "unavailable_count": unavail,
                    "extracted_at": p["extracted_at"],
                    "genres": [{"genre": g["genre"], "count": g["track_count"]} for g in genres],
                    "sample_video_ids": sample_vids,
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

                tracks.append({
                    "video_id": t["video_id"],
                    "title": t_title,
                    "artists": artists,
                    "album": t_album,
                    "duration_s": round((t["duration_ms"] or 0) / 1000),
                    "genre": t_genre,
                    "status": t_status,
                    "score": t["score"],
                    "spotify_id": t["spotify_id"] or "",
                    "reason": t["reason"] or "",
                    "result_title": t["result_title"] if "result_title" in t.keys() and t["result_title"] else "",
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

        elif path == "/api/alternatives":
            from yt2sp.resolve.spotify_resolver import find_alternative_versions
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
            alts = find_alternative_versions(row["title"], artists)
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
                if t_row and t_row["title"]:
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

        if path == "/api/extract":
            with _job_lock:
                if _job_state["running"]:
                    self._send_json({"error": "Proses lain sedang berjalan"}, 400)
                    return
                _job_state["running"] = True
                _job_state["type"] = "extract"
                _job_state["current"] = 0
                _job_state["total"] = 0
                _job_state["message"] = "Menghubungi YouTube Music..."
                _job_state["error"] = None
            _invalidate_api_cache()

            raw_pl = payload.get("playlist_id", "").strip()
            liked = payload.get("liked", False)

            def _run():
                from yt2sp.ytm.extract import (
                    get_ytm, get_playlist_details, parse_track, get_liked_songs, clean_playlist_id
                )
                try:
                    db.init_db()
                    _update_job(True, "extract", 0, 0, "Menghubungi YouTube Music...")
                    ytm = get_ytm()

                    if liked:
                        tracks_raw = get_liked_songs(ytm)
                        pl_title = "Liked Songs"
                        yt_pid = "LIKED_SONGS"
                        unavail_count = 0
                    else:
                        clean_id = clean_playlist_id(raw_pl)
                        if not clean_id:
                            raise ValueError("Link atau ID Playlist tidak valid!")
                        res = get_playlist_details(ytm, clean_id)
                        pl_title = res.title
                        tracks_raw = res.tracks
                        unavail_count = getattr(res, "unavailable_count", 0)
                        yt_pid = clean_id

                    total = len(tracks_raw)
                    if total == 0:
                        raise ValueError(f"Tidak ada lagu ditemukan di playlist '{pl_title}'. Pastikan playlist bersifat Publik atau Unlisted.")

                    _update_job(True, "extract", 0, total, f"Menyimpan {total} lagu dari '{pl_title}'...")
                    db_pl_id = db.upsert_playlist(yt_pid, pl_title, total, unavailable_count=unavail_count)

                    saved = 0
                    for pos, raw in enumerate(tracks_raw):
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
                            )
                            db.upsert_playlist_track(db_pl_id, track["video_id"], pos)
                            saved += 1
                        _update_job(True, "extract", pos + 1, total, f"Menyimpan ({pos + 1}/{total}): {display_title}")

                    finish_msg = f"Selesai! {saved} lagu berhasil ditarik dari '{pl_title}'."
                    if unavail_count > 0:
                        finish_msg += f" ({unavail_count} video YouTube tidak dapat dimuat karena dihapus/privat oleh uploader)."
                    _update_job(False, "extract", saved, total, finish_msg)
                except Exception as exc:
                    logger.exception("Extract error: %s", exc)
                    _update_job(False, "extract", 0, 0, f"Gagal: {str(exc)}", error=str(exc))

            threading.Thread(target=_run, daemon=True).start()
            self._send_json({"status": "started"})
            return

        elif path == "/api/resolve":
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
                    )
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

                # Ekstrak Spotify ID dari berbagai format link/URI/ID
                import re
                clean_input = (spotify_id or "").strip()
                final_id = None
                m_url = re.search(r"open\.spotify\.com/track/([A-Za-z0-9]{22})", clean_input)
                m_uri = re.search(r"spotify:track:([A-Za-z0-9]{22})", clean_input)
                m_exact = re.search(r"^([A-Za-z0-9]{22})$", clean_input)
                m_any = re.search(r"([A-Za-z0-9]{22})", clean_input)

                if m_url:
                    final_id = m_url.group(1)
                elif m_uri:
                    final_id = m_uri.group(1)
                elif m_exact:
                    final_id = m_exact.group(1)
                elif m_any:
                    final_id = m_any.group(1)

                if not final_id:
                    self._send_json({
                        "error": "Link atau ID Spotify tidak valid. Masukkan URL seperti https://open.spotify.com/track/... atau URI spotify:track:..."
                    }, 400)
                    return

                # Ambil info lagu dari Spotify oEmbed (100% gratis, tanpa API key)
                sp_title = ""
                sp_thumbnail = ""
                try:
                    oembed_url = f"https://open.spotify.com/oembed?url=https://open.spotify.com/track/{final_id}"
                    req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=3) as r:
                        oembed_data = json.loads(r.read().decode("utf-8"))
                        sp_title = oembed_data.get("title", "")
                        sp_thumbnail = oembed_data.get("thumbnail_url", "")
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
                    result_title=sp_title or track_title or "Spotify Track",
                    result_artist=artists_val or "Manual Input",
                    decided_by="ui_manual",
                    reason="Diinput manual oleh pengguna lewat UI",
                )

                _invalidate_api_cache()
                self._send_json({
                    "status": "ok",
                    "spotify_id": final_id,
                    "title": sp_title or track_title,
                    "thumbnail_url": sp_thumbnail,
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
            db.reset_all_data(clear_cache=clear_cache)
            _invalidate_api_cache()
            _update_job(False, None, 0, 0, "Database berhasil dikosongkan. Siap mulai dari 0.")
            self._send_json({"status": "ok", "message": "Semua data berhasil direset ke 0."})
            return

        elif path == "/api/delete-playlist":
            db.init_db()
            playlist_ids = payload.get("playlist_ids")
            playlist_id = payload.get("playlist_id")
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
            pl_id = None
            if playlist_id not in (None, "all", "", 0, "0"):
                try:
                    pl_id = int(playlist_id)
                except (ValueError, TypeError):
                    pl_id = None

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
