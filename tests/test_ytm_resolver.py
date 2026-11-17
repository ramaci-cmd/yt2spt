"""Tests for YouTube Music Resolver and alternatives finder."""
from unittest.mock import MagicMock

from yt2sp.destinations.ytm_resolver import (
    YTMTrackCandidate,
    find_ytm_alternative_versions,
    search_ytm_tracks,
)


def test_search_ytm_tracks_mocked():
    mock_ytm = MagicMock()
    mock_item1 = {
        "videoId": "BciS5krYL80",
        "title": "Hotel California",
        "artists": [{"name": "Eagles", "id": "123"}],
        "album": {"name": "Hotel California (2013 Remaster)"},
        "duration_seconds": 391,
        "videoType": "MUSIC_VIDEO_TYPE_ATV",
        "thumbnails": [{"url": "https://yt3.ggpht.com/thumb1"}],
    }
    mock_ytm.search.return_value = [mock_item1]

    candidates = search_ytm_tracks("Hotel California", ["Eagles"], ytm=mock_ytm)
    assert len(candidates) == 1

    c = candidates[0]
    assert isinstance(c, YTMTrackCandidate)
    assert c.video_id == "BciS5krYL80"
    assert c.title == "Hotel California"
    assert c.artist == "Eagles"
    assert c.duration_ms == 391000
    assert c.video_type == "MUSIC_VIDEO_TYPE_ATV"
    assert c.url == "https://music.youtube.com/watch?v=BciS5krYL80"


def test_find_ytm_alternative_versions_mocked():
    mock_ytm = MagicMock()
    mock_item_cover = {
        "videoId": "cover123456",
        "title": "Hotel California (Acoustic Cover)",
        "artists": [{"name": "Boyce Avenue", "id": "456"}],
        "duration_seconds": 240,
        "thumbnails": [{"url": "https://yt3.ggpht.com/thumb_cover"}],
    }
    mock_ytm.search.return_value = [mock_item_cover]

    alts = find_ytm_alternative_versions("Hotel California", ["Eagles"], ytm=mock_ytm)
    assert len(alts) >= 1
    alt = alts[0]
    assert alt["video_id"] == "cover123456"
    assert "Cover" in alt["tag"] or "Alternatif" in alt["tag"]
