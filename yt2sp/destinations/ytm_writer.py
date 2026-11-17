"""YouTube Music Playlist Writer – Membuat playlist riil di akun pengguna via ytmusicapi."""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ytmusicapi import YTMusic

logger = logging.getLogger(__name__)

DEFAULT_YTM_AUTH = Path("ytm_auth.json")


def normalize_browser_headers(raw: str) -> str:
    """
    Normalisasi input cURL (bash) atau Raw Headers dari Developer Tools
    menjadi format "Key: Value" baris per baris yang dipahami oleh ytmusicapi.setup.
    Otomatis mengekstrak flag -H dan flag -b / --cookie dari command cURL,
    serta menyisipkan 'x-goog-authuser: 0' jika belum ada.
    """
    if not raw or not raw.strip():
        return ""

    lines: list[str] = []
    # 1. Match -H '...' or -H "..."
    h_matches = re.findall(r"(?:-H|--header)\s+[\"']([^\"']+)[\"']", raw)
    lines.extend(h_matches)

    # 2. Match -b '...' or --cookie '...'
    b_matches = re.findall(r"(?:-b|--cookie)\s+[\"']([^\"']+)[\"']", raw)
    for b in b_matches:
        lines.append(f"cookie: {b}")

    if not lines:
        for line in raw.splitlines():
            line = line.strip()
            m = re.match(r"(?:-H|--header)\s+[\"']?([^\"']+)[\"']?", line)
            mb = re.match(r"(?:-b|--cookie)\s+[\"']?([^\"']+)[\"']?", line)
            if m:
                lines.append(m.group(1).rstrip(";\\ "))
            elif mb:
                lines.append(f"cookie: {mb.group(1).rstrip(';\\ ')}")
            elif line:
                lines.append(line)

    cleaned: list[str] = []
    has_authuser = False
    for line in lines:
        if line.startswith("-H ") or line.startswith("--header "):
            line = re.sub(r"^(?:-H|--header)\s+[\"']?", "", line).rstrip("\"'\\ ")
        if line.startswith("-b ") or line.startswith("--cookie "):
            val = re.sub(r"^(?:-b|--cookie)\s+[\"']?", "", line).rstrip("\"'\\ ")
            line = f"cookie: {val}"

        if ": " in line:
            k, v = line.split(": ", 1)
            k_clean = k.strip().strip("\"'").lower()
            if k_clean == "x-goog-authuser":
                has_authuser = True
            cleaned.append(f"{k_clean}: {v.strip().rstrip(';')}")
        elif ":" in line:
            k, v = line.split(":", 1)
            k_clean = k.strip().strip("\"'").lower()
            if k_clean == "x-goog-authuser":
                has_authuser = True
            cleaned.append(f"{k_clean}: {v.strip().rstrip(';')}")

    if not has_authuser:
        cleaned.append("x-goog-authuser: 0")

    return "\n".join(cleaned)


@dataclass
class YTMExportResult:
    playlist_id: str
    playlist_url: str
    title: str
    total_requested: int
    total_added: int
    failed_ids: list[str] = field(default_factory=list)
    status: str = "success"  # "success" | "partial" | "failed"
    error_message: str | None = None


class AuthResult(tuple):
    """Tuple (bool, str | None) yang juga dapat dievaluasi langsung sebagai boolean."""
    def __new__(cls, ok: bool, err: str | None = None):
        return super().__new__(cls, (ok, err))

    @property
    def ok(self) -> bool:
        return self[0]

    @property
    def err(self) -> str | None:
        return self[1]

    def __bool__(self) -> bool:
        return self[0]


def check_ytm_auth(auth_path: Path | str | None = None) -> AuthResult:
    """Periksa apakah file autentikasi YouTube Music tersedia di filesystem."""
    candidates = [
        Path(auth_path) if auth_path else None,
        Path("ytm_auth.json"),
        Path("oauth.json"),
        Path("headers_auth.json"),
    ]
    for p in candidates:
        if p and p.exists() and p.is_file() and p.stat().st_size > 10:
            return AuthResult(True, None)
    return AuthResult(False, "File autentikasi ('ytm_auth.json' atau 'oauth.json') tidak ditemukan.")


def get_authenticated_ytm(auth_path: Path | str | None = None) -> YTMusic:
    """
    Return instance YTMusic terautentikasi.
    Mendukung ytm_auth.json, oauth.json, atau headers_auth.json.
    """
    candidates = [
        Path(auth_path) if auth_path else None,
        Path("ytm_auth.json"),
        Path("oauth.json"),
        Path("headers_auth.json"),
    ]
    for p in candidates:
        if p and p.exists() and p.is_file() and p.stat().st_size > 10:
            return YTMusic(str(p))
    raise RuntimeError(
        "File autentikasi YouTube Music ('ytm_auth.json' atau 'oauth.json') tidak ditemukan.\n"
        "Silakan lakukan setup autentikasi terlebih dahulu:\n"
        "1. Di Web UI: klik tombol 'Setup Akun YTM' dan paste cURL browser yang valid (dengan Cookie).\n"
        "2. Di Terminal: jalankan perintah 'python -m yt2sp.cli auth-ytm'."
    )


