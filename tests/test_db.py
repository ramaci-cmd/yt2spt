"""Tests for database layer."""
import tempfile
from pathlib import Path
from yt2sp.store import db


def test_db_operations(tmp_path: Path):
    db_file = tmp_path / "test.db"
    db.init_db(db_file)

    # 1. Upsert playlist
    pl_id = db.upsert_playlist("PL123", "My Playlist", 2, unavailable_count=1)
    assert pl_id > 0
    pl_row = db.get_playlist_by_ytid("PL123")
    assert pl_row is not None
    assert pl_row["unavailable_count"] == 1

    # 2. Upsert tracks
    db.upsert_track("vid1", "Title 1", ["Artist 1"], "Album 1", 200000, "MUSIC_VIDEO_TYPE_ATV")
    db.upsert_track("vid2", "Title 2", ["Artist 2"], "Album 2", 180000, "MUSIC_VIDEO_TYPE_ATV")

    db.upsert_playlist_track(pl_id, "vid1", 0)
    db.upsert_playlist_track(pl_id, "vid2", 1)

    # Verify playlist tracks
    tracks = db.get_playlist_tracks(pl_id)
    assert len(tracks) == 2
    assert tracks[0]["video_id"] == "vid1"
    assert tracks[1]["video_id"] == "vid2"

    sample_vids = db.get_playlist_sample_video_ids(pl_id, limit=4)
    assert sample_vids == ["vid1", "vid2"]

    # 3. Match operations
    db.set_match(
        "vid1",
        spotify_id="4cOdK2wGLETKBW3PvgPWqT",
        tier="T1",
        score=0.98,
        status="resolved_auto",
        result_title="Title 1",
        result_artist="Artist 1",
    )

    m = db.get_match("vid1")
    assert m["spotify_id"] == "4cOdK2wGLETKBW3PvgPWqT"
    assert m["status"] == "resolved_auto"

    # Status summary
    s = db.get_status_summary()
    assert s["total"] == 2
    assert s["resolved_auto"] == 1
    assert s["pending"] == 1

    # 4. Genre operations with validation source
    db.update_track_genre("vid1", "Pop", source="itunes+deezer")
    db.update_track_genre("vid2", "Uncategorized", source="none")
    
    uncat = db.get_tracks_without_genre(include_uncategorized=True)
    assert len(uncat) == 1
    assert uncat[0]["video_id"] == "vid2"

    null_only = db.get_tracks_without_genre(include_uncategorized=False)
    assert len(null_only) == 0

    # 5. Batch deletion of tracks
    db.upsert_track("vid3", "Title 3", ["Artist 3"], "Album 3", 190000, "MUSIC_VIDEO_TYPE_ATV")
    db.upsert_playlist_track(pl_id, "vid3", 2)
    assert len(db.get_playlist_tracks(pl_id)) == 3

    deleted_count = db.delete_tracks(["vid1", "vid3"], pl_id)
    assert deleted_count == 2
    remaining = db.get_playlist_tracks(pl_id)
    assert len(remaining) == 1
    assert remaining[0]["video_id"] == "vid2"

    # 6. Batch deletion of playlists
    pl_id2 = db.upsert_playlist("PL456", "Second Playlist", 0)
    assert len(db.get_all_playlists()) == 2
    del_pl_count = db.delete_playlists([pl_id, pl_id2])
    assert del_pl_count == 2
    assert len(db.get_all_playlists()) == 0

