"""Resolver T2 fallback: Deezer search API (gratis, tanpa API key).

Flow:
1. Search Deezer dengan query judul + artis
2. Ambil ISRC dari detail track
3. Lookup ISRC di MusicBrainz → dapat Spotify ID langsung
"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "yt2sp/1.0 (https://github.com/local/yt2sp)"}
_MB_HEADERS = {"User-Agent": "yt2sp/1.0 (contact@example.com)"}


@dataclass
class DeezerCandidate:
    deezer_id: int
    title: str
    artist: str
    duration_ms: int
    isrc: str | None
    spotify_ids: list[str]  # dari MusicBrainz


def _get_json(url: str, headers: dict, timeout: int = 10) -> dict | None:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        logger.debug("HTTP %d untuk %s", e.code, url)
        return None
    except Exception as e:
        logger.debug("Error fetch %s: %s", url, e)
        return None


def search_deezer(
    title: str,
    artists: list[str],
    *,
    top_n: int = 3,
) -> list[DeezerCandidate]:
    """Cari di Deezer lalu enrich dengan ISRC + Spotify ID dari MusicBrainz."""
    primary = artists[0] if artists else ""
    query = urllib.parse.quote(f"{title} {primary}".strip())
    url = f"https://api.deezer.com/search?q={query}&limit={top_n}"

    data = _get_json(url, _HEADERS)
    if not data or not data.get("data"):
        return []

    candidates: list[DeezerCandidate] = []
    for item in data["data"][:top_n]:
        track_id = item["id"]
        track_detail = _get_json(f"https://api.deezer.com/track/{track_id}", _HEADERS)
        isrc = track_detail.get("isrc") if track_detail else None
        duration_ms = item.get("duration", 0) * 1000

        # Lookup Spotify ID jika ada ISRC (MusicBrainz + Spotify search fallback)
        spotify_ids: list[str] = []
        if isrc:
            spotify_ids = _resolve_spotify_from_isrc(isrc)
            time.sleep(0.3)

        candidates.append(
            DeezerCandidate(
                deezer_id=track_id,
                title=item.get("title", ""),
                artist=item.get("artist", {}).get("name", ""),
                duration_ms=duration_ms,
                isrc=isrc,
                spotify_ids=spotify_ids,
            )
        )
    return candidates


def _resolve_spotify_from_isrc(isrc: str) -> list[str]:
    """Cari Spotify track ID dari ISRC via MusicBrainz lalu fallback ke Spotify search."""
    # 1. MusicBrainz ISRC endpoint
    ids = _mb_spotify_from_isrc(isrc)
    if ids:
        return ids

    # 2. Spotify native ISRC search fallback
    try:
        from yt2sp.resolve.spotify_resolver import _get_client
        client = _get_client()
        res = client.search(f"isrc:{isrc}", types=("track",))
        for t in (res.tracks or []):
            if t.id and t.id not in ids:
                ids.append(t.id)
    except Exception as exc:
        logger.debug("Spotify isrc query error for %s: %s", isrc, exc)
    return ids


def _mb_spotify_from_isrc(isrc: str) -> list[str]:
    """Query MusicBrainz ISRC endpoint → return list Spotify track IDs."""
    url = f"https://musicbrainz.org/ws/2/isrc/{isrc}?fmt=json&inc=url-rels"
    data = _get_json(url, _MB_HEADERS, timeout=15)
    if not data:
        return []
    ids: list[str] = []
    for rec in data.get("recordings", []):
        for rel in rec.get("relations", []):
            resource = rel.get("url", {}).get("resource", "")
            if "open.spotify.com/track/" in resource:
                sp_id = resource.split("open.spotify.com/track/")[1].split("?")[0].strip()
                if sp_id and sp_id not in ids:
                    ids.append(sp_id)
    return ids
