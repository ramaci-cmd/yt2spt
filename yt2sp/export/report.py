"""Export laporan CSV per playlist."""
from __future__ import annotations

import csv
import json
import urllib.parse
from pathlib import Path


def write_csv_report(
    playlist_title: str,
    tracks: list,  # list of sqlite3.Row
    output_dir: Path,
) -> Path:
    """
    Tulis laporan CSV.
    Kolom: position, video_id, yt_title, yt_artists, yt_duration_s,
           status, tier, score, spotify_id, reason, search_link
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_title = playlist_title.replace("/", "_").replace("\\", "_")
    out_path = output_dir / f"{safe_title}_report.csv"

    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "position", "video_id", "yt_title", "yt_artists", "yt_duration_s",
            "status", "tier", "score", "spotify_id", "reason", "search_link",
        ])
        for t in tracks:
            artists = json.loads(t["artists"]) if t["artists"] else []
            duration_s = round((t["duration_ms"] or 0) / 1000)
            query = urllib.parse.quote(f"{t['title']} {' '.join(artists)}")
            search_link = f"https://open.spotify.com/search/{query}"
            writer.writerow([
                t["position"],
                t["video_id"],
                t["title"],
                ", ".join(artists),
                duration_s,
                t["status"] or "pending",
                t["tier"] or "",
                f"{t['score']:.3f}" if t["score"] is not None else "",
                t["spotify_id"] or "",
                t["reason"] or "",
                search_link,
            ])
    return out_path
