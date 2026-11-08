"""Tests for multi-source genre detection and cross-validation."""
from unittest.mock import patch

from yt2sp.resolve.genre import (
    clean_track_query,
    detect_genre_heuristic,
    fetch_genre,
    fetch_genre_validated,
    validate_and_reconcile_genre,
)


def test_clean_track_query():
    # Remove bracket noise
    assert clean_track_query("Song Name [Official Music Video]", "Artist") == "Song Name Artist"
    assert clean_track_query("Track Title (Official Video)", "Artist") == "Track Title Artist"
    assert clean_track_query("【歌ってみた】Rokuchounen【Cover】", "Singer") == "Rokuchounen Singer"
    # Pipe cover separator
    assert clean_track_query("Original Song - Original Artist | Cover Singer", "Cover Singer") == "Original Song - Original Artist Cover Singer"


def test_detect_genre_heuristic():
    assert detect_genre_heuristic("Wildfire", "HOYO-MiX") == "Soundtrack & Classical"
    assert detect_genre_heuristic("Genshin Impact BGM", "Yu-Peng Chen") == "Soundtrack & Classical"
    assert detect_genre_heuristic("World is Mine feat. 初音ミク", "supercell") == "Anime"
    assert detect_genre_heuristic("Kopi Dangdut Koplo Kendang", "Singer") == "Dangdut & Koplo"
    assert detect_genre_heuristic("Lofi Beats to Study to", "Chillhop") == "Electronic & Dance"
    assert detect_genre_heuristic("Random Song", "Random Artist") is None


def test_validate_and_reconcile_agreement():
    # Both iTunes and Deezer agree on Pop
    res = validate_and_reconcile_genre("Pop", "Pop", None)
    assert res.genre == "Pop"
    assert res.status == "validated_agreement"
    assert res.confidence == 1.0
    assert res.source == "itunes+deezer"


def test_validate_and_reconcile_specificity():
    # iTunes has specific Indonesian Pop, Deezer has generic Pop
    res1 = validate_and_reconcile_genre("Indonesian Pop", "Pop", None)
    assert res1.genre == "Indonesian Pop"
    assert res1.status == "cross_validated"
    assert res1.confidence == 0.92

    # Deezer has specific Dangdut & Koplo, iTunes has generic Asian Music / Pop
    res2 = validate_and_reconcile_genre("Asian Music", "Dangdut", None)
    assert res2.genre == "Dangdut & Koplo"
    assert res2.status == "cross_validated"
    assert res2.confidence == 0.92


def test_validate_single_source():
    # Only Deezer found
    res_deezer = validate_and_reconcile_genre(None, "Rock", None)
    assert res_deezer.genre == "Rock"
    assert res_deezer.status == "single_source_deezer"
    assert res_deezer.confidence == 0.85

    # Only iTunes found
    res_itunes = validate_and_reconcile_genre("Alternative", None, None)
    assert res_itunes.genre == "Alternative & Indie"
    assert res_itunes.status == "single_source_itunes"
    assert res_itunes.confidence == 0.85


def test_validate_heuristic_fallback():
    # Both APIs return None, fallback to heuristic
    res = validate_and_reconcile_genre(None, None, "Anime")
    assert res.genre == "Anime"
    assert res.status == "heuristic"
    assert res.confidence == 0.75
    assert res.source == "context_heuristic"

    # All return None
    res_uncat = validate_and_reconcile_genre(None, None, None)
    assert res_uncat.genre == "Uncategorized"
    assert res_uncat.status == "uncategorized"
    assert res_uncat.confidence == 0.0


def test_fetch_genre_validated_with_mocks():
    with patch("yt2sp.resolve.genre.fetch_itunes_raw") as mock_itunes, \
         patch("yt2sp.resolve.genre.fetch_deezer_raw") as mock_deezer:
        mock_itunes.return_value = "Pop"
        mock_deezer.return_value = "Pop"

        res = fetch_genre_validated("Semua Aku Dirayakan", ["Nadin Amizah"])
        assert res.genre == "Pop"
        assert res.status == "validated_agreement"

        # Check backward-compatible fetch_genre returns string
        genre_str = fetch_genre("Semua Aku Dirayakan", ["Nadin Amizah"])
        assert genre_str == "Pop"
        assert isinstance(genre_str, str)
