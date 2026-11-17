"""Tests for YouTube Music Playlist Writer."""
from unittest.mock import MagicMock

from yt2sp.destinations.ytm_writer import (
    YTMExportResult,
    create_and_populate_ytm_playlist,
    normalize_browser_headers,
)


def test_normalize_browser_headers_curl():
    curl_input = """curl 'https://music.youtube.com/youtubei/v1/browse' \\
  -H 'accept: */*' \\
  -H 'cookie: SID=123; SAPISID=456;' \\
  -H 'user-agent: Mozilla/5.0'"""
    res = normalize_browser_headers(curl_input)
    assert "cookie: SID=123; SAPISID=456" in res
    assert "x-goog-authuser: 0" in res
    assert "user-agent: Mozilla/5.0" in res


def test_create_and_populate_ytm_playlist_mocked():
    mock_ytm = MagicMock()
    mock_ytm.create_playlist.return_value = "PLtest123456789"
    mock_ytm.add_playlist_items.return_value = {"status": "STATUS_SUCCEEDED"}

    video_ids = [f"vid_{i:04d}" for i in range(120)]
    res = create_and_populate_ytm_playlist(
        title="My Road Trip Hits",
        video_ids=video_ids,
        description="Spotify to YTM Test",
        privacy_status="PRIVATE",
        chunk_size=50,
        ytm_client=mock_ytm,
    )

    assert isinstance(res, YTMExportResult)
    assert res.status == "success"
    assert res.playlist_id == "PLtest123456789"
    assert res.playlist_url == "https://music.youtube.com/playlist?list=PLtest123456789"
    assert res.total_requested == 120
    assert res.total_added == 120
    assert len(res.failed_ids) == 0

    # 120 tracks / 50 chunk size = 3 calls to add_playlist_items
    assert mock_ytm.add_playlist_items.call_count == 3
