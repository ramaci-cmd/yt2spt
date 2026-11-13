"""Pipeline resolve utama: ambil pending tracks, search Spotify, score, simpan."""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Callable

from yt2sp.match.score import classify, compute_score
from yt2sp.resolve.deezer_resolver import search_deezer
from yt2sp.resolve.genre import fetch_genre
from yt2sp.resolve.rate_limiter import RateLimiter, backoff_sleep
from yt2sp.resolve.spotify_resolver import SpotifyCandidate, search_spotify
from yt2sp.store import db

logger = logging.getLogger(__name__)


def run_resolve(
    *,
    limit: int | None = None,
    playlist_id: int | None = None,
    rate_per_minute: float = 30.0,
    auto_threshold: float = 0.85,
    review_threshold: float = 0.60,
    title_weight: float = 0.6,
    artist_weight: float = 0.4,
    duration_tolerance: float = 0.10,
    on_progress: Callable[[str, str, float], None] | None = None,
    stop_event: threading.Event | None = None,
) -> dict:
    """
    Jalankan resolver T1 (Spotify search) untuk semua pending tracks.

    on_progress(video_id, status, score) dipanggil tiap lagu selesai.
    Return dict statistik.
    """
    limiter = RateLimiter(rate_per_minute=rate_per_minute)
    pending = db.get_pending_tracks(playlist_id=playlist_id)
    if limit:
        pending = pending[:limit]

    stats = {"processed": 0, "auto": 0, "review": 0, "failed": 0, "skipped": 0}

    for track in pending:
        if stop_event and stop_event.is_set():
            logger.info("run_resolve dihentikan oleh stop_event.")
            break

        video_id = track["video_id"]
        title = track["title"] or ""
        artists: list[str] = json.loads(track["artists"]) if track["artists"] else []
        duration_ms = track["duration_ms"] or 0
        video_type = track["video_type"] or ""

        # Skip lagu non-musik (podcast, video UGC yang bukan lagu)
        if video_type in ("MUSIC_VIDEO_TYPE_UGC",):
            db.set_match(
                video_id,
                spotify_id=None,
                tier="T0",
                score=0.0,
                status="skipped",
                reason=f"video_type={video_type}",
            )
            stats["skipped"] += 1
            if on_progress:
                on_progress(video_id, "skipped", 0.0)
            continue

        # Rate limit
        limiter.acquire()

        try:
            candidates = search_spotify(title, artists, top_n=5)
        except Exception as exc:
            logger.error("Error resolve %s: %s", video_id, exc)
            db.set_match(
                video_id,
                spotify_id=None,
                tier="T1",
                score=0.0,
                status="failed",
                reason=str(exc)[:200],
            )
            stats["failed"] += 1
            if on_progress:
                on_progress(video_id, "failed", 0.0)
            continue

        # Score tiap kandidat T1 (Spotify), ambil yang terbaik
        best_score = -1.0
        best_candidate = None
        best_reason = ""
        best_tier = "T1"

        for cand in candidates:
            score, reason = compute_score(
                title,
                artists,
                cand.title,
                cand.artist,
                duration_ms,
                cand.duration_ms,
                title_weight=title_weight,
                artist_weight=artist_weight,
                duration_tolerance=duration_tolerance,
            )
            if score > best_score:
                best_score = score
                best_candidate = cand
                best_reason = reason

        status = classify(
            best_score,
            auto_threshold=auto_threshold,
            review_threshold=review_threshold,
        )

        # Fallback T2: Deezer ISRC jika T1 gagal atau tidak ada kandidat
        if status == "failed" or not candidates:
            try:
                deezer_cands = search_deezer(title, artists, top_n=2)
                for dcand in deezer_cands:
                    if not dcand.spotify_ids:
                        continue
                    d_score, d_reason = compute_score(
                        title,
                        artists,
                        dcand.title,
                        dcand.artist,
                        duration_ms,
                        dcand.duration_ms,
                        title_weight=title_weight,
                        artist_weight=artist_weight,
                        duration_tolerance=duration_tolerance,
                    )
                    if d_score >= review_threshold and d_score > best_score:
                        best_score = d_score
                        best_tier = "T2_isrc"
                        best_candidate = SpotifyCandidate(
                            spotify_id=dcand.spotify_ids[0],
                            uri=f"spotify:track:{dcand.spotify_ids[0]}",
                            title=dcand.title,
                            artist=dcand.artist,
                            duration_ms=dcand.duration_ms,
                        )
                        best_reason = f"ISRC {dcand.isrc or ''} via Deezer; {d_reason}".strip("; ")
                        status = classify(
                            best_score,
                            auto_threshold=auto_threshold,
                            review_threshold=review_threshold,
                        )
                        break
            except Exception as exc:
                logger.debug("T2 Deezer fallback error for %s: %s", video_id, exc)

        if not best_candidate and status == "failed":
            best_reason = best_reason or "tidak ditemukan di Spotify maupun Deezer"

        db.set_match(
            video_id,
            spotify_id=best_candidate.spotify_id if best_candidate else None,
            tier=best_tier,
            score=max(0.0, best_score),
            status=status,
            result_title=best_candidate.title if best_candidate else "",
            result_artist=best_candidate.artist if best_candidate else "",
            decided_by="auto",
            reason=best_reason,
        )

        # Ambil dan simpan genre lagu dengan validasi multi-sumber
        try:
            track_genre = track["genre"] if "genre" in track.keys() and track["genre"] and track["genre"] != "Uncategorized" else None
            if not track_genre:
                from yt2sp.resolve.genre import fetch_genre_validated
                gres = fetch_genre_validated(
                    title,
                    artists,
                    result_title=best_candidate.title if best_candidate else None,
                    result_artist=best_candidate.artist if best_candidate else None,
                )
                db.update_track_genre(video_id, gres.genre, source=gres.source)
        except Exception:
            pass

        stats["processed"] += 1
        if status == "resolved_auto":
            stats["auto"] += 1
        elif status == "needs_review":
            stats["review"] += 1
        else:
            stats["failed"] += 1

        if on_progress:
            on_progress(video_id, status, best_score)

    return stats
