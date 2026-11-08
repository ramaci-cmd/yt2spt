"""Export URI Spotify ke file teks berformat blok-N."""
from __future__ import annotations

import re
from pathlib import Path

_URI_RE = re.compile(r"^spotify:track:[A-Za-z0-9]{22}$")


def validate_uri(uri: str) -> bool:
    return bool(_URI_RE.match(uri))


def write_uri_blocks(
    playlist_title: str,
    uris: list[str],
    output_dir: Path,
    chunk_size: int = 50,
    dedup: bool = False,
) -> list[Path]:
    """
    Tulis URI ke file teks, pecah per chunk_size.
    Return list file yang dibuat.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize nama file
    safe_title = re.sub(r'[\\/:*?"<>|]', "_", playlist_title).strip()

    # Optional dedup (jaga urutan)
    if dedup:
        seen: set[str] = set()
        deduped: list[str] = []
        for u in uris:
            if u not in seen:
                seen.add(u)
                deduped.append(u)
        uris = deduped

    # Validasi
    valid_uris = [u for u in uris if validate_uri(u)]
    invalid_count = len(uris) - len(valid_uris)

    files: list[Path] = []
    for i, start in enumerate(range(0, len(valid_uris), chunk_size), 1):
        chunk = valid_uris[start : start + chunk_size]
        filename = output_dir / f"{safe_title}_part{i:03d}.txt"
        filename.write_text("\n".join(chunk) + "\n", encoding="utf-8")
        files.append(filename)

    return files
