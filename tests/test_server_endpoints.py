"""Tests for server API endpoints."""
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from yt2sp.store import db
from yt2sp.ui.server import UIHandler


@pytest.fixture(scope="module")
def test_env(tmp_path_factory):
    tmp_dir = tmp_path_factory.mktemp("db")
    db_file = tmp_dir / "yt2sp.db"

    patcher = patch("yt2sp.store.db.DB_PATH", db_file)
    patcher.start()

    db.init_db(db_file)
    server = ThreadingHTTPServer(("127.0.0.1", 0), UIHandler)
    host, port = server.server_address
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    yield f"http://{host}:{port}", db_file

    server.shutdown()
    server.server_close()
    patcher.stop()


def test_ytm_auth_status_endpoint(test_env):
    server_url, _ = test_env
    with patch("yt2sp.destinations.ytm_writer.check_ytm_auth", return_value=(True, None)):
        req = urllib.request.Request(f"{server_url}/api/ytm-auth-status")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            assert data["authenticated"] is True


def test_export_ytm_unauthenticated(test_env):
    server_url, _ = test_env
    with patch("yt2sp.destinations.ytm_writer.check_ytm_auth", return_value=(False, "No auth file")):
        req = urllib.request.Request(
            f"{server_url}/api/export-ytm",
            data=json.dumps({"playlist_id": "all"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req)
            assert False, "Should raise HTTPError"
        except urllib.error.HTTPError as exc:
            assert exc.code == 401
            body = json.loads(exc.read().decode())
            assert "Autentikasi YouTube Music belum siap" in body["error"]


def test_review_manual_ytm_video_id(test_env):
    server_url, db_file = test_env
    with patch("yt2sp.store.db.DB_PATH", db_file):
        # Insert dummy track into DB
        db.init_db(db_file)
        db.upsert_track("sp_track_123456789012", "Never Gonna Give You Up", ["Rick Astley"], "Whenever You Need Somebody", 213000, "song")

        payload = {
            "video_id": "sp_track_123456789012",
            "action": "manual",
            "spotify_id": "https://music.youtube.com/watch?v=dQw4w9WgXcQ",
        }
        req = urllib.request.Request(
            f"{server_url}/api/review",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            assert data["status"] == "ok"
            assert data["spotify_id"] == "dQw4w9WgXcQ"
            assert data["dest_id"] == "dQw4w9WgXcQ"


def test_tracks_endpoint_thumbnail_fields(test_env):
    server_url, db_file = test_env
    with patch("yt2sp.store.db.DB_PATH", db_file):
        db.init_db(db_file)
        sp_id = "test_sp_track_00112233"
        dest_vid = "dQw4w9WgXcQ"
        db.upsert_track(
            sp_id,
            "Sample Song",
            ["Sample Artist"],
            "Sample Album",
            180000,
            "song",
            thumbnail_url="https://i.scdn.co/image/test_cover_123",
            source_provider="spotify",
        )
        db.set_match(
            sp_id,
            dest_id=dest_vid,
            spotify_id=dest_vid,
            tier="T1_direct",
            score=0.95,
            status="resolved_auto",
            result_title="Sample Song YTM",
            result_artist="Sample Artist",
            decided_by="auto",
            reason="High similarity",
            result_url=f"https://music.youtube.com/watch?v={dest_vid}",
            result_thumbnail="https://yt3.googleusercontent.com/test_ytm_thumb",
        )

        req = urllib.request.Request(f"{server_url}/api/tracks?playlist_id=all")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            tracks = data.get("tracks", [])
            matched_track = next((t for t in tracks if t["video_id"] == sp_id), None)
            assert matched_track is not None
            assert matched_track["thumbnail_url"] == "https://i.scdn.co/image/test_cover_123"
            assert matched_track["result_thumbnail"] == "https://yt3.googleusercontent.com/test_ytm_thumb"
            assert matched_track["dest_id"] == dest_vid
