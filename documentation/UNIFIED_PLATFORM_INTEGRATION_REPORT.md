# UNIFIED BIDIRECTIONAL MUSIC MIGRATION PLATFORM
## Integration Audit, System Architecture, & Backward Compatibility Report

**Codebase:** `yt2sp` (YouTube Music ⇄ Spotify Bidirectional Platform)  
**Date:** 2026-11-17  
**Status:** FULLY INTEGRATED & VERIFIED (34/34 Tests Passed)  

---

## 1. PHASE 1 — INTEGRATION AUDIT

### Background & Conflict Analysis
Prior to integration, the codebase had undergone an initial directional pivot where the legacy YouTube Music → Spotify components were replaced with Spotify → YouTube Music components. This introduced three fundamental conflicts:
1. **Directional Monopoly:** The extraction and resolution pipelines were hardcoded for a single direction, meaning YouTube Music extraction and Spotify search were dormant or bypassed.
2. **Interface Contract Defects:**
   * In `spotify_extract.py:116`: Extraction crashed when reading `playlist.owner.display_name` due to `spotify_scraper.UserRef` lacking `.display_name`.
   * In `ytm_writer.py:34`: `check_ytm_auth` returned a bare `bool`, while `server.py` and `cli.py` expected `(auth_ok, auth_err)`, causing unpack failures.
   * In `ytm_writer.py:110`: `create_and_populate_ytm_playlist` expected `video_ids: list[str]`, but callers passed keyword `track_ids=...`.
   * In `cli.py:113`: Interactive setup attempted to call `YTMusic.setup(...)`, which does not exist as a class method (it is a module-level function `ytmusicapi.setup`).
3. **Database Provider Ambiguity:** Existing SQLite tables did not reliably store source and destination metadata for legacy playlists vs newly imported Spotify playlists.

---

## 2. PHASE 2 — ARCHITECTURE UNIFICATION

### Core Architecture
A single, unified application foundation was established to serve both migration flows seamlessly:

```
                      ┌──────────────────────────────────────┐
                      │    Unified Input & Direction Router  │
                      │   (Auto-detects URL or Toggle Pill)  │
                      └──────────────────┬───────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
       [YouTube Music Source]                            [Spotify Source]
       yt2sp.ytm.extract                                 yt2sp.sources.spotify_extract
                 │                                               │
                 └───────────────────────┬───────────────────────┘
                                         ▼
                      ┌──────────────────────────────────────┐
                      │    Provider-Aware SQLite Layer (WAL) │
                      │  Tracks: source_provider ('yt'/'sp') │
                      │  Playlists: source & destination     │
                      │  Matches: dest_id & spotify_id alias │
                      └──────────────────┬───────────────────┘
                                         │
                                         ▼
                      ┌──────────────────────────────────────┐
                      │     Unified Shared Matching Engine   │
                      │     RapidFuzz + Duration Penalties   │
                      │     Distinctive Marker Filtering     │
                      └──────────────────┬───────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
     [To Spotify Destination]                        [To YTM Destination]
     yt2sp.resolve.spotify_resolver                  yt2sp.destinations.ytm_resolver
     yt2sp.resolve.deezer_resolver (T2 fallback)     yt2sp.destinations.ytm_writer
     yt2sp.export.writer (URI blocks)                ytmusicapi batch population
```

### Module Refinements
1. **`yt2sp/destinations/ytm_writer.py`**:
   * Introduced `AuthResult(tuple)`: Evaluates cleanly as `bool(res)` for boolean checks AND unpacks as `auth_ok, auth_err` for dual-variable assignments.
   * Parameter Normalization: `create_and_populate_ytm_playlist` now accepts `video_ids: list[str] | None = None` and `track_ids: list[str] | None = None`.
2. **`yt2sp/sources/spotify_extract.py`**:
   * Safe owner lookup: `(getattr(playlist.owner, 'name', None) or getattr(playlist.owner, 'display_name', None) or "") if playlist.owner else ""`.
   * Stricter URL sanitizer: Excludes YouTube playlist IDs and links from being misclassified as Spotify base62 IDs.
3. **`yt2sp/cli.py`**:
   * Fixed `from ytmusicapi import setup as ytm_setup; ytm_setup(filepath=...)`.
   * Added auto-detection and destination provider awareness to `extract`, `resolve`, and `export`.

