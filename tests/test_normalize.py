"""Tests for title and artist normalization."""
from yt2sp.match.normalize import (
    has_distinctive_marker,
    normalize_artist,
    normalize_title,
)


def test_normalize_strips_noise():
    # Official video, 4K, Remastered
    raw = "Never Gonna Give You Up (Official Video) (4K Remaster)"
    assert normalize_title(raw) == "never gonna give you up"

    # MV, HD
    raw2 = "Bohemian Rhapsody [Official Music Video 4K]"
    assert normalize_title(raw2) == "bohemian rhapsody"

    # Lyrics video
    raw3 = "Yellow (Lyric Video)"
    assert normalize_title(raw3) == "yellow"


def test_normalize_preserves_distinctive_markers():
    # Live
    raw = "Hotel California (Live at The Forum)"
    norm = normalize_title(raw)
    assert "live" in norm

    # Remix
    raw2 = "Levitating (feat. DaBaby) (Remix)"
    norm2 = normalize_title(raw2)
    assert "remix" in norm2

    # Acoustic
    raw3 = "Creep (Acoustic Version)"
    norm3 = normalize_title(raw3)
    assert "acoustic" in norm3

    # Cover
    raw4 = "Fast Car (Luke Combs Cover)"
    norm4 = normalize_title(raw4)
    assert "cover" in norm4


def test_has_distinctive_marker():
    assert has_distinctive_marker("Song Title (Live in Jakarta)") == {"live"}
    assert has_distinctive_marker("Song Title (Acoustic / Remix)") == {"acoustic", "remix"}
    assert has_distinctive_marker("Regular Official Video") == set()


def test_normalize_artist():
    assert normalize_artist("Rick Astley") == "rick astley"
    assert normalize_artist("Dua Lipa feat. DaBaby") == "dua lipa"
    assert normalize_artist("Hindia ft. Sal Priadi") == "hindia"
