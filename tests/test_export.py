"""Tests for export writer and report."""
from pathlib import Path
from yt2sp.export.writer import validate_uri, write_uri_blocks


def test_validate_uri():
    assert validate_uri("spotify:track:4cOdK2wGLETKBW3PvgPWqT") is True
    assert validate_uri("spotify:track:short") is False
    assert validate_uri("https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT") is False


def test_write_uri_blocks(tmp_path: Path):
    uris = [
        f"spotify:track:{i:022d}" for i in range(125)
    ]
    files = write_uri_blocks("Test Playlist", uris, tmp_path, chunk_size=50)

    # 125 tracks / 50 chunk size = 3 files (50, 50, 25)
    assert len(files) == 3
    assert files[0].name == "Test Playlist_part001.txt"
    assert files[1].name == "Test Playlist_part002.txt"
    assert files[2].name == "Test Playlist_part003.txt"

    lines_part1 = files[0].read_text().strip().split("\n")
    assert len(lines_part1) == 50

    lines_part3 = files[2].read_text().strip().split("\n")
    assert len(lines_part3) == 25