---

## 3. PHASE 3 — FEATURE INTEGRATION

### Bidirectional Resolution (`yt2sp/resolve/pipeline.py`)
`run_resolve` now detects target destination on a per-playlist or per-track basis:
* If target destination is **YouTube Music**:
  * Calls `search_ytm_tracks(title, artists, top_n=5)`.
  * Computes RapidFuzz scores and duration penalties.
  * Employs single-artist fallback search if initial query yields low scores.
  * Records `dest_id` and `spotify_id` as the YouTube video ID.
* If target destination is **Spotify**:
  * Calls `search_spotify(title, artists, top_n=5)`.
  * Computes RapidFuzz scores and duration penalties.
  * Employs Deezer ISRC fallback (`search_deezer`) for missing or ambiguous tracks.
  * Records `dest_id` and `spotify_id` as the Spotify track ID.

### Unified Review Studio Backend
* **Alternatives (`/api/alternatives`)**:
  * If the track source is Spotify, searches YouTube Music candidates via `find_ytm_alternative_versions`.
  * If the track source is YouTube, searches Spotify candidates via `find_alternative_versions`.
  * Returns candidates with normalized badges (`amber`, `purple`, `blue`), duration deltas, and similarity scores.
* **Audio Preview (`/api/preview`)**:
  * Seamlessly queries Deezer CDN (MP3) and Apple iTunes Search API (M4A) for 30-second playable snippets across both platforms.
* **Manual Overrides (`/api/review`)**:
  * Accepts either 11-character YouTube video IDs or 22-character Spotify track IDs / URLs, fetching oEmbed metadata automatically.

---

## 4. PHASE 4 — UI/UX INTEGRATION

### Design Continuity & Zero Disruption
* **Layout & Palette**: Maintained the exact warm cream and dark nature editorial design system (`#F2F1EC`, `#183327`, `#121614`).
* **Migration Direction Selector**:
  * Placed intuitive pill toggles above the playlist extraction bar:
    * `[ YouTube Music → Spotify ]` (Classic)
    * `[ Spotify → YouTube Music ]` (New)
  * Clicking either pill dynamically updates the placeholder, button text, and instructions.
  * **Zero-Friction Auto-Detection**: Pasting a Spotify URL automatically switches the direction to `Spotify → YouTube Music`; pasting a YouTube/YTM URL automatically switches to `YouTube Music → Spotify`.
* **Playlist Library Catalog**:
  * Every playlist card displays a clean provider badge: `YTM → Spotify` or `Spotify → YTM`.
* **Export Actions**:
  * Step 5 and the Review Studio dynamically display the appropriate export actions:
    * "Buat Playlist di YouTube Music" for YTM destinations.
    * "Salin Semua URI Spotify" and "Salin per Bagian (50 Lagu)" for Spotify destinations.
    * "Export File (.txt & CSV Report)" for local file creation.
* **Non-Intrusive Feature Announcement**:
  * An elegant, dismissible banner informs existing users: *"Pengalaman migrasi musik Anda semakin lengkap. Sekarang mendukung transfer playlist dua arah (YouTube Music ⇄ Spotify)."* The dismissal state is permanently remembered in `localStorage`.

---

## 5. PHASE 5 — BACKWARD COMPATIBILITY

### Database Schema Migration
* Executed defensively using `ALTER TABLE ... ADD COLUMN ...` wrapped in try/except blocks.
* Added columns:
  * `playlists.source_provider` (Default: `'youtube'`)
  * `playlists.destination_provider` (Default: `'spotify'`)
  * `playlists.description`
  * `playlists.thumbnail_url`
  * `tracks.source_provider` (Default: `'youtube'`)
  * `tracks.isrc`
  * `tracks.thumbnail_url`
  * `tracks.preview_url`
  * `matches.dest_id`
  * `matches.result_url`
  * `matches.result_thumbnail`
* Auto-sanitization ensures that existing playlists from legacy installations retain their original YouTube Music identity without manual migration scripts.

---

## 6. PHASE 6 — REGRESSION TESTING

