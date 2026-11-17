"""Resolver Destinasi: Cari lagu di YouTube Music menggunakan ytmusicapi (100% Gratis, Tanpa Kuota Dev).

Flow:
1. Build query dari judul Spotify + artis utama Spotify
2. Cari top-N hasil di YouTube Music (filter='songs' dengan fallback ke videos)
3. Return kandidat terstruktur dengan video_id, title, artist, album, duration_ms, thumbnail_url, url
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

from ytmusicapi import YTMusic

logger = logging.getLogger(__name__)

# Singleton YTMusic instance (thread-safe)
_ytm_client: YTMusic | None = None
_ytm_lock = threading.Lock()


def get_ytm_client() -> YTMusic:
    global _ytm_client
    with _ytm_lock:
        if _ytm_client is None:
            _ytm_client = YTMusic()
        return _ytm_client


def reset_ytm_client() -> None:
    global _ytm_client
    with _ytm_lock:
        _ytm_client = None


@dataclass
class YTMTrackCandidate:
    video_id: str
    title: str
    artist: str
    artists: list[str]
    album: str
    duration_ms: int
    video_type: str
    thumbnail_url: str | None = None
    url: str = ""

    def __post_init__(self):
        if not self.url and self.video_id:
            self.url = f"https://music.youtube.com/watch?v={self.video_id}"


def _parse_duration_to_ms(duration_val: Any) -> int:
    """Konversi duration_seconds (int) atau string '3:45' / '1:05:20' ke milidetik."""
    if isinstance(duration_val, (int, float)) and duration_val > 0:
        return int(duration_val * 1000)

    if not duration_val or not isinstance(duration_val, str):
        return 0

    parts = duration_val.strip().split(":")
    try:
        if len(parts) == 2:
            return (int(parts[0]) * 60 + int(parts[1])) * 1000
        elif len(parts) == 3:
            return (int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])) * 1000
    except (ValueError, TypeError):
        pass
    return 0


def search_ytm_tracks(
    title: str,
    artists: list[str],
    *,
    top_n: int = 5,
    max_retries: int = 3,
    ytm: YTMusic | None = None,
) -> list[YTMTrackCandidate]:
    """
    Cari lagu di YouTube Music berdasarkan metadata Spotify.
    Return list kandidat YTMTrackCandidate.
    """
    primary_artist = artists[0] if artists else ""
    query = f"{title} {primary_artist}".strip()
    client = ytm or get_ytm_client()

    for attempt in range(max_retries):
        try:
            # 1. Cari dengan filter='songs' (rekaman studio resmi)
            results = client.search(query, filter="songs", limit=max(top_n, 5))
            
            # 2. Jika songs kosong, fallback ke pencarian umum (videos/music)
            if not results:
                results = client.search(query, filter="videos", limit=max(top_n, 5))

            candidates: list[YTMTrackCandidate] = []
            seen_ids: set[str] = set()

            for item in results or []:
                vid = item.get("videoId")
                if not vid or vid in seen_ids:
                    continue
                seen_ids.add(vid)

                t_name = item.get("title") or ""
                item_artists = [a.get("name", "") for a in (item.get("artists") or []) if a and a.get("name")]
                primary_a = item_artists[0] if item_artists else (item.get("author") or "")

                album_info = item.get("album") or {}
                album_name = (album_info.get("name") if isinstance(album_info, dict) else "") or ""

                # Durasi
                dur_ms = 0
                if "duration_seconds" in item and item["duration_seconds"]:
                    dur_ms = int(item["duration_seconds"]) * 1000
                elif "duration" in item and item["duration"]:
                    dur_ms = _parse_duration_to_ms(item["duration"])

                vtype = item.get("videoType") or "MUSIC_VIDEO_TYPE_ATV"

                # Thumbnail
                thumb_url = None
                thumbs = item.get("thumbnails") or []
                if thumbs:
                    thumb_url = thumbs[-1].get("url")
                if not thumb_url and vid:
                    thumb_url = f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg"

                candidates.append(
                    YTMTrackCandidate(
                        video_id=vid,
                        title=t_name,
                        artist=primary_a,
                        artists=item_artists or ([primary_a] if primary_a else []),
                        album=album_name,
                        duration_ms=dur_ms,
                        video_type=vtype,
                        thumbnail_url=thumb_url,
                        url=f"https://music.youtube.com/watch?v={vid}",
                    )
                )

                if len(candidates) >= top_n:
                    break

            return candidates

        except Exception as exc:
            logger.warning(
                "YTM search attempt %d/%d gagal untuk '%s': %s",
                attempt + 1,
                max_retries,
                query,
                exc,
            )
            if attempt < max_retries - 1:
                time.sleep(1.5 ** attempt)
            else:
                reset_ytm_client()

    return []


def find_ytm_alternative_versions(
    title: str,
    artists: list[str],
    *,
    max_results: int = 8,
    ytm: YTMusic | None = None,
) -> list[dict[str, Any]]:
    """
    Mencari variasi lagu alternatif di YouTube Music:
    - Cover oleh penyanyi berbeda
    - Versi aransemen lain (Acoustic / Live / Remix)
    - Hasil kemiripan judul tinggi lainnya
    """
    from rapidfuzz import fuzz
    from yt2sp.match.normalize import normalize_artist, normalize_title

    client = ytm or get_ytm_client()
    clean_title = normalize_title(title)
    primary_artist = artists[0] if artists else ""
    norm_orig_artist = normalize_artist(primary_artist)

    queries = [clean_title, f"{clean_title} cover", f"{clean_title} acoustic"]
    seen_ids: set[str] = set()
    alternatives: list[dict[str, Any]] = []

    for q in queries:
        try:
            res = client.search(q, filter="songs", limit=6)
            if not res:
                res = client.search(q, filter="videos", limit=6)

            for item in res or []:
                vid = item.get("videoId")
                if not vid or vid in seen_ids:
                    continue
                seen_ids.add(vid)

                t_name = item.get("title") or ""
                item_artists = [a.get("name", "") for a in (item.get("artists") or []) if a and a.get("name")]
                t_artist = item_artists[0] if item_artists else (item.get("author") or "Unknown")

                norm_cand_artist = normalize_artist(t_artist)
                norm_cand_title = normalize_title(t_name)

                title_sim = fuzz.token_set_ratio(clean_title, norm_cand_title)
                art_sim = fuzz.token_set_ratio(norm_orig_artist, norm_cand_artist)

                # Filter hanya yang judulnya mirip (>= 50%)
                if title_sim < 50:
                    continue

                dur_s = 0
                if "duration_seconds" in item and item["duration_seconds"]:
                    dur_s = int(item["duration_seconds"])
                elif "duration" in item and item["duration"]:
                    dur_s = round(_parse_duration_to_ms(item["duration"]) / 1000)

                # Klasifikasi tag
                if title_sim >= 80 and art_sim < 50:
                    tag = "Penyanyi Berbeda (Cover)"
                    badge_color = "amber"
                    desc = f"Judul sama, dibawakan oleh {t_artist}"
                elif any(m in t_name.lower() for m in ["remix", "acoustic", "live", "cover", "karaoke"]):
                    tag = "Versi Alternatif (Cover/Remix/Live)"
                    badge_color = "purple"
                    desc = f"Versi aransemen lain oleh {t_artist}"
                else:
                    tag = "Kemiripan Judul & Musisi"
                    badge_color = "blue"
                    desc = f"Lagu serupa oleh {t_artist}"

                thumb = None
                thumbs = item.get("thumbnails") or []
                if thumbs:
                    thumb = thumbs[-1].get("url")
                if not thumb and vid:
                    thumb = f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg"

                alternatives.append({
                    "video_id": vid,
                    "spotify_id": vid,  # kompatibilitas field UI
                    "uri": f"https://music.youtube.com/watch?v={vid}",
                    "title": t_name,
                    "artist": t_artist,
                    "duration_s": dur_s,
                    "tag": tag,
                    "badge_color": badge_color,
                    "desc": desc,
                    "title_sim": round(title_sim),
                    "art_sim": round(art_sim),
                    "thumbnail_url": thumb,
                })

                if len(alternatives) >= max_results:
                    break

        except Exception as exc:
            logger.debug("Error searching YTM alternatives for '%s': %s", q, exc)

        if len(alternatives) >= max_results:
            break

    # Urutkan: Cover/Penyanyi berbeda dulu, lalu kemiripan judul tertinggi
    alternatives.sort(key=lambda x: (x["tag"].startswith("Penyanyi"), x["title_sim"]), reverse=True)
    return alternatives[:max_results]
