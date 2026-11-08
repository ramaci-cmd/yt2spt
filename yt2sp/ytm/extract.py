"""Wrapper ytmusicapi untuk ekstrak playlist dan lagu YouTube Music."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ytmusicapi import YTMusic

logger = logging.getLogger(__name__)

_YTM_AUTH_FILE = Path("ytm_auth.json")


def clean_playlist_id(raw_input: str) -> str:
    """Ekstrak ID playlist bersih dari string atau link URL YouTube/YouTube Music."""
    s = raw_input.strip()
    if not s:
        return ""
    if "list=" in s:
        import urllib.parse
        parsed = urllib.parse.urlparse(s)
        qs = urllib.parse.parse_qs(parsed.query)
        if "list" in qs and qs["list"]:
            return qs["list"][0]
        import re
        match = re.search(r"[?&]list=([a-zA-Z0-9_-]+)", s)
        if match:
            return match.group(1)
    return s


def get_ytm(auth_path: Path | None = None) -> YTMusic:
    """Return YTMusic instance. Pakai auth jika tersedia."""
    p = auth_path or _YTM_AUTH_FILE
    if p.exists():
        return YTMusic(str(p))
    return YTMusic()  # unauthenticated – hanya playlist publik


def get_library_playlists(ytm: YTMusic) -> list[dict]:
    """Ambil semua playlist library user (butuh auth)."""
    playlists = ytm.get_library_playlists(limit=100)
    return playlists or []


def get_playlist_items(ytm: YTMusic, playlist_id: str) -> list[dict]:
    """Ambil semua lagu dalam playlist (handle pagination otomatis)."""
    clean_id = clean_playlist_id(playlist_id)
    if not clean_id:
        raise ValueError("ID atau Link Playlist tidak valid.")
    data = ytm.get_playlist(clean_id, limit=None)
    return data.get("tracks", [])


class PlaylistResult(tuple):
    """2-tuple (title, tracks) dengan metadata tambahan unavailable_count & total_reported."""
    def __new__(cls, title: str, tracks: list[dict], unavailable_count: int = 0, total_reported: int = 0):
        obj = super().__new__(cls, (title, tracks))
        obj.title = title
        obj.tracks = tracks
        obj.unavailable_count = unavailable_count
        obj.total_reported = total_reported
        return obj


def get_playlist_details(ytm: YTMusic, playlist_id: str) -> PlaylistResult:
    """Ambil judul dan semua lagu dalam playlist, serta hitung lagu yang disembunyikan/dihapus oleh YouTube."""
    clean_id = clean_playlist_id(playlist_id)
    if not clean_id:
        raise ValueError("ID atau Link Playlist tidak valid.")
    data = ytm.get_playlist(clean_id, limit=None)
    title = data.get("title") or f"Playlist {clean_id[:12]}"
    tracks = data.get("tracks") or []

    raw_count = data.get("trackCount")
    try:
        total_reported = int(raw_count) if raw_count is not None else len(tracks)
    except (ValueError, TypeError):
        total_reported = len(tracks)

    unavailable_count = max(0, total_reported - len(tracks))
    return PlaylistResult(title, tracks, unavailable_count=unavailable_count, total_reported=total_reported)



def parse_track(raw: dict) -> dict[str, Any] | None:
    """
    Parsing satu track dari ytmusicapi ke format internal.
    Return None jika track tidak valid (video non-musik, dll).
    """
    video_id = raw.get("videoId")
    if not video_id:
        return None

    title = (raw.get("title") or "").strip()
    artists: list[str] = [a.get("name", "") for a in (raw.get("artists") or []) if a and a.get("name")]
    album_data = raw.get("album") or {}
    album = (album_data.get("name") if isinstance(album_data, dict) else "") or ""
    duration_ms = _parse_duration_ms(raw.get("duration") or "")
    video_type = raw.get("videoType") or "MUSIC_VIDEO_TYPE_ATV"

    return {
        "video_id": video_id,
        "title": title,
        "artists": artists,
        "album": album,
        "duration_ms": duration_ms,
        "video_type": video_type,
    }


def _parse_duration_ms(duration_str: str) -> int:
    """Konversi '3:45' atau '1:03:45' ke milidetik."""
    if not duration_str:
        return 0
    parts = duration_str.strip().split(":")
    try:
        if len(parts) == 2:
            m, s = parts
            return (int(m) * 60 + int(s)) * 1000
        elif len(parts) == 3:
            h, m, s = parts
            return (int(h) * 3600 + int(m) * 60 + int(s)) * 1000
    except ValueError:
        pass
    return 0


def get_liked_songs(ytm: YTMusic) -> list[dict]:
    """Ambil Liked Songs sebagai playlist virtual (membutuhkan file ytm_auth.json)."""
    if not _YTM_AUTH_FILE.exists():
        raise RuntimeError(
            "Fitur 'Liked Songs Akun' memerlukan autentikasi login YouTube Music (file ytm_auth.json belum ada).\n"
            "Solusi mudah: Jika Anda sudah punya link playlist Liked Music Anda, silakan paste link tersebut di kotak 'Link Playlist' dan klik 'Tarik Playlist'!"
        )
    try:
        data = ytm.get_liked_songs(limit=5000)
        return data.get("tracks", [])
    except Exception as exc:
        logger.warning("Gagal ambil Liked Songs: %s", exc)
        raise RuntimeError(f"Gagal mengambil Liked Songs: {exc}")
