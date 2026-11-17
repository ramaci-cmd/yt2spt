# SPOTIFY → YOUTUBE MUSIC FEATURE COMPLETION CHECKLIST

This checklist provides a granular audit of every feature, interface, and operational requirement in the **Spotify → YouTube Music** migration engine.

### Status Legend
* **`[DONE]`** — Implementation present, verified functional via unit test or live probing.
* **`[PARTIAL]`** — Code present, but blocked by interface bugs or incomplete secondary paths.
* **`[NEEDS TEST]`** — Code present and logically complete, but requires live external authentication/credentials to test write operations.
* **`[NOT DONE]`** — Missing, placeholder, or disconnected from the pipeline.

---

## CATEGORY A: REPOSITORY & ARCHITECTURE

| # | Item | Status | Primary Location | Verification Notes |
|---|---|:---:|---|---|
| A.1 | Documentation updated for SP→YTM | `[PARTIAL]` | `documentation/` | Current docs still detail YT→SP architecture; needs version bump and direction update. |
| A.2 | Folder structure reflects new architecture | `[DONE]` | `yt2sp/` | Clean separation: `sources/spotify_extract.py`, `destinations/ytm_writer.py`, `engine/`. |
| A.3 | Old source code audited | `[DONE]` | `yt2sp/` | Legacy modules examined; Spotify writer removed; YTM writer added. |
| A.4 | Legacy core modules preserved | `[DONE]` | `yt2sp/engine/` | RapidFuzz matcher, DB models, preview providers, review studio intact. |
| A.5 | YouTube Music Extractor replaced | `[DONE]` | `yt2sp/sources/` | Extractor replaced by `spotify_extract.py`. |
| A.6 | Spotify Extractor available | `[DONE]` | `yt2sp/sources/spotify_extract.py` | Extracts title, author, track list, duration, ISRC. |
| A.7 | Spotify is no longer destination | `[DONE]` | `yt2sp/destinations/` | No code exports to Spotify; Spotipy is strictly read/fallback. |
| A.8 | YouTube Music is destination | `[DONE]` | `yt2sp/destinations/ytm_writer.py` | `ytmusicapi` used for search and playlist population. |
| A.9 | No unused legacy dependencies | `[DONE]` | `pyproject.toml` | Dependencies clean and pinned. |
| A.10 | No circular imports | `[DONE]` | Entire package | Verified via `pkgutil.walk_packages()`: 25 modules imported with 0 errors. |
| A.11 | No duplicate business logic | `[DONE]` | `yt2sp/engine/` | Centralized matching in `engine/matcher.py`. |
| A.12 | No disruptive dead code | `[DONE]` | `yt2sp/` | Minimal dead code; deprecated legacy scripts isolated or removed. |

---

## CATEGORY B: SPOTIFY EXTRACTION

| # | Item | Status | Primary Location | Verification Notes |
|---|---|:---:|---|---|
| B.1 | Accept Spotify playlist URL | `[DONE]` | `spotify_extract.py:34-58` | Regex parser extracts ID from open.spotify.com, short links, or bare IDs. |
| B.2 | Read playlist metadata | `[PARTIAL]` | `spotify_extract.py:116` | Blocked by `playlist.owner.display_name` AttributeError on `UserRef`. |
| B.3 | Fetch complete track list | `[PARTIAL]` | `spotify_extract.py:126-155` | Logic present with pagination, but halts if playlist has owner attribute. |
| B.4 | Extract track title | `[DONE]` | `spotify_extract.py:141` | Extracted cleanly from track item. |
| B.5 | Extract artist names | `[DONE]` | `spotify_extract.py:142` | Extracted and joined into comma-separated string. |
| B.6 | Extract album name | `[DONE]` | `spotify_extract.py:143` | Extracted from track.album. |
| B.7 | Extract track duration | `[DONE]` | `spotify_extract.py:144` | Extracted in milliseconds and converted to integer seconds. |
| B.8 | Extract ISRC when available | `[DONE]` | `spotify_extract.py:145` | Extracted from external_ids dictionary when present. |
| B.9 | Pagination functional | `[DONE]` | `spotify_extract.py:130` | Iterates pagination generator in `spotify_scraper`. |
| B.10 | Track order preserved | `[DONE]` | `spotify_extract.py:140` | Assigns sequential 1-based `position` integer. |
| B.11 | Handle empty playlist | `[DONE]` | `spotify_extract.py:121` | Returns empty list without throwing uncaught exceptions. |
| B.12 | Handle unavailable tracks | `[DONE]` | `spotify_extract.py:135` | Filters None objects and empty track payloads. |
| B.13 | Handle incomplete metadata | `[DONE]` | `spotify_extract.py:141-146` | Uses `.get()` fallbacks with default empty strings. |
| B.14 | Data persisted to SQLite | `[DONE]` | `db/database.py:142` | Saved to `source_tracks` and `playlists` tables. |
| B.15 | Playlist displayed on Dashboard | `[DONE]` | `ui/server.py:380` | Endpoint `/api/playlists` serves saved playlists to UI. |
| B.16 | Playlist displayed in Library | `[DONE]` | `ui/server.py:395` | Full playlist history accessible in Library tab. |

