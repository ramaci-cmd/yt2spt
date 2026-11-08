"""Tests for fuzzy scoring and classification."""
from yt2sp.match.score import classify, compute_score


def test_exact_match():
    score, reason = compute_score(
        yt_title="Never Gonna Give You Up (Official Video)",
        yt_artists=["Rick Astley"],
        sp_title="Never Gonna Give You Up",
        sp_artist="Rick Astley",
        yt_duration_ms=213000,
        sp_duration_ms=213500,
    )
    assert score >= 0.95
    assert classify(score) == "resolved_auto"


def test_distinctive_marker_penalty():
    # YTM is live version, Spotify is studio version
    score, reason = compute_score(
        yt_title="Hotel California (Live)",
        yt_artists=["Eagles"],
        sp_title="Hotel California",
        sp_artist="Eagles",
    )
    # Penalty applies
    assert "marker" in reason
    assert score < 0.85
    assert classify(score) in ("needs_review", "failed")


def test_classify_thresholds():
    assert classify(0.90) == "resolved_auto"
    assert classify(0.85) == "resolved_auto"
    assert classify(0.84) == "needs_review"
    assert classify(0.60) == "needs_review"
    assert classify(0.59) == "failed"


def test_duration_tolerance():
    # Difference <= 5s: no penalty
    score1, reason1 = compute_score(
        yt_title="Song A",
        yt_artists=["Artist A"],
        sp_title="Song A",
        sp_artist="Artist A",
        yt_duration_ms=60000,
        sp_duration_ms=63000,
    )
    assert "durasi" not in reason1

    # Difference > 12s on a 5-minute song (even if < 10%): penalty applies
    score2, reason2 = compute_score(
        yt_title="Song B",
        yt_artists=["Artist B"],
        sp_title="Song B",
        sp_artist="Artist B",
        yt_duration_ms=300000,
        sp_duration_ms=320000,
    )
    assert "durasi" in reason2
    assert score2 <= 0.90
