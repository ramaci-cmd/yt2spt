"""Tests for resolver and fallback components."""
from unittest.mock import MagicMock, patch

from yt2sp.resolve.deezer_resolver import _resolve_spotify_from_isrc, DeezerCandidate
from yt2sp.resolve.spotify_resolver import _get_client, _reset_client


def test_spotify_client_singleton_and_reset():
    _reset_client()
    c1 = _get_client()
    c2 = _get_client()
    assert c1 is c2
    _reset_client()
    c3 = _get_client()
    assert c3 is not c1
    _reset_client()


def test_resolve_spotify_from_isrc_musicbrainz():
    with patch("yt2sp.resolve.deezer_resolver._mb_spotify_from_isrc") as mock_mb:
        mock_mb.return_value = ["spotify1234567890abcdef"]
        ids = _resolve_spotify_from_isrc("USRC17607839")
        assert ids == ["spotify1234567890abcdef"]
        mock_mb.assert_called_once_with("USRC17607839")


def test_resolve_spotify_from_isrc_fallback():
    with patch("yt2sp.resolve.deezer_resolver._mb_spotify_from_isrc") as mock_mb, \
         patch("yt2sp.resolve.spotify_resolver._get_client") as mock_client_getter:
        mock_mb.return_value = []
        mock_track = MagicMock()
        mock_track.id = "fallback1234567890abcd"
        mock_res = MagicMock()
        mock_res.tracks = [mock_track]
        mock_client = MagicMock()
        mock_client.search.return_value = mock_res
        mock_client_getter.return_value = mock_client

        ids = _resolve_spotify_from_isrc("USRC17607839")
        assert ids == ["fallback1234567890abcd"]
        mock_client.search.assert_called_once_with("isrc:USRC17607839", types=("track",))