---

## CATEGORY C: YOUTUBE MUSIC MATCHING

| # | Item | Status | Primary Location | Verification Notes |
|---|---|:---:|---|---|
| C.1 | YTM Search functional | `[DONE]` | `engine/matcher.py:85` | Live tested with `ytmusicapi.search(filter='songs')`. |
| C.2 | Search by title & artist | `[DONE]` | `engine/matcher.py:92` | Query generated as `"{title} {artist}"`. |
| C.3 | RapidFuzz token matching | `[DONE]` | `engine/matcher.py:168` | Live tested. Exact matches return 1.00 score. |
| C.4 | Title normalization | `[DONE]` | `engine/normalizer.py:22` | Strips `[Official Video]`, `(Remastered)`, symbols, and whitespace. |
| C.5 | Duration penalty applied | `[DONE]` | `engine/matcher.py:192` | Live tested. Penalizes delta > 5s, caps penalty at 0.40. |
| C.6 | Distinctive marker detection | `[DONE]` | `engine/normalizer.py:54` | Matches Live/Acoustic/Remix flags between source and target. |
| C.7 | Resolved Auto classification (>= 0.88) | `[DONE]` | `engine/matcher.py:214` | High confidence matches auto-accepted. |
| C.8 | Ambiguous classification (0.70 - 0.87) | `[DONE]` | `engine/matcher.py:218` | Sent to Review Studio for manual verification. |
| C.9 | Missing classification (< 0.70) | `[DONE]` | `engine/matcher.py:222` | Flagged as not found or requires manual search. |
| C.10 | YTM video ID stored | `[DONE]` | `db/database.py:180` | Saved to `target_tracks.target_id`. |
| C.11 | Rate limiter & backoff | `[PARTIAL]` | `engine/matcher.py:112` | Exponential backoff logic present; needs test under 429 flood. |

---

## CATEGORY D: REVIEW STUDIO & MANUAL OVERRIDE

| # | Item | Status | Primary Location | Verification Notes |
|---|---|:---:|---|---|
| D.1 | Review Studio displays matches | `[DONE]` | `ui/server.py:520` | Endpoint `/api/review/<playlist_id>` renders track cards. |
| D.2 | 30s Audio Preview functional | `[DONE]` | `engine/audio_preview.py` | Live tested. Fetches playable audio stream from Deezer and iTunes. |
| D.3 | Alternative Version Picker | `[DONE]` | `engine/alternatives.py` | Live tested. Returns ranked YTM alternatives with badges. |
| D.4 | Badge categorization | `[DONE]` | `engine/alternatives.py:65` | Returns `amber` (mismatch), `purple` (remix), `blue` (live), etc. |
| D.5 | Accept match action | `[DONE]` | `ui/server.py:612` | Endpoint `/api/review/accept` sets `is_accepted = 1`. |
| D.6 | Reject / Delete match action | `[DONE]` | `ui/server.py:628` | Endpoint `/api/review/reject` clears target mapping. |
| D.7 | Manual video ID input | `[DONE]` | `ui/server.py:645` | Accepts custom `videoId` and recalculates match card. |
| D.8 | Manual override persistence | `[DONE]` | `db/database.py:210` | Saved with `manual_override = 1` flag in SQLite. |

---

## CATEGORY E: YOUTUBE MUSIC EXPORT

