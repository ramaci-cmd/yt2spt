"""Fuzzy scoring judul + artis menggunakan rapidfuzz.

Skor akhir = bobot_judul * sim_judul + bobot_artis * sim_artis
Penalti: jika salah satu sisi punya penanda pembeda tapi yang lain tidak.
"""
from __future__ import annotations

from rapidfuzz import fuzz

from yt2sp.match.normalize import (
    has_distinctive_marker,
    normalize_artist,
    normalize_title,
)

_DISTINCTIVE_PENALTY = 0.30  # kurangi skor jika penanda mismatch


def _best_artist_score(yt_artists: list[str], sp_artist: str) -> float:
    """Ambil skor tertinggi antara semua artis YTM vs artis Spotify."""
    sp_norm = normalize_artist(sp_artist)
    best = 0.0
    for a in yt_artists:
        a_norm = normalize_artist(a)
        s = fuzz.token_set_ratio(a_norm, sp_norm) / 100.0
        if s > best:
            best = s
    return best


def compute_score(
    yt_title: str,
    yt_artists: list[str],
    sp_title: str,
    sp_artist: str,
    yt_duration_ms: int | None = None,
    sp_duration_ms: int | None = None,
    *,
    title_weight: float = 0.6,
    artist_weight: float = 0.4,
    duration_tolerance: float = 0.10,
    max_duration_diff_ms: int = 12000,
) -> tuple[float, str]:
    """
    Return (score, reason).
    score dalam rentang 0.0 – 1.0.
    reason berisi penjelasan singkat.
    """
    yt_norm = normalize_title(yt_title)
    sp_norm = normalize_title(sp_title)

    title_sim = fuzz.token_set_ratio(yt_norm, sp_norm) / 100.0
    artist_sim = _best_artist_score(yt_artists, sp_artist)

    score = title_weight * title_sim + artist_weight * artist_sim
    reasons: list[str] = []

    # Penalti penanda pembeda
    yt_markers = has_distinctive_marker(yt_title)
    sp_markers = has_distinctive_marker(sp_title)
    only_yt = yt_markers - sp_markers
    only_sp = sp_markers - yt_markers
    if only_yt:
        score -= _DISTINCTIVE_PENALTY
        reasons.append(f"marker hanya di YTM: {only_yt}")
    if only_sp:
        score -= _DISTINCTIVE_PENALTY
        reasons.append(f"marker hanya di Spotify: {only_sp}")

    # Penalti durasi (opsional)
    if yt_duration_ms and sp_duration_ms and yt_duration_ms > 0:
        diff_ms = abs(yt_duration_ms - sp_duration_ms)
        diff_pct = diff_ms / yt_duration_ms
        if diff_ms > 5000 and (diff_pct > duration_tolerance or diff_ms > max_duration_diff_ms):
            score -= 0.10
            reasons.append(f"durasi beda {diff_pct:.0%}")

    score = max(0.0, min(1.0, score))
    reason = "; ".join(reasons) if reasons else "ok"
    return score, reason


def classify(
    score: float,
    *,
    auto_threshold: float = 0.85,
    review_threshold: float = 0.60,
) -> str:
    """Return 'resolved_auto' | 'needs_review' | 'failed'."""
    if score >= auto_threshold:
        return "resolved_auto"
    if score >= review_threshold:
        return "needs_review"
    return "failed"
