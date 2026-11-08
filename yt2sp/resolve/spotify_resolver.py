"""Resolver T1: cari lagu di Spotify menggunakan spotifyscraper (tanpa API key).

Flow:
1. Build query dari judul + artis utama
2. Cari top-N hasil di Spotify
3. Return kandidat dengan title, artist, uri, duration_ms
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from spotify_scraper import SpotifyClient  # type: ignore

logger = logging.getLogger(__name__)

# Singleton client – reuse satu session (thread-safe)
_client: SpotifyClient | None = None
_client_lock = threading.Lock()


def _get_client() -> SpotifyClient:
    global _client
    with _client_lock:
        if _client is None:
            _client = SpotifyClient()
        return _client


def _reset_client() -> None:
    global _client
    with _client_lock:
        _client = None


@dataclass
class SpotifyCandidate:
    spotify_id: str
    uri: str
    title: str
    artist: str
    duration_ms: int


def search_spotify(
    title: str,
    artists: list[str],
    *,
    top_n: int = 5,
    max_retries: int = 3,
) -> list[SpotifyCandidate]:
    """
    Cari lagu di Spotify. Return list kandidat (bisa kosong).
    Retry otomatis jika terjadi error jaringan.
    """
    # Build query: "Title Artist1"
    primary_artist = artists[0] if artists else ""
    query = f"{title} {primary_artist}".strip()

    for attempt in range(max_retries):
        try:
            client = _get_client()
            results = client.search(query, types=("track",))
            candidates: list[SpotifyCandidate] = []
            for track in (results.tracks or [])[:top_n]:
                track_artist = (
                    track.artists[0].name if track.artists else ""
                )
                candidates.append(
                    SpotifyCandidate(
                        spotify_id=track.id,
                        uri=track.uri,
                        title=track.name or "",
                        artist=track_artist,
                        duration_ms=track.duration_ms or 0,
                    )
                )
            return candidates
        except Exception as exc:
            logger.warning(
                "Spotify search attempt %d/%d gagal untuk '%s': %s",
                attempt + 1,
                max_retries,
                query,
                exc,
            )
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                # Reset client supaya next call buat session baru (thread-safe)
                _reset_client()
    return []


def find_alternative_versions(
    title: str,
    artists: list[str],
    *,
    max_results: int = 8,
) -> list[dict]:
    """
    Mencari lagu alternatif di Spotify ketika versi aslinya tidak ditemukan atau berbeda:
    - Judul sama persis tapi penyanyi berbeda (Cover / Penyanyi Lain)
    - Versi aransemen berbeda (Acoustic / Live / Remix)
    - Lagu dengan kemiripan judul tinggi
    """
    from rapidfuzz import fuzz
    from yt2sp.match.normalize import normalize_artist, normalize_title

    client = _get_client()
    clean_title = normalize_title(title)
    primary_artist = artists[0] if artists else ""
    norm_orig_artist = normalize_artist(primary_artist)

    queries = [clean_title, f"{clean_title} cover"]
    seen_ids: set[str] = set()
    alternatives: list[dict] = []

    for q in queries:
        try:
            res = client.search(q, types=("track",))
            for t in (res.tracks or []):
                if not t.id or t.id in seen_ids:
                    continue
                seen_ids.add(t.id)

                t_artist = t.artists[0].name if t.artists else "Unknown"
                norm_cand_artist = normalize_artist(t_artist)
                norm_cand_title = normalize_title(t.name or "")

                title_sim = fuzz.token_set_ratio(clean_title, norm_cand_title)
                art_sim = fuzz.token_set_ratio(norm_orig_artist, norm_cand_artist)

                # Filter hanya yang judulnya mirip (>= 60%)
                if title_sim < 60:
                    continue

                # Klasifikasi tipe alternatif
                if title_sim >= 80 and art_sim < 50:
                    tag = "Penyanyi Berbeda (Cover)"
                    badge_color = "amber"
                    desc = f"Judul sama, dinyanyikan oleh {t_artist}"
                elif any(m in (t.name or "").lower() for m in ["remix", "acoustic", "live", "cover"]):
                    tag = "Versi Alternatif (Cover/Remix/Live)"
                    badge_color = "purple"
                    desc = f"Versi aransemen lain oleh {t_artist}"
                else:
                    tag = "Kemiripan Judul & Musisi"
                    badge_color = "blue"
                    desc = f"Lagu serupa oleh {t_artist}"

                alternatives.append({
                    "spotify_id": t.id,
                    "uri": t.uri or f"spotify:track:{t.id}",
                    "title": t.name or "",
                    "artist": t_artist,
                    "duration_s": round((t.duration_ms or 0) / 1000),
                    "tag": tag,
                    "badge_color": badge_color,
                    "desc": desc,
                    "title_sim": round(title_sim),
                    "art_sim": round(art_sim),
                })
                if len(alternatives) >= max_results:
                    break
        except Exception as exc:
            logger.debug("Error finding alternatives for '%s': %s", q, exc)

        if len(alternatives) >= max_results:
            break

    # Urutkan berdasarkan prioritas: Penyanyi Berbeda / Cover dulu, lalu title_sim tertinggi
    alternatives.sort(key=lambda x: (x["tag"].startswith("Penyanyi"), x["title_sim"]), reverse=True)
    return alternatives[:max_results]

