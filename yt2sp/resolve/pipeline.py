"""Pipeline resolve utama: ambil pending tracks, search destination provider (Spotify atau YouTube Music), score, simpan."""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Callable

from yt2sp.destinations.ytm_resolver import YTMTrackCandidate, search_ytm_tracks
from yt2sp.match.score import classify, compute_score
from yt2sp.resolve.deezer_resolver import search_deezer
from yt2sp.resolve.rate_limiter import RateLimiter, backoff_sleep
from yt2sp.resolve.spotify_resolver import SpotifyCandidate, search_spotify
from yt2sp.store import db

logger = logging.getLogger(__name__)


def run_resolve(
    *,
    limit: int | None = None,
    playlist_id: int | None = None,
    rate_per_minute: float = 80.0,
    auto_threshold: float = 0.80,
    review_threshold: float = 0.55,
    title_weight: float = 0.6,
    artist_weight: float = 0.4,
    duration_tolerance: float = 0.10,
    on_progress: Callable[[str, str, float], None] | None = None,
    stop_event: threading.Event | None = None,
) -> dict:
    """
    Jalankan matching engine dua arah (bidirectional):
    - Jika track berasal dari Spotify -> cari kecocokan di YouTube Music (T1 YTM search)
    - Jika track berasal dari YouTube Music -> cari kecocokan di Spotify (T1 Spotify search + T2 Deezer ISRC)

    on_progress(video_id, status, score) dipanggil tiap lagu selesai.
    Return dict statistik.
    """
    limiter = RateLimiter(rate_per_minute=rate_per_minute)
    pending = db.get_pending_tracks(playlist_id=playlist_id)
    if limit:
        pending = pending[:limit]

    # Check destination playlist provider if playlist_id is provided
    playlist_dest = None
    if playlist_id is not None:
        pl_info = db.get_playlist(playlist_id)
        if pl_info:
            playlist_dest = pl_info["destination_provider"] if "destination_provider" in pl_info.keys() else None

    stats = {"processed": 0, "auto": 0, "review": 0, "failed": 0, "skipped": 0}

    for track in pending:
        if stop_event and stop_event.is_set():
            logger.info("run_resolve stopped by stop_event.")
            break

        video_id = track["video_id"]
        title = track["title"] or ""
        artists: list[str] = json.loads(track["artists"]) if track["artists"] else []
        duration_ms = track["duration_ms"] or 0
        video_type = track["video_type"] or ""
        track_src = (track["source_provider"] if "source_provider" in track.keys() else None) or "youtube"

        # Determine target provider
        if playlist_dest:
            is_targeting_ytm = (playlist_dest == "ytm")
        else:
            is_targeting_ytm = (track_src == "spotify")

        # Skip non-music tracks
        if video_type in ("PODCAST", "EPISODE", "SKIPPED", "MUSIC_VIDEO_TYPE_UGC"):
            db.set_match(
                video_id,
                dest_id=None,
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

        best_score = -1.0
        best_candidate: Any = None
        best_reason = ""
        best_tier = "T1"
        status = "failed"
        dest_id: str | None = None
        res_title: str = ""
        res_artist: str = ""
        res_url: str = ""
        res_thumb: str = ""

        # Route 1: Spotify -> YouTube Music
        if is_targeting_ytm:
            try:
                candidates = search_ytm_tracks(title, artists, top_n=5)
            except Exception as exc:
                logger.error("Error resolve YTM %s: %s", video_id, exc)
                candidates = []

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

            # Fallback search if primary query yields no confident candidate
            if (status == "failed" or not candidates) and artists:
                try:
                    fallback_cands = search_ytm_tracks(title, [artists[0]], top_n=3)
                    for fcand in fallback_cands:
                        f_score, f_reason = compute_score(
                            title,
                            artists,
                            fcand.title,
                            fcand.artist,
                            duration_ms,
                            fcand.duration_ms,
                            title_weight=title_weight,
                            artist_weight=artist_weight,
                            duration_tolerance=duration_tolerance,
                        )
                        if f_score >= review_threshold and f_score > best_score:
                            best_score = f_score
                            best_tier = "T2_fallback"
                            best_candidate = fcand
                            best_reason = f"Fallback search: {f_reason}".strip("; ")
                            status = classify(
                                best_score,
                                auto_threshold=auto_threshold,
                                review_threshold=review_threshold,
                            )
                            break
                except Exception as exc:
                    logger.debug("T2 fallback error for %s: %s", video_id, exc)

            if not best_candidate and status == "failed":
                best_reason = best_reason or "not found in YouTube Music catalog"

            if best_candidate:
                dest_id = best_candidate.video_id
                res_title = best_candidate.title
                res_artist = best_candidate.artist
                res_url = best_candidate.url
                res_thumb = best_candidate.thumbnail_url or (f"https://i.ytimg.com/vi/{dest_id}/mqdefault.jpg" if (dest_id and len(dest_id) == 11) else "")

        # Route 2: YouTube Music -> Spotify
        else:
            try:
                sp_candidates = search_spotify(title, artists, top_n=5)
            except Exception as exc:
                logger.error("Error resolve Spotify %s: %s", video_id, exc)
                sp_candidates = []

            for scand in sp_candidates:
                score, reason = compute_score(
                    title,
                    artists,
                    scand.title,
                    scand.artist,
                    duration_ms,
                    scand.duration_ms,
                    title_weight=title_weight,
                    artist_weight=artist_weight,
                    duration_tolerance=duration_tolerance,
                )
                if score > best_score:
                    best_score = score
                    best_candidate = scand
                    best_reason = reason

            status = classify(
                best_score,
                auto_threshold=auto_threshold,
                review_threshold=review_threshold,
            )

            # Fallback T2: Deezer ISRC if T1 search fails
            if status == "failed" or not sp_candidates:
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
                best_reason = best_reason or "not found in Spotify or Deezer catalog"

            if best_candidate:
                dest_id = best_candidate.spotify_id
                res_title = best_candidate.title
                res_artist = best_candidate.artist
                res_url = getattr(best_candidate, "uri", f"spotify:track:{best_candidate.spotify_id}")
                res_thumb = ""

        # Persist match in database
        db.set_match(
            video_id,
            dest_id=dest_id,
            spotify_id=dest_id,  # Backward compatibility synchronization
            tier=best_tier,
            score=max(0.0, best_score),
            status=status,
            result_title=res_title,
            result_artist=res_artist,
            decided_by="auto",
            reason=best_reason,
            result_url=res_url,
            result_thumbnail=res_thumb,
        )

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