def create_and_populate_ytm_playlist(
    title: str,
    video_ids: list[str] | None = None,
    *,
    track_ids: list[str] | None = None,
    description: str = "Migrated from Spotify using Spotify2YTM",
    privacy_status: str = "PRIVATE",
    chunk_size: int = 50,
    auth_path: Path | str | None = None,
    on_progress: Callable[[int, int, str], None] | None = None,
    ytm_client: YTMusic | None = None,
) -> YTMExportResult:
    """
    Membuat playlist baru di YouTube Music dan menambahkan lagu-lagu yang telah dicocokkan.
    
    Args:
        title: Nama playlist yang akan dibuat
        video_ids: List YouTube video IDs dalam urutan yang tepat
        track_ids: Alias untuk video_ids (kompatibilitas dengan pemanggil UI dan CLI)
        description: Deskripsi playlist
        privacy_status: 'PRIVATE', 'UNLISTED', atau 'PUBLIC'
        chunk_size: Ukuran batch penambahan lagu (default: 50)
        auth_path: Path file kredensial ytm_auth.json
        on_progress: Callback progress (current, total, status_message)
        ytm_client: Instance YTMusic terinjeksi (untuk testing)
    """
    raw_ids = video_ids if video_ids is not None else (track_ids or [])
    if not raw_ids:
        raise ValueError("Daftar lagu (video_ids / track_ids) kosong. Tidak ada lagu untuk dimasukkan ke playlist.")

    ytm = ytm_client or get_authenticated_ytm(auth_path)

    # Filter out ID kosong atau invalid
    valid_ids: list[str] = [vid.strip() for vid in raw_ids if vid and isinstance(vid, str) and len(vid.strip()) >= 5]
    if not valid_ids:
        raise ValueError("Tidak ada video ID YouTube yang valid untuk ditambahkan.")

    # 1. Buat playlist kosong di YouTube Music
    logger.info("Membuat playlist YouTube Music: '%s' (privacy: %s)", title, privacy_status)
    try:
        raw_res = ytm.create_playlist(
            title=title,
            description=description,
            privacy_status=privacy_status,
        )
    except Exception as exc:
        logger.error("Gagal membuat playlist YouTube Music '%s': %s", title, exc)
        return YTMExportResult(
            playlist_id="",
            playlist_url="",
            title=title,
            total_requested=len(valid_ids),
            total_added=0,
            failed_ids=valid_ids,
            status="failed",
            error_message=f"Gagal membuat playlist: {exc}",
        )

    # Ambil ID playlist yang dikembalikan
    if isinstance(raw_res, str):
        created_pl_id = raw_res
    elif isinstance(raw_res, dict):
        created_pl_id = raw_res.get("id") or raw_res.get("playlistId") or ""
    else:
        created_pl_id = str(raw_res)

    if not created_pl_id or "error" in created_pl_id.lower():
        err_msg = f"Respon pembuatan playlist tidak valid: {raw_res}"
        logger.error(err_msg)
        return YTMExportResult(
            playlist_id="",
            playlist_url="",
            title=title,
            total_requested=len(valid_ids),
            total_added=0,
            failed_ids=valid_ids,
            status="failed",
            error_message=err_msg,
        )

    # Format URL bersih (jika diawali VL, hilangkan prefix VL untuk link publik)
    clean_url_id = created_pl_id[2:] if created_pl_id.startswith("VL") else created_pl_id
    playlist_url = f"https://music.youtube.com/playlist?list={clean_url_id}"

    # 2. Masukkan lagu ke dalam playlist secara bertahap (chunking per 50 lagu)
    total_tracks = len(valid_ids)
    added_count = 0
    failed_ids: list[str] = []

    for i in range(0, total_tracks, chunk_size):
        chunk = valid_ids[i : i + chunk_size]
        try:
            ytm.add_playlist_items(
                playlistId=created_pl_id,
                videoIds=chunk,
                duplicates=True,
            )
            added_count += len(chunk)
            msg = f"Menambahkan lagu ({added_count}/{total_tracks}) ke playlist..."
            if on_progress:
                on_progress(added_count, total_tracks, msg)
            # Jeda kecil antar-chunk untuk stabilitas
            time.sleep(0.3)
        except Exception as exc:
            logger.warning("Gagal menambahkan chunk lagu %d..%d: %s", i, i + len(chunk), exc)
            # Retry item per item jika chunk gagal
            for vid in chunk:
                try:
                    ytm.add_playlist_items(playlistId=created_pl_id, videoIds=[vid], duplicates=True)
                    added_count += 1
                except Exception as ind_exc:
                    logger.debug("Gagal menambahkan lagu %s: %s", vid, ind_exc)
                    failed_ids.append(vid)

    status = "success" if not failed_ids else ("partial" if added_count > 0 else "failed")
    return YTMExportResult(
        playlist_id=created_pl_id,
        playlist_url=playlist_url,
        title=title,
        total_requested=total_tracks,
        total_added=added_count,
        failed_ids=failed_ids,
        status=status,
    )