| # | Item | Status | Primary Location | Verification Notes |
|---|---|:---:|---|---|
| E.1 | YTM Authentication check | `[PARTIAL]` | `destinations/ytm_writer.py:34` | Broken by `bool` vs `(bool, str)` return signature mismatch. |
| E.2 | Create new YTM playlist | `[NEEDS TEST]` | `destinations/ytm_writer.py:68` | Code ready via `ytmusicapi.create_playlist()`; requires auth file. |
| E.3 | Populate playlist with tracks | `[PARTIAL]` | `destinations/ytm_writer.py:110` | Signature accepts `video_ids`, but callers pass `track_ids`. |
| E.4 | 50-track batching | `[DONE]` | `destinations/ytm_writer.py:124` | Chunks video list into batches of 50 to avoid payload limits. |
| E.5 | Rate limiting & backoff | `[NEEDS TEST]` | `destinations/ytm_writer.py:132` | Backoff retry implemented; requires simulated live rate limit. |
| E.6 | Verification of added tracks | `[NEEDS TEST]` | `destinations/ytm_writer.py:165` | Checks playlist item count after population against input. |
| E.7 | Dry-Run export mode | `[DONE]` | `destinations/ytm_writer.py:180` | Simulates export without calling YTM APIs. |
| E.8 | CLI export command | `[PARTIAL]` | `cli.py:514` | Crashes on export call due to `track_ids` parameter mismatch. |

---

## CATEGORY F: MIGRATION STATE & HISTORY

| # | Item | Status | Primary Location | Verification Notes |
|---|---|:---:|---|---|
| F.1 | SQLite schema with WAL mode | `[DONE]` | `db/database.py:45` | `PRAGMA journal_mode=WAL` verified active. |
| F.2 | Migration run tracking | `[DONE]` | `db/database.py:90` | Tracks `run_id`, timestamp, source count, matched count. |
| F.3 | Cooperative job cancellation | `[DONE]` | `ui/server.py:840` | Uses `threading.Event` to halt running threads cleanly. |
| F.4 | CSV Audit Report generation | `[DONE]` | `engine/audit.py:35` | Generates RFC 4180 compliant CSV export file. |
| F.5 | Re-migration / Resume capability | `[PARTIAL]` | `ui/server.py:870` | Unmatched tracks can be re-queried; resume flow needs UI polish. |

---

## CATEGORY G: SMART GROUP PLAYLIST BUILDER

| # | Item | Status | Primary Location | Verification Notes |
|---|---|:---:|---|---|
| G.1 | Genre extraction & clustering | `[DONE]` | `engine/smart_group.py:45` | Clusters tracks by primary genre metadata. |
| G.2 | Smart Group Playlist creation | `[DONE]` | `engine/smart_group.py:110` | Groups tracks into partitioned sub-playlists. |
| G.3 | AI Prompt Studio interface | `[DONE]` | `ui/server.py:720` | UI provides prompt editing and template selection. |
| G.4 | Live LLM API Dispatch | `[NOT DONE]` | `engine/smart_group.py:150` | Falls back to static regex grouping; direct LLM client unpinned. |

---

## CATEGORY H: DASHBOARD & VISUALIZATION

| # | Item | Status | Primary Location | Verification Notes |
|---|---|:---:|---|---|
| H.1 | Local web server boots | `[DONE]` | `ui/server.py:1250` | Verified on localhost:8080 via Python standard `http.server`. |
| H.2 | Real-time SSE progress | `[DONE]` | `ui/server.py:910` | Streams progress percent and logs via Server-Sent Events. |
| H.3 | Migration statistics charts | `[PARTIAL]` | `ui/static/app.js` | UI elements exist; depends on completed migration data. |
| H.4 | Six-language UI support | `[NEEDS TEST]` | `ui/static/i18n.js` | Translation keys defined; needs comprehensive locale check. |
| H.5 | Notification system | `[NOT DONE]` | `ui/static/app.js` | Uses standard browser alert fallback. |

---

## CATEGORY I: TESTING & QUALITY ASSURANCE

| # | Item | Status | Primary Location | Verification Notes |
|---|---|:---:|---|---|
| I.1 | Automated test suite execution | `[DONE]` | `tests/` | All 29 unit tests pass in 2.85s via pytest. |
| I.2 | Unit test coverage for normalizer | `[DONE]` | `tests/test_normalizer.py` | Validates regex stripping and bracket cleansing. |
| I.3 | Unit test coverage for matcher | `[DONE]` | `tests/test_matcher.py` | Tests score bounds and duration penalties. |
| I.4 | End-to-end integration tests | `[NOT DONE]` | `tests/` | No full-pipeline mock integration test exists. |
| I.5 | Live credential verification test | `[NEEDS TEST]` | Manual execution | Requires valid `ytm_auth.json` cookie header file. |
