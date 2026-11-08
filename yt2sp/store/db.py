"""SQLite database layer – semua state disimpan di sini (WAL mode)."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path("yt2sp.db")

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """Return per-thread connection with high-performance PRAGMAs."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA synchronous=NORMAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
        _local.conn.execute("PRAGMA cache_size=-64000")  # 64MB page cache in RAM
        _local.conn.execute("PRAGMA temp_store=MEMORY")  # in-memory temp tables and sorting
        _local.conn.execute("PRAGMA mmap_size=268435456")  # 256MB memory-mapped I/O
    return _local.conn


def init_db(db_path: Path | None = None) -> None:
    """Buat tabel jika belum ada."""
    global DB_PATH
    if db_path:
        DB_PATH = db_path
    conn = _get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS playlists (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            yt_playlist_id  TEXT UNIQUE NOT NULL,
            title           TEXT,
            track_count     INTEGER,
            unavailable_count INTEGER DEFAULT 0,
            extracted_at    TEXT
        );

        CREATE TABLE IF NOT EXISTS tracks (
            video_id    TEXT PRIMARY KEY,
            title       TEXT,
            artists     TEXT,   -- JSON array of strings
            album       TEXT,
            duration_ms INTEGER,
            video_type  TEXT,
            genre       TEXT
        );

        CREATE TABLE IF NOT EXISTS playlist_tracks (
            playlist_id INTEGER NOT NULL REFERENCES playlists(id),
            video_id    TEXT    NOT NULL REFERENCES tracks(video_id),
            position    INTEGER NOT NULL,
            PRIMARY KEY (playlist_id, video_id)
        );

        CREATE TABLE IF NOT EXISTS matches (
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

        CREATE TABLE IF NOT EXISTS api_cache (
            key         TEXT PRIMARY KEY,
            response_json TEXT,
            http_status INTEGER,
            cached_at   TEXT
        );

        CREATE TABLE IF NOT EXISTS runs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at  TEXT,
            finished_at TEXT,
            summary     TEXT
        );

        CREATE TABLE IF NOT EXISTS golden (
            video_id        TEXT PRIMARY KEY,
            spotify_id_human TEXT,
            notes           TEXT
        );

        -- Performance Indexes
        CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);
        CREATE INDEX IF NOT EXISTS idx_matches_status_spid ON matches(status, spotify_id);
        CREATE INDEX IF NOT EXISTS idx_matches_spid ON matches(spotify_id);
        CREATE INDEX IF NOT EXISTS idx_pt_playlist ON playlist_tracks(playlist_id);
        CREATE INDEX IF NOT EXISTS idx_pt_video ON playlist_tracks(video_id);
        CREATE INDEX IF NOT EXISTS idx_tracks_genre ON tracks(genre);
        CREATE INDEX IF NOT EXISTS idx_api_cache_key ON api_cache(key);
        """
    )
    try:
        conn.execute("ALTER TABLE tracks ADD COLUMN genre TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE playlists ADD COLUMN unavailable_count INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE tracks ADD COLUMN genre_source TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Playlist ──────────────────────────────────────────────────────────────────

def upsert_playlist(yt_playlist_id: str, title: str, track_count: int, unavailable_count: int = 0) -> int:
    conn = _get_conn()
    conn.execute(
        """
        INSERT INTO playlists (yt_playlist_id, title, track_count, unavailable_count, extracted_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(yt_playlist_id) DO UPDATE SET
            title=excluded.title,
            track_count=excluded.track_count,
            unavailable_count=excluded.unavailable_count,
            extracted_at=excluded.extracted_at
        """,
        (yt_playlist_id, title, track_count, unavailable_count, now_iso()),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM playlists WHERE yt_playlist_id=?", (yt_playlist_id,)
    ).fetchone()
    return row["id"]


def get_all_playlists() -> list[sqlite3.Row]:
    return _get_conn().execute("SELECT * FROM playlists ORDER BY id").fetchall()


def get_playlist_by_ytid(yt_playlist_id: str) -> sqlite3.Row | None:
    return _get_conn().execute(
        "SELECT * FROM playlists WHERE yt_playlist_id=?", (yt_playlist_id,)
    ).fetchone()


# ── Track ─────────────────────────────────────────────────────────────────────

def upsert_track(
    video_id: str,
    title: str,
    artists: list[str],
    album: str,
    duration_ms: int,
    video_type: str,
) -> None:
    conn = _get_conn()
    conn.execute(
        """
        INSERT INTO tracks (video_id, title, artists, album, duration_ms, video_type)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(video_id) DO NOTHING
        """,
        (video_id, title, json.dumps(artists, ensure_ascii=False), album, duration_ms, video_type),
    )
    conn.commit()


def get_track(video_id: str) -> sqlite3.Row | None:
    """Return single track by video_id."""
    return _get_conn().execute(
        "SELECT * FROM tracks WHERE video_id=?", (video_id,)
    ).fetchone()


def upsert_playlist_track(playlist_id: int, video_id: str, position: int) -> None:
    conn = _get_conn()
    conn.execute(
        """
        INSERT INTO playlist_tracks (playlist_id, video_id, position)
        VALUES (?, ?, ?)
        ON CONFLICT(playlist_id, video_id) DO UPDATE SET position=excluded.position
        """,
        (playlist_id, video_id, position),
    )
    conn.commit()


def get_playlist_tracks(playlist_id: int) -> list[sqlite3.Row]:
    """Return tracks+matches for a playlist in order."""
    return _get_conn().execute(
        """
        SELECT t.*, pt.position, m.spotify_id, m.status, m.score, m.tier, m.reason,
               m.result_title, m.result_artist
        FROM playlist_tracks pt
        JOIN tracks t ON t.video_id = pt.video_id
        LEFT JOIN matches m ON m.video_id = pt.video_id
        WHERE pt.playlist_id = ?
        ORDER BY pt.position
        """,
        (playlist_id,),
    ).fetchall()


def get_all_library_tracks() -> list[sqlite3.Row]:
    """Return all unique tracks across the entire library with match info and playlist names."""
    return _get_conn().execute(
        """
        SELECT t.*,
               COALESCE(MIN(pt.position), 0) as position,
               m.spotify_id, m.status, m.score, m.tier, m.reason,
               m.result_title, m.result_artist,
               GROUP_CONCAT(DISTINCT p.title) as in_playlists
        FROM tracks t
        LEFT JOIN matches m ON m.video_id = t.video_id
        LEFT JOIN playlist_tracks pt ON pt.video_id = t.video_id
        LEFT JOIN playlists p ON p.id = pt.playlist_id
        GROUP BY t.video_id
        ORDER BY t.rowid DESC
        """
    ).fetchall()


# ── Match ─────────────────────────────────────────────────────────────────────

def init_match(video_id: str) -> None:
    """Buat baris match dengan status pending jika belum ada."""
    conn = _get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO matches (video_id, status, updated_at) VALUES (?, 'pending', ?)",
        (video_id, now_iso()),
    )
    conn.commit()


def set_match(
    video_id: str,
    *,
    spotify_id: str | None,
    tier: str,
    score: float,
    status: str,
    result_title: str = "",
    result_artist: str = "",
    decided_by: str = "auto",
    reason: str = "",
) -> None:
    conn = _get_conn()
    conn.execute(
        """
        INSERT INTO matches
            (video_id, spotify_id, tier, score, status, result_title, result_artist,
             decided_by, reason, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(video_id) DO UPDATE SET
            spotify_id=excluded.spotify_id,
            tier=excluded.tier,
            score=excluded.score,
            status=excluded.status,
            result_title=excluded.result_title,
            result_artist=excluded.result_artist,
            decided_by=excluded.decided_by,
            reason=excluded.reason,
            updated_at=excluded.updated_at
        """,
        (
            video_id, spotify_id, tier, score, status,
            result_title, result_artist, decided_by, reason, now_iso(),
        ),
    )
    conn.commit()


def get_match(video_id: str) -> sqlite3.Row | None:
    return _get_conn().execute(
        "SELECT * FROM matches WHERE video_id=?", (video_id,)
    ).fetchone()


def get_pending_tracks(playlist_id: int | None = None) -> list[sqlite3.Row]:
    """Tracks yang belum punya match final."""
    if playlist_id is not None:
        return _get_conn().execute(
            """
            SELECT t.*
            FROM playlist_tracks pt
            JOIN tracks t ON t.video_id = pt.video_id
            LEFT JOIN matches m ON m.video_id = t.video_id
            WHERE pt.playlist_id = ?
              AND (m.video_id IS NULL OR m.status = 'pending')
            ORDER BY pt.position
            """,
            (playlist_id,),
        ).fetchall()
    return _get_conn().execute(
        """
        SELECT t.*
        FROM tracks t
        LEFT JOIN matches m ON m.video_id = t.video_id
        WHERE m.video_id IS NULL
           OR m.status = 'pending'
        ORDER BY t.video_id
        """
    ).fetchall()


def reset_unresolved_tracks_to_pending(playlist_id: int | None = None, reset_all: bool = False) -> int:
    """Reset status match ke pending untuk lagu yang belum accepted atau auto."""
    conn = _get_conn()
    if playlist_id is not None:
        if reset_all:
            cur = conn.execute(
                """
                UPDATE matches
                SET status = 'pending'
                WHERE video_id IN (SELECT video_id FROM playlist_tracks WHERE playlist_id=?)
                """,
                (playlist_id,),
            )
        else:
            cur = conn.execute(
                """
                UPDATE matches
                SET status = 'pending'
                WHERE video_id IN (SELECT video_id FROM playlist_tracks WHERE playlist_id=?)
                  AND status NOT IN ('accepted', 'resolved_auto')
                """,
                (playlist_id,),
            )
    else:
        if reset_all:
            cur = conn.execute("UPDATE matches SET status = 'pending'")
        else:
            cur = conn.execute("UPDATE matches SET status = 'pending' WHERE status NOT IN ('accepted', 'resolved_auto')")
    conn.commit()
    return cur.rowcount



def get_review_tracks() -> list[sqlite3.Row]:
    """Tracks yang butuh review manual."""
    return _get_conn().execute(
        """
        SELECT t.*, m.spotify_id, m.score, m.tier, m.result_title, m.result_artist, m.reason
        FROM matches m
        JOIN tracks t ON t.video_id = m.video_id
        WHERE m.status = 'needs_review'
        ORDER BY m.score DESC
        """
    ).fetchall()


def get_missing_tracks(playlist_id: int | None = None) -> list[sqlite3.Row]:
    """Lagu yang sudah dicari tapi gagal, ditolak, atau butuh review (BUKAN yang masih pending/antrean)."""
    conn = _get_conn()
    if playlist_id:
        return conn.execute(
            """
            SELECT t.*, pt.position, m.spotify_id, m.status, m.score, m.reason, m.result_title, m.result_artist
            FROM playlist_tracks pt
            JOIN tracks t ON t.video_id = pt.video_id
            JOIN matches m ON m.video_id = pt.video_id
            WHERE pt.playlist_id = ?
              AND m.status IN ('failed', 'rejected', 'needs_review')
            ORDER BY pt.position
            """,
            (playlist_id,),
        ).fetchall()
    return conn.execute(
        """
        SELECT t.*, m.spotify_id, m.status, m.score, m.reason, m.result_title, m.result_artist
        FROM tracks t
        JOIN matches m ON m.video_id = t.video_id
        WHERE m.status IN ('failed', 'rejected', 'needs_review')
        ORDER BY t.video_id
        """
    ).fetchall()


def get_status_summary() -> dict[str, Any]:
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
    by_status: dict[str, int] = {}
    for row in conn.execute(
        "SELECT status, COUNT(*) as n FROM matches GROUP BY status"
    ).fetchall():
        by_status[row["status"]] = row["n"]
    pending = total - sum(by_status.values())
    return {
        "total": total,
        "pending": pending,
        "resolved_auto": by_status.get("resolved_auto", 0),
        "needs_review": by_status.get("needs_review", 0),
        "accepted": by_status.get("accepted", 0),
        "rejected": by_status.get("rejected", 0),
        "failed": by_status.get("failed", 0),
        "skipped": by_status.get("skipped", 0),
    }


# ── API Cache ─────────────────────────────────────────────────────────────────

def get_cache(key: str) -> dict | None:
    row = _get_conn().execute(
        "SELECT response_json FROM api_cache WHERE key=?", (key,)
    ).fetchone()
    if row:
        return json.loads(row["response_json"])
    return None


def set_cache(key: str, data: dict, http_status: int = 200) -> None:
    conn = _get_conn()
    conn.execute(
        """
        INSERT INTO api_cache (key, response_json, http_status, cached_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            response_json=excluded.response_json,
            http_status=excluded.http_status,
            cached_at=excluded.cached_at
        """,
        (key, json.dumps(data, ensure_ascii=False), http_status, now_iso()),
    )
    conn.commit()


# ── Golden Set ────────────────────────────────────────────────────────────────

def upsert_golden(video_id: str, spotify_id_human: str, notes: str = "") -> None:
    conn = _get_conn()
    conn.execute(
        """
        INSERT INTO golden (video_id, spotify_id_human, notes)
        VALUES (?, ?, ?)
        ON CONFLICT(video_id) DO UPDATE SET
            spotify_id_human=excluded.spotify_id_human,
            notes=excluded.notes
        """,
        (video_id, spotify_id_human, notes),
    )
    conn.commit()


def get_golden_set() -> list[sqlite3.Row]:
    return _get_conn().execute(
        """
        SELECT g.*, m.spotify_id as matched_id, m.status, m.score
        FROM golden g
        LEFT JOIN matches m ON m.video_id = g.video_id
        """
    ).fetchall()


# ── Genre & Categorization ───────────────────────────────────────────────────

def update_track_genre(video_id: str, genre: str, source: str | None = None) -> None:
    conn = _get_conn()
    if source:
        conn.execute("UPDATE tracks SET genre=?, genre_source=? WHERE video_id=?", (genre, source, video_id))
    else:
        conn.execute("UPDATE tracks SET genre=? WHERE video_id=?", (genre, video_id))
    conn.commit()


def get_tracks_without_genre(include_uncategorized: bool = True) -> list[sqlite3.Row]:
    """Lagu yang belum memiliki genre (atau berstatus Uncategorized)."""
    if include_uncategorized:
        return _get_conn().execute(
            """
            SELECT t.*, m.result_title, m.result_artist
            FROM tracks t
            LEFT JOIN matches m ON m.video_id = t.video_id
            WHERE t.genre IS NULL OR t.genre = '' OR t.genre = 'Uncategorized'
            """
        ).fetchall()
    return _get_conn().execute(
        """
        SELECT t.*, m.result_title, m.result_artist
        FROM tracks t
        LEFT JOIN matches m ON m.video_id = t.video_id
        WHERE t.genre IS NULL OR t.genre = ''
        """
    ).fetchall()


def get_playlist_genres(playlist_id: int) -> list[sqlite3.Row]:
    """Hitung jumlah lagu per genre dalam suatu playlist."""
    return _get_conn().execute(
        """
        SELECT COALESCE(t.genre, 'Uncategorized') as genre, COUNT(*) as track_count
        FROM playlist_tracks pt
        JOIN tracks t ON t.video_id = pt.video_id
        LEFT JOIN matches m ON m.video_id = pt.video_id
        WHERE pt.playlist_id = ?
        GROUP BY genre
        ORDER BY track_count DESC
        """,
        (playlist_id,),
    ).fetchall()


def get_playlist_tracks_for_genre(playlist_id: int, genre: str) -> list[sqlite3.Row]:
    """Ambil lagu dalam playlist untuk genre tertentu."""
    return _get_conn().execute(
        """
        SELECT t.*, pt.position, m.spotify_id, m.status, m.score, m.tier, m.reason
        FROM playlist_tracks pt
        JOIN tracks t ON t.video_id = pt.video_id
        LEFT JOIN matches m ON m.video_id = pt.video_id
        WHERE pt.playlist_id = ?
          AND LOWER(TRIM(COALESCE(t.genre, 'Uncategorized'))) = LOWER(TRIM(?))
        ORDER BY pt.position
        """,
        (playlist_id, genre),
    ).fetchall()


def get_all_library_genres() -> list[sqlite3.Row]:
    """Hitung jumlah lagu per genre di seluruh database."""
    return _get_conn().execute(
        """
        SELECT COALESCE(t.genre, 'Uncategorized') as genre, COUNT(DISTINCT t.video_id) as track_count
        FROM tracks t
        GROUP BY genre
        ORDER BY track_count DESC
        """
    ).fetchall()


def get_all_library_tracks_for_genre(genre: str) -> list[sqlite3.Row]:
    """Ambil lagu di seluruh database untuk genre tertentu."""
    return _get_conn().execute(
        """
        SELECT t.*,
               COALESCE(MIN(pt.position), 0) as position,
               m.spotify_id, m.status, m.score, m.tier, m.reason,
               GROUP_CONCAT(DISTINCT p.title) as in_playlists
        FROM tracks t
        LEFT JOIN matches m ON m.video_id = t.video_id
        LEFT JOIN playlist_tracks pt ON pt.video_id = t.video_id
        LEFT JOIN playlists p ON p.id = pt.playlist_id
        WHERE LOWER(TRIM(COALESCE(t.genre, 'Uncategorized'))) = LOWER(TRIM(?))
        GROUP BY t.video_id
        ORDER BY t.rowid DESC
        """,
        (genre,),
    ).fetchall()


# ── Reset / Hapus Data ────────────────────────────────────────────────────────

def reset_all_data(clear_cache: bool = False) -> None:
    """Hapus semua data playlist, track, matches, dan runs untuk mulai dari nol."""
    conn = _get_conn()
    conn.execute("DELETE FROM matches")
    conn.execute("DELETE FROM playlist_tracks")
    conn.execute("DELETE FROM tracks")
    conn.execute("DELETE FROM playlists")
    conn.execute("DELETE FROM runs")
    if clear_cache:
        conn.execute("DELETE FROM api_cache")
    conn.commit()
    try:
        conn.execute("VACUUM")
    except Exception:
        pass


def delete_playlist(playlist_id: int) -> None:
    """Hapus satu playlist beserta tracks yang tidak lagi terhubung ke playlist manapun."""
    delete_playlists([playlist_id])


def delete_playlists(playlist_ids: list[int]) -> int:
    """Hapus sejumlah playlist sekaligus dari database."""
    if not playlist_ids:
        return 0
    conn = _get_conn()
    placeholders = ",".join("?" for _ in playlist_ids)
    conn.execute(f"DELETE FROM playlist_tracks WHERE playlist_id IN ({placeholders})", playlist_ids)
    conn.execute(f"DELETE FROM playlists WHERE id IN ({placeholders})", playlist_ids)
    # Hapus tracks & matches yatim (orphan)
    conn.execute(
        "DELETE FROM matches WHERE video_id NOT IN (SELECT video_id FROM playlist_tracks)"
    )
    conn.execute(
        "DELETE FROM tracks WHERE video_id NOT IN (SELECT video_id FROM playlist_tracks)"
    )
    conn.commit()
    try:
        conn.execute("VACUUM")
    except Exception:
        pass
    return len(playlist_ids)


def delete_track(video_id: str, playlist_id: int | None = None) -> None:
    """Hapus satu lagu dari playlist tertentu atau dari seluruh database."""
    delete_tracks([video_id], playlist_id)


def delete_tracks(video_ids: list[str], playlist_id: int | None = None) -> int:
    """Hapus sejumlah lagu sekaligus dari playlist tertentu atau dari seluruh database."""
    if not video_ids:
        return 0
    conn = _get_conn()
    placeholders = ",".join("?" for _ in video_ids)
    if playlist_id is not None:
        conn.execute(
            f"DELETE FROM playlist_tracks WHERE playlist_id=? AND video_id IN ({placeholders})",
            [playlist_id, *video_ids],
        )
        conn.execute(
            "UPDATE playlists SET track_count = (SELECT COUNT(*) FROM playlist_tracks WHERE playlist_id=?) WHERE id=?",
            (playlist_id, playlist_id),
        )
        # Hapus matches dan tracks jika tidak ada lagi di playlist manapun
        conn.execute(
            "DELETE FROM matches WHERE video_id NOT IN (SELECT video_id FROM playlist_tracks)"
        )
        conn.execute(
            "DELETE FROM tracks WHERE video_id NOT IN (SELECT video_id FROM playlist_tracks)"
        )
    else:
        affected_playlists = [
            row[0]
            for row in conn.execute(
                f"SELECT DISTINCT playlist_id FROM playlist_tracks WHERE video_id IN ({placeholders})",
                video_ids,
            ).fetchall()
        ]
        conn.execute(f"DELETE FROM playlist_tracks WHERE video_id IN ({placeholders})", video_ids)
        conn.execute(f"DELETE FROM matches WHERE video_id IN ({placeholders})", video_ids)
        conn.execute(f"DELETE FROM tracks WHERE video_id IN ({placeholders})", video_ids)
        for pid in affected_playlists:
            conn.execute(
                "UPDATE playlists SET track_count = (SELECT COUNT(*) FROM playlist_tracks WHERE playlist_id=?) WHERE id=?",
                (pid, pid),
            )
    conn.commit()
    try:
        conn.execute("VACUUM")
    except Exception:
        pass
    return len(video_ids)

