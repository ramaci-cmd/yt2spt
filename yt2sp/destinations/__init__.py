"""Destination package – Modul destinasi & penulisan katalog musik YouTube Music."""
from __future__ import annotations

from yt2sp.destinations.ytm_resolver import (
    YTMTrackCandidate,
    find_ytm_alternative_versions,
    search_ytm_tracks,
)
from yt2sp.destinations.ytm_writer import (
    YTMExportResult,
    check_ytm_auth,
    create_and_populate_ytm_playlist,
    get_authenticated_ytm,
)

__all__ = [
    "YTMTrackCandidate",
    "find_ytm_alternative_versions",
    "search_ytm_tracks",
    "YTMExportResult",
    "check_ytm_auth",
    "create_and_populate_ytm_playlist",
    "get_authenticated_ytm",
]
