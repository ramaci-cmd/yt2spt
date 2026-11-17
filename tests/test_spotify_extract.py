"""Tests for Spotify Playlist Extractor."""
from unittest.mock import MagicMock

from yt2sp.sources.spotify_extract import (
    clean_spotify_playlist_id,
    extract_spotify_playlist,
)


def test_clean_spotify_playlist_id():
    # Standard Web URL
    url1 = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=abcd1234efgh"
    assert clean_spotify_playlist_id(url1) == "37i9dQZF1DXcBWIGoYBM5M"

    # URL with localized country subpath (e.g. Indonesian locale intl-id)
    url_intl = "https://open.spotify.com/intl-id/playlist/37i9dQZF1DXcBWIGoYBM5M?si=abcd1234efgh"
    assert clean_spotify_playlist_id(url_intl) == "37i9dQZF1DXcBWIGoYBM5M"

    # URL with trailing slash
    url2 = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M/"
    assert clean_spotify_playlist_id(url2) == "37i9dQZF1DXcBWIGoYBM5M"

    # Spotify URI
    uri = "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"
    assert clean_spotify_playlist_id(uri) == "37i9dQZF1DXcBWIGoYBM5M"

    # Bare ID
    bare = "37i9dQZF1DXcBWIGoYBM5M"
    assert clean_spotify_playlist_id(bare) == "37i9dQZF1DXcBWIGoYBM5M"

    # Empty
    assert clean_spotify_playlist_id("") == ""


def test_extract_spotify_playlist_mocked():
    mock_client = MagicMock()
    mock_playlist = MagicMock()
    mock_playlist.name = "My Awesome Hits"
    mock_playlist.description = "Best tracks of the year"
    mock_playlist.owner.display_name = "Spotify Curator"
    mock_playlist.total_tracks = 2
    mock_playlist.images = [MagicMock(url="https://i.scdn.co/image/cover123")]

    track1 = MagicMock()
    track1.id = "4cOdK2wGLETKBW3PvgPWqT"
    track1.name = "Never Gonna Give You Up"
    a1 = MagicMock()
    a1.name = "Rick Astley"
    track1.artists = [a1]
    track1.album.name = "Whenever You Need Somebody"
    track1.duration_ms = 213000
    img1 = MagicMock()
    img1.url = "https://i.scdn.co/image/track1"
    track1.images = [img1]
    track1.isrc = "GBARL9800034"
    track1.preview_url = "https://p.scdn.co/mp3-preview/test"
    track1.uri = "spotify:track:4cOdK2wGLETKBW3PvgPWqT"
    track1.playable = True

    track2 = MagicMock()
    track2.id = "5tP4uqz4nJYabcdefghijk"
    track2.name = "Hotel California"
    a2 = MagicMock()
    a2.name = "Eagles"
    track2.artists = [a2]
    track2.album.name = "Hotel California"
    track2.duration_ms = 390000
    track2.images = []
    track2.isrc = None
    track2.preview_url = None
    track2.uri = "spotify:track:5tP4uqz4nJYabcdefghijk"
    track2.playable = True

    mock_item1 = MagicMock(track=track1)
    mock_item2 = MagicMock(track=track2)
    mock_playlist.tracks = [mock_item1, mock_item2]

    mock_client.get_playlist.return_value = mock_playlist

    res = extract_spotify_playlist("37i9dQZF1DXcBWIGoYBM5M", client=mock_client)

    assert res.id == "37i9dQZF1DXcBWIGoYBM5M"
    assert res.playlist_id == "37i9dQZF1DXcBWIGoYBM5M"
    assert res.cover_image == "https://i.scdn.co/image/cover123"
    assert res.thumbnail_url == "https://i.scdn.co/image/cover123"
    assert res.title == "My Awesome Hits"
    assert res.description == "Best tracks of the year"
    assert res.track_count == 2
    assert res.unavailable_count == 0
    assert len(res.tracks) == 2

    t1 = res.tracks[0]
    assert t1.track_id == "4cOdK2wGLETKBW3PvgPWqT"
    assert t1.id == "4cOdK2wGLETKBW3PvgPWqT"
    assert t1.video_id == "4cOdK2wGLETKBW3PvgPWqT"
    assert t1.title == "Never Gonna Give You Up"
    assert t1.artists == ["Rick Astley"]
    assert t1.album == "Whenever You Need Somebody"
    assert t1.duration_ms == 213000
    assert t1.isrc == "GBARL9800034"

    d1 = t1.to_dict()
    assert d1["video_id"] == "4cOdK2wGLETKBW3PvgPWqT"
    assert d1["title"] == "Never Gonna Give You Up"
