"""Spotify Playlist Extractor menggunakan spotifyscraper (100% Gratis, Tanpa Spotify Dev Account)."""
from __future__ import annotations

import logging
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

from spotify_scraper import SpotifyClient

logger = logging.getLogger(__name__)

# Regex untuk mengenali Spotify playlist ID (22 karakter base62 alfanumerik)
_SP_PLAYLIST_RE = re.compile(r"([a-zA-Z0-9]{22})")


def clean_spotify_playlist_id(raw_input: str) -> str:
    """
    Ekstrak ID playlist Spotify bersih (22 karakter) dari:
    - URL Web: https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=...
    - URI Spotify: spotify:playlist:37i9dQZF1DXcBWIGoYBM5M
    - Bare ID: 37i9dQZF1DXcBWIGoYBM5M
    """
    s = raw_input.strip()
    if not s:
        return ""

    # Jangan parse jika jelas merupakan link atau ID YouTube
    if "youtube.com" in s or "youtu.be" in s or s.startswith("PL") or s.startswith("RD") or s.startswith("OLAK"):
        return ""

    # Cek format URL: open.spotify.com/playlist/<id> atau open.spotify.com/intl-xx/playlist/<id>
    if "spotify.com" in s and "/playlist/" in s:
        part = s.split("/playlist/")[1]
        clean_id = part.split("?")[0].split("/")[0].strip()
        m = _SP_PLAYLIST_RE.match(clean_id)
        if m:
            return m.group(1)

    # Cek format URI: spotify:playlist:<id>
    if s.startswith("spotify:playlist:"):
        clean_id = s.split("spotify:playlist:")[1].strip()
        m = _SP_PLAYLIST_RE.match(clean_id)
        if m:
            return m.group(1)

    # Cek jika input langsung berupa 22 karakter base62 utuh
    if _SP_PLAYLIST_RE.fullmatch(s):
        return s

    return ""


@dataclass
class SpotifyTrackItem:
    track_id: str
    title: str
    artists: list[str]
    album: str
    duration_ms: int
    isrc: str | None = None
    thumbnail_url: str | None = None
    preview_url: str | None = None
    uri: str = ""
    is_playable: bool = True

    @property
    def id(self) -> str:
        return self.track_id

    @property
    def video_id(self) -> str:
        return self.track_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "video_id": self.track_id,  # Kompatibel dengan primary key tabel tracks
            "track_id": self.track_id,
            "title": self.title,
            "artists": self.artists,
            "album": self.album,
            "duration_ms": self.duration_ms,
            "isrc": self.isrc,
            "thumbnail_url": self.thumbnail_url,
            "preview_url": self.preview_url,
            "uri": self.uri or f"spotify:track:{self.track_id}",
            "video_type": "SPOTIFY_TRACK",
        }


@dataclass
class SpotifyPlaylistResult:
    id: str
    title: str
    description: str
    owner: str
    track_count: int
    unavailable_count: int
    thumbnail_url: str | None
    tracks: list[SpotifyTrackItem] = field(default_factory=list)

    @property
    def playlist_id(self) -> str:
        return self.id

    @property
    def cover_image(self) -> str | None:
        return self.thumbnail_url


def extract_spotify_playlist(
    playlist_id_or_url: str,
    *,
    max_tracks: int | None = None,
    client: SpotifyClient | None = None,
) -> SpotifyPlaylistResult:
    """
    Ekstrak metadata playlist dan daftar lagu dari Spotify publik.
    Tidak memerlukan akun Spotify Developer atau token OAuth.
    """
    clean_id = clean_spotify_playlist_id(playlist_id_or_url)
    if not clean_id:
        raise ValueError("Link atau ID Playlist Spotify tidak valid.")

    sp = client or SpotifyClient()
    try:
        playlist = sp.get_playlist(clean_id, max_tracks=max_tracks)
    except Exception as exc:
        logger.error("Gagal mengambil playlist Spotify %s: %s", clean_id, exc)
        raise RuntimeError(f"Gagal memuat playlist Spotify: {exc}")

    title = playlist.name or f"Playlist {clean_id[:10]}"
    description = playlist.description or ""
    owner = (getattr(playlist.owner, "name", None) or getattr(playlist.owner, "display_name", None) or "") if playlist.owner else ""
    
    # Ambil cover playlist jika ada
    thumbnail_url = None
    if playlist.images and len(playlist.images) > 0:
        img0 = playlist.images[0]
        thumbnail_url = getattr(img0, "url", None) or (img0 if isinstance(img0, str) else None)

    raw_items = playlist.tracks or []
    extracted_tracks: list[SpotifyTrackItem] = []
    unavailable_count = 0

    for idx, item in enumerate(raw_items):
        track = item.track if hasattr(item, "track") and item.track else item
        if not track or not getattr(track, "id", None):
            unavailable_count += 1
            continue

        t_id = track.id
        t_name = (track.name or "").strip() or "Untitled Track"
        
        # Ekstrak musisi
        t_artists = [a.name for a in (track.artists or []) if a and getattr(a, "name", None)]
        if not t_artists:
            t_artists = ["Unknown Artist"]

        # Ekstrak album
        t_album = ""
        if hasattr(track, "album") and track.album:
            t_album = track.album.name or ""

        # Ekstrak cover track
        t_thumb = None
        if hasattr(track, "images") and track.images:
            t_thumb = track.images[0].url

        t_dur = getattr(track, "duration_ms", 0) or 0
        t_isrc = getattr(track, "isrc", None)
        t_prev = getattr(track, "preview_url", None)
        t_uri = getattr(track, "uri", None) or f"spotify:track:{t_id}"
        t_playable = getattr(track, "playable", True)

        if not t_playable:
            unavailable_count += 1

        extracted_tracks.append(
            SpotifyTrackItem(
                track_id=t_id,
                title=t_name,
                artists=t_artists,
                album=t_album,
                duration_ms=t_dur,
                isrc=t_isrc,
                thumbnail_url=t_thumb,
                preview_url=t_prev,
                uri=t_uri,
                is_playable=t_playable,
            )
        )

    total_reported = getattr(playlist, "total_tracks", len(extracted_tracks)) or len(extracted_tracks)
    # Unavailable jika total yang dilaporkan lebih banyak dari tracks yang dapat diakses
    if total_reported > len(extracted_tracks):
        unavailable_count = max(unavailable_count, total_reported - len(extracted_tracks))

    return SpotifyPlaylistResult(
        id=clean_id,
        title=title,
        description=description,
        owner=owner,
        track_count=len(extracted_tracks),
        unavailable_count=unavailable_count,
        thumbnail_url=thumbnail_url,
        tracks=extracted_tracks,
    )