### Automated Test Suite Execution (Pytest)
```
============================= test session starts =============================
platform win32 -- Python 3.14.2, pytest-9.2.0, pluggy-1.7.0
rootdir: ...\generate_technical_documentation
collected 34 items

tests/test_bidirectional.py::test_scenario_a_legacy_database_migration PASSED [  2%]
tests/test_bidirectional.py::test_scenario_b_legacy_yt_to_spotify_workflow PASSED [  5%]
tests/test_bidirectional.py::test_scenario_c_new_spotify_to_ytm_workflow PASSED [  8%]
tests/test_bidirectional.py::test_auth_result_contract PASSED            [ 11%]
tests/test_bidirectional.py::test_url_auto_detection PASSED              [ 14%]
tests/test_db.py::test_db_operations PASSED                              [ 17%]
tests/test_export.py::test_validate_uri PASSED                           [ 20%]
tests/test_export.py::test_write_uri_blocks PASSED                       [ 23%]
tests/test_genre.py::test_clean_track_query PASSED                       [ 26%]
tests/test_genre.py::test_detect_genre_heuristic PASSED                  [ 29%]
tests/test_genre.py::test_validate_and_reconcile_agreement PASSED        [ 32%]
tests/test_genre.py::test_validate_and_reconcile_specificity PASSED      [ 35%]
tests/test_genre.py::test_validate_single_source PASSED                  [ 38%]
tests/test_genre.py::test_validate_heuristic_fallback PASSED             [ 41%]
tests/test_genre.py::test_fetch_genre_validated_with_mocks PASSED        [ 44%]
tests/test_normalize.py::test_normalize_strips_noise PASSED              [ 47%]
tests/test_normalize.py::test_normalize_preserves_distinctive_markers PASSED [ 50%]
tests/test_normalize.py::test_has_distinctive_marker PASSED              [ 52%]
tests/test_normalize.py::test_normalize_artist PASSED                    [ 55%]
tests/test_resolve.py::test_spotify_client_singleton_and_reset PASSED    [ 58%]
tests/test_resolve.py::test_resolve_spotify_from_isrc_musicbrainz PASSED [ 61%]
tests/test_resolve.py::test_resolve_spotify_from_isrc_fallback PASSED    [ 64%]
tests/test_score.py::test_exact_match PASSED                             [ 67%]
tests/test_score.py::test_distinctive_marker_penalty PASSED              [ 70%]
tests/test_score.py::test_classify_thresholds PASSED                     [ 73%]
tests/test_score.py::test_duration_tolerance PASSED                      [ 76%]
tests/test_server_endpoints.py::test_ytm_auth_status_endpoint PASSED     [ 79%]
tests/test_server_endpoints.py::test_export_ytm_unauthenticated PASSED   [ 82%]
tests/test_server_endpoints.py::test_review_manual_ytm_video_id PASSED   [ 85%]
tests/test_spotify_extract.py::test_clean_spotify_playlist_id PASSED     [ 88%]
tests/test_spotify_extract.py::test_extract_spotify_playlist_mocked PASSED [ 91%]
tests/test_ytm_resolver.py::test_search_ytm_tracks_mocked PASSED         [ 94%]
tests/test_ytm_resolver.py::test_find_ytm_alternative_versions_mocked PASSED [ 97%]
tests/test_ytm_writer.py::test_create_and_populate_ytm_playlist_mocked PASSED [100%]

============================= 34 passed in 3.56s ==============================
```

---

## 7. PHASE 7 — UPDATE VALIDATION (SIMULATED UPGRADE)

### Verification of Existing User Migration
1. **Database Upgrade Simulation (`test_scenario_a_legacy_database_migration`)**:
   * A legacy database containing historical playlists, tracks, and matches was opened with the updated runtime.
   * `db.init_db()` safely created new nullable columns and auto-classified existing entries as `source_provider='youtube'` and `destination_provider='spotify'`.
   * Historical tracks, accepted statuses, and Spotify match IDs remained 100% accessible and queryable.
2. **Live Public Extraction Verification**:
   * Executed live extraction of public playlist `37i9dQZF1DXcBWIGoYBM5M`:
     * Result: Successfully fetched 5 tracks with title, artists, duration, and owner `"Spotify"` without encountering `AttributeError`.
3. **Live Public Matching Verification**:
   * Verified RapidFuzz token matching, duration penalties, and alternative candidate lookups against real YouTube Music endpoints.

### Summary
The platform has achieved seamless bidirectional harmony without discarding or fragmenting legacy code. Existing users will experience zero friction, while gaining direct access to reverse Spotify → YouTube Music migration.
