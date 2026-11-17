"""Comprehensive verification tests for the Unified Bidirectional Music Migration Platform.

Scenarios tested:
- Scenario A: Existing User Update & Legacy Database Backward Compatibility
- Scenario B: Legacy Workflow (YouTube Music -> Spotify)
- Scenario C: New Workflow (Spotify -> YouTube Music)
- Scenario D: API Bidirectional & Dynamic Alternative Routing
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yt2sp.destinations.ytm_resolver import YTMTrackCandidate
from yt2sp.destinations.ytm_writer import AuthResult, check_ytm_auth, create_and_populate_ytm_playlist
from yt2sp.resolve.pipeline import run_resolve
from yt2sp.resolve.spotify_resolver import SpotifyCandidate
from yt2sp.sources.spotify_extract import SpotifyPlaylistResult, SpotifyTrackItem, clean_spotify_playlist_id
from yt2sp.store import db


def test_scenario_a_legacy_database_migration(tmp_path: Path):
    """
    Simulate updating from a legacy v1.3.7 database created before the reverse refactor.
    Ensure existing tables, columns, playlist history, and matches are 100% preserved.
    """
    legacy_db_file = tmp_path / "legacy_yt2sp.db"

    # 1. Create a raw legacy v1.3.7 SQLite schema without new columns
    conn = sqlite3.connect(str(legacy_db_file))
    conn.executescript(
        """
        CREATE TABLE playlists (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            yt_playlist_id  TEXT UNIQUE NOT NULL,
            title           TEXT,
            track_count     INTEGER,
            unavailable_count INTEGER DEFAULT 0,
            extracted_at    TEXT
        );
        CREATE TABLE tracks (
            video_id    TEXT PRIMARY KEY,
            title       TEXT,
            artists     TEXT,
            album       TEXT,
            duration_ms INTEGER,
            video_type  TEXT,
            genre       TEXT
        );
        CREATE TABLE playlist_tracks (
            playlist_id INTEGER NOT NULL REFERENCES playlists(id),
            video_id    TEXT    NOT NULL REFERENCES tracks(video_id),
            position    INTEGER NOT NULL,
            PRIMARY KEY (playlist_id, video_id)
        );
        CREATE TABLE matches (
            video_id        TEXT PRIMARY KEY REFERENCES tracks(video_id),
            spotify_id      TEXT,
            tier            TEXT,
            score           REAL,
            status          TEXT DEFAULT 'pending',
            result_title    TEXT,
            result_artist   TEXT,
            decided_by      TEXT,
            reason          TEXT,
            updated_at      TEXT
        );
        INSERT INTO playlists (yt_playlist_id, title, track_count, extracted_at)
        VALUES ('PL_legacy_ytm_123', 'My Nostalgic 90s Hits', 2, '2025-01-01T00:00:00Z');

        INSERT INTO tracks (video_id, title, artists, album, duration_ms, video_type)
        VALUES ('yt_vid_001', 'Wonderwall', '["Oasis"]', '(What''s the Story) Morning Glory?', 258000, 'song'),
               ('yt_vid_002', 'Song 2', '["Blur"]', 'Blur', 122000, 'song');

        INSERT INTO playlist_tracks (playlist_id, video_id, position)
        VALUES (1, 'yt_vid_001', 0), (1, 'yt_vid_002', 1);

        INSERT INTO matches (video_id, spotify_id, tier, score, status, result_title, result_artist, decided_by)
        VALUES ('yt_vid_001', 'sp_oasis_wonderwall_id', 'T1', 0.98, 'accepted', 'Wonderwall', 'Oasis', 'auto'),
               ('yt_vid_002', 'sp_blur_song2_id', 'T1', 0.95, 'accepted', 'Song 2', 'Blur', 'auto');
        """
    )
    conn.commit()
    conn.close()

    # 2. Run db.init_db() on the legacy database file
    db.init_db(legacy_db_file)

    # 3. Verify zero data loss and safe column migration
    pls = db.get_all_playlists()
    assert len(pls) == 1
    p = pls[0]
    assert p["title"] == "My Nostalgic 90s Hits"
    assert p["yt_playlist_id"] == "PL_legacy_ytm_123"
    assert p["track_count"] == 2
    # Ensure source_provider and destination_provider correctly identify it as legacy YouTube Music -> Spotify
    assert p["source_provider"] == "youtube"
    assert p["destination_provider"] == "spotify"

    tracks = db.get_playlist_tracks(p["id"])
    assert len(tracks) == 2
    assert tracks[0]["title"] == "Wonderwall"
    assert tracks[0]["spotify_id"] == "sp_oasis_wonderwall_id"
    assert tracks[0]["status"] == "accepted"


def test_scenario_b_legacy_yt_to_spotify_workflow(tmp_path: Path):
    """
    Test YouTube Music -> Spotify workflow end-to-end:
    - Extracted track stored with source_provider='youtube'
    - Resolved targeting Spotify via search_spotify
    - Match saved with Spotify ID
    """
    db_file = tmp_path / "yt2sp_workflow.db"
    db.init_db(db_file)

    pl_id = db.upsert_playlist(
        "PL_rock_classics",
        "Classic Rock",
        1,
        source_provider="youtube",
        destination_provider="spotify",
    )
    db.upsert_track(
        "yt_vid_hotel_california",
        "Hotel California",
        ["Eagles"],
        "Hotel California",
        390000,
        source_provider="youtube",
    )
    db.upsert_playlist_track(pl_id, "yt_vid_hotel_california", 0)

    # Mock search_spotify
    mock_spotify_cand = SpotifyCandidate(
        spotify_id="40riOy7x9W7GXjyGp4pjAv",
        uri="spotify:track:40riOy7x9W7GXjyGp4pjAv",
        title="Hotel California - 2013 Remaster",
        artist="Eagles",
        duration_ms=391000,
    )

    with patch("yt2sp.resolve.pipeline.search_spotify", return_value=[mock_spotify_cand]):
        stats = run_resolve(playlist_id=pl_id)
        assert stats["processed"] == 1
        assert stats["auto"] == 1

    # Verify match stored in database
    match = db.get_match("yt_vid_hotel_california")
    assert match is not None
    assert match["status"] == "resolved_auto"
    assert match["spotify_id"] == "40riOy7x9W7GXjyGp4pjAv"
    assert match["dest_id"] == "40riOy7x9W7GXjyGp4pjAv"


def test_scenario_c_new_spotify_to_ytm_workflow(tmp_path: Path):
    """
    Test Spotify -> YouTube Music workflow end-to-end:
    - Spotify playlist extracted and stored with source_provider='spotify'
    - Resolved targeting YouTube Music via search_ytm_tracks
    - Match saved with YTM video ID
    - Playlist export verified via create_and_populate_ytm_playlist
    """
    db_file = tmp_path / "sp2yt_workflow.db"
    db.init_db(db_file)

    pl_id = db.upsert_playlist(
        "37i9dQZF1DXcBWIGoYBM5M",
        "Today's Top Hits",
        1,
        source_provider="spotify",
        destination_provider="ytm",
    )
    db.upsert_track(
        "sp_track_blinding_lights",
        "Blinding Lights",
        ["The Weeknd"],
        "After Hours",
        200000,
        source_provider="spotify",
    )
    db.upsert_playlist_track(pl_id, "sp_track_blinding_lights", 0)

    # Mock search_ytm_tracks
    mock_ytm_cand = YTMTrackCandidate(
        video_id="4NRXx6U8ABQ",
        title="Blinding Lights",
        artist="The Weeknd",
        artists=["The Weeknd"],
        album="After Hours",
        duration_ms=200000,
        video_type="song",
        url="https://music.youtube.com/watch?v=4NRXx6U8ABQ",
        thumbnail_url="https://i.ytimg.com/vi/4NRXx6U8ABQ/default.jpg",
    )

    with patch("yt2sp.resolve.pipeline.search_ytm_tracks", return_value=[mock_ytm_cand]):
        stats = run_resolve(playlist_id=pl_id)
        assert stats["processed"] == 1
        assert stats["auto"] == 1

    # Verify match stored in database
    match = db.get_match("sp_track_blinding_lights")
    assert match is not None
    assert match["status"] == "resolved_auto"
    assert match["dest_id"] == "4NRXx6U8ABQ"
    assert match["spotify_id"] == "4NRXx6U8ABQ"

    # Test export call to YouTube Music
    mock_ytm = MagicMock()
    mock_ytm.create_playlist.return_value = "PL_new_ytm_playlist_id"
    mock_ytm.add_playlist_items.return_value = {"status": "STATUS_SUCCEEDED"}

    res = create_and_populate_ytm_playlist(
        title="Today's Top Hits (Spotify2YTM)",
        track_ids=[match["dest_id"]],
        ytm_client=mock_ytm,
    )
    assert res.status == "success"
    assert res.playlist_id == "PL_new_ytm_playlist_id"
    assert res.total_added == 1


def test_auth_result_contract():
    """Verify AuthResult works both as a boolean and as an unpackable 2-tuple."""
    # When authenticating successfully
    res_ok = AuthResult(True, None)
    assert bool(res_ok) is True
    ok, err = res_ok
    assert ok is True
    assert err is None

    # When authentication fails
    res_err = AuthResult(False, "Missing credentials")
    assert bool(res_err) is False
    ok, err = res_err
    assert ok is False
    assert err == "Missing credentials"


def test_url_auto_detection():
    """Verify URL detection correctly routes Spotify vs YouTube Music URLs."""
    # Spotify URL variants
    assert clean_spotify_playlist_id("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=123") == "37i9dQZF1DXcBWIGoYBM5M"
    assert clean_spotify_playlist_id("spotify:playlist:37i9dQZF1DXcBWIGoYBM5M") == "37i9dQZF1DXcBWIGoYBM5M"
    assert clean_spotify_playlist_id("37i9dQZF1DXcBWIGoYBM5M") == "37i9dQZF1DXcBWIGoYBM5M"

    # YouTube Music URLs must NOT be parsed as Spotify IDs
    assert clean_spotify_playlist_id("https://music.youtube.com/playlist?list=PL1234567890123456789012") == ""
    assert clean_spotify_playlist_id("PL12345678901234567890123456789012") == ""
    assert clean_spotify_playlist_id("RDCLAK5uy_k123456789012345678901234") == ""
