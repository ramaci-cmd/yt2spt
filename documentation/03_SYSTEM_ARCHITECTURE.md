# 03. SYSTEM ARCHITECTURE & COMPONENT TOPOLOGY
# Spotify2YTM (`sp2yt` / `yt2sp` v2.0.0) — High-Precision Reverse Migration Platform (Spotify → YouTube Music)

---

## 1. Architectural Patterns & Design Principles

Spotify2YTM mengadopsi kombinasi pola arsitektur modern yang disesuaikan untuk keandalan eksekusi lokal dan migrasi arah baru:

1. **Local-First & Offline-Ready Architecture:** Seluruh data master, status relasi, dan cache respon API disimpan dalam satu file database lokal (`yt2sp.db`). Pengguna tetap dapat meninjau, memfilter, dan mengelola playlist yang sudah dicocokkan meskipun koneksi internet terputus.
2. **Layered Pipeline Architecture (ETL Pattern):** Alur kerja sistem terpisah secara tegas ke dalam 5 lapisan independen:
   - *Ingestion Layer:* Ekstraksi dari sumber **Spotify** (`yt2sp.sources.spotify_extract`).
   - *Persistence Layer:* Penyimpanan dan indexing SQLite 3 WAL dengan skema provider-neutral.
   - *Reconciliation & Matching Engine:* Normalisasi, fuzzy distance RapidFuzz, dan pencarian katalog tujuan **YouTube Music** (`yt2sp.destinations.ytm_resolver`).
   - *Classification & Enrichment Layer:* Validasi silang genre multi-sumber (iTunes + Deezer).
   - *Destination Dispatch & Writing Layer:* Pembuatan dan injeksi playlist otomatis ke akun **YouTube Music** (`yt2sp.destinations.ytm_writer`), dengan cadangan ekspor CSV.
3. **Decoupled Asynchronous Background Worker Pattern:** Seluruh operasi I/O jaringan yang membutuhkan waktu lama (ekstraksi, pencocokan massal, validasi genre, pembuatan playlist YTM) dieksekusi di *daemon thread* terpisah (`threading.Thread(target=..., daemon=True)`), sementara thread utama server HTTP tetap melayani request UI secara non-blocking dengan polling adaptif.
4. **Resilient Multi-Pass Fallback Pattern:** Pencarian lagu di YouTube Music mendahulukan katalog lagu resmi (`filter='songs'`), lalu fallback ke katalog video resmi jika lagu belum ditemukan.
5. **Batch Playlist Population with Chunking:** Injeksi lagu ke playlist YouTube Music dipecah ke dalam chunk aman berisi 50 video ID untuk mencegah timeout dan rate limiting.

---

## 2. High-Level System Architecture Diagram

Diagram berikut mengilustrasikan arsitektur sistem tingkat tinggi dari antarmuka pengguna hingga integrasi pihak ketiga eksternal.

```mermaid
flowchart TB
    subgraph CLIENT_LAYER["1. CLIENT INTERACTION LAYER"]
        BROWSER["Web Browser (Chrome/Edge/Brave)<br/>SPA Dashboard (Vanilla JS + Tailwind)"]
        TERMINAL["Terminal Console (PowerShell/Bash)<br/>Typer CLI + Rich Tables"]
    end

    subgraph SERVER_LAYER["2. LOCAL APPLICATION SERVER (yt2sp.ui.server)"]
        HTTP_ROUTER["ThreadingHTTPServer (:5000)<br/>UIHandler Router & Static Serve"]
        AUTH_GUARD["CSRF Guard & Safe Origin Validator<br/>(_is_safe_origin)"]
        GZIP_ENGINE["Dynamic Gzip Compressor<br/>(Compress Level 6)"]
        API_CACHE["In-Memory API TTL Cache Store<br/>(_get_cached_api / _set_cached_api)"]
        JOB_ORCHESTRATOR["Background Job Orchestrator<br/>(_job_state, _job_lock, _job_cancel_event)"]
    end

    subgraph PIPELINE_LAYER["3. DOMAIN LOGIC & PROCESSING PIPELINES"]
        SPOTIFY_EXTRACTOR["Spotify Extractor (Source)<br/>(yt2sp.sources.spotify_extract)"]
        MATCH_PIPELINE["Multi-Pass Reconciliation Pipeline<br/>(yt2sp.resolve.pipeline)"]
        NORMALIZER["Regex Cleaner & Distinctive Preserver<br/>(yt2sp.match.normalize)"]
        SCORING_ENGINE["RapidFuzz Token Set Scorer<br/>(yt2sp.match.score)"]
        YTM_RESOLVER["YouTube Music Resolver<br/>(yt2sp.destinations.ytm_resolver)"]
        YTM_WRITER["YouTube Music Playlist Writer<br/>(yt2sp.destinations.ytm_writer)"]
        GENRE_VALIDATOR["Cross-Validated Genre Engine<br/>(yt2sp.resolve.genre)"]
        EXPORT_ENGINE["Chunk Writer & CSV Reporter<br/>(yt2sp.export)"]
    end

    subgraph PERSISTENCE_LAYER["4. PERSISTENCE & DATA STORAGE"]
        SQLITE_DB[("yt2sp.db<br/>(SQLite 3 - WAL Mode)")]
        DB_TABLES["Tables: playlists, tracks, playlist_tracks,<br/>matches, api_cache, golden, runs"]
        DB_CONFIG["PRAGMA Cache: 64MB RAM<br/>mmap_size: 256MB, temp_store: MEMORY"]
    end

    subgraph EXTERNAL_SERVICES["5. EXTERNAL PUBLIC CATALOG SERVICES (Zero-Cost / Public)"]
        EXT_SPOTIFY["Spotify Public Web Catalog (Source)"]
        EXT_YTM["YouTube Music API / Web (Destination)"]
        EXT_ITUNES["Apple iTunes Search API (Metadata/Preview)"]
        EXT_DEEZER["Deezer Public API (Genre/Preview)"]
    end

    BROWSER <-->|REST API JSON / HTTP 5000| HTTP_ROUTER
    TERMINAL <-->|CLI Commands| PIPELINE_LAYER
    HTTP_ROUTER --> JOB_ORCHESTRATOR
    JOB_ORCHESTRATOR --> SPOTIFY_EXTRACTOR
    JOB_ORCHESTRATOR --> MATCH_PIPELINE
    JOB_ORCHESTRATOR --> YTM_WRITER
    SPOTIFY_EXTRACTOR <-->|Scrape Public Catalog| EXT_SPOTIFY
    SPOTIFY_EXTRACTOR --> SQLITE_DB
    MATCH_PIPELINE --> NORMALIZER
    MATCH_PIPELINE --> YTM_RESOLVER
    YTM_RESOLVER <-->|ytmusicapi.search| EXT_YTM
    YTM_RESOLVER --> SCORING_ENGINE
    MATCH_PIPELINE --> SQLITE_DB
    YTM_WRITER <-->|create_playlist & add_items| EXT_YTM
    GENRE_VALIDATOR <-->|Enrichment| EXT_ITUNES
    GENRE_VALIDATOR <-->|Enrichment| EXT_DEEZER
```
        EXT_SPOTIFY["Spotify Web Public Catalog<br/>(via spotifyscraper & oEmbed)"]
        EXT_DEEZER["Deezer Public Search & Track API<br/>(ISRC & 30s Audio Stream)"]
        EXT_MUSICBRAINZ["MusicBrainz Open Metadata<br/>(/ws/2/isrc -> Spotify Track URL)"]
        EXT_ITUNES["Apple iTunes Search API<br/>(Genre & 30s Audio Fallback)"]
    end

    %% Relasi Client ke Server
    BROWSER <-->|REST JSON & SSE/Polling| HTTP_ROUTER
    TERMINAL <-->|Direct Subprocess Call| PIPELINE_LAYER
    HTTP_ROUTER --> AUTH_GUARD --> GZIP_ENGINE
    GZIP_ENGINE --> API_CACHE
    API_CACHE <--> JOB_ORCHESTRATOR

    %% Relasi Server ke Pipeline
    JOB_ORCHESTRATOR -->|Spawns Worker Thread| YTM_EXTRACTOR
    JOB_ORCHESTRATOR -->|Spawns Worker Thread| MATCH_PIPELINE
    JOB_ORCHESTRATOR -->|Spawns Worker Thread| GENRE_VALIDATOR

    %% Relasi Pipeline
    YTM_EXTRACTOR --> PERSISTENCE_LAYER
    MATCH_PIPELINE --> NORMALIZER --> SCORING_ENGINE
    MATCH_PIPELINE --> RATE_LIMITER
    MATCH_PIPELINE <--> PERSISTENCE_LAYER
    GENRE_VALIDATOR <--> PERSISTENCE_LAYER
    EXPORT_ENGINE <--> PERSISTENCE_LAYER

    %% Relasi ke Eksternal
    YTM_EXTRACTOR <-->|HTTPS| EXT_YTM
    RATE_LIMITER --> EXT_SPOTIFY
    MATCH_PIPELINE <-->|Tier 1 Scraping| EXT_SPOTIFY
    MATCH_PIPELINE <-->|Tier 2 ISRC Fallback| EXT_DEEZER
    EXT_DEEZER <-->|ISRC Lookup| EXT_MUSICBRAINZ
    GENRE_VALIDATOR <-->|Parallel Query| EXT_ITUNES
    GENRE_VALIDATOR <-->|Parallel Query| EXT_DEEZER
    HTTP_ROUTER <-->|Audio Preview Proxy| EXT_DEEZER
    HTTP_ROUTER <-->|Audio Preview Fallback| EXT_ITUNES

    %% Ekspor ke Spotify Desktop
    EXPORT_ENGINE -->|System Clipboard / Chunk File| SPOTIFY_DESKTOP
    SPOTIFY_DESKTOP -->|Ctrl + V Keyboard Ingestion| SPOTIFY_DESKTOP
```

---

## 3. Component Diagram & Module Dependencies

Diagram dependensi modul di bawah ini memetakan interaksi antar-modul Python dalam paket `yt2sp`:

```mermaid
graph TD
    CLI["yt2sp.cli<br/>(Typer Entrypoint)"]
    SERVER["yt2sp.ui.server<br/>(HTTP Web Server)"]
    CONFIG["yt2sp.config<br/>(Toml Loader)"]
    DB["yt2sp.store.db<br/>(SQLite Layer)"]
    YTM["yt2sp.ytm.extract<br/>(YTM Extractor)"]
    PIPELINE["yt2sp.resolve.pipeline<br/>(Match Orchestrator)"]
    SP_RES["yt2sp.resolve.spotify_resolver<br/>(Spotify Client)"]
    DZ_RES["yt2sp.resolve.deezer_resolver<br/>(Deezer + MB)"]
    RATE["yt2sp.resolve.rate_limiter<br/>(Token Bucket)"]
    GENRE["yt2sp.resolve.genre<br/>(Genre Validator)"]
    NORM["yt2sp.match.normalize<br/>(String Sanitizer)"]
    SCORE["yt2sp.match.score<br/>(RapidFuzz Math)"]
    WRITER["yt2sp.export.writer<br/>(URI Chunk Writer)"]
    REPORT["yt2sp.export.report<br/>(CSV BOM Generator)"]

    CLI --> CONFIG
    CLI --> DB
    CLI --> YTM
    CLI --> PIPELINE
    CLI --> GENRE
    CLI --> WRITER
    CLI --> REPORT
    CLI --> SERVER

    SERVER --> CONFIG
    SERVER --> DB
    SERVER --> YTM
    SERVER --> PIPELINE
    SERVER --> GENRE
    SERVER --> SP_RES
    SERVER --> NORM

    PIPELINE --> DB
    PIPELINE --> RATE
    PIPELINE --> SP_RES
    PIPELINE --> DZ_RES
    PIPELINE --> SCORE
    PIPELINE --> GENRE

    DZ_RES --> SP_RES

    SCORE --> NORM
    SP_RES --> NORM
    SP_RES --> SCORE
```

---

## 4. End-to-End Data Flow Diagram (DFD)

Alur transformasi data dimulai dari penarikan URL YouTube Music hingga penyalinan ke Spotify Desktop:

```mermaid
sequenceDiagram
    autonumber
    actor User as Pengguna
    participant UI as Web Dashboard / CLI
    participant Server as HTTP Server (server.py)
    participant YTM as YTM Extract (ytmusicapi)
    participant DB as SQLite DB (yt2sp.db)
    participant Matcher as Pipeline (pipeline.py)
    participant Spotify as Spotify Scraper
    participant Deezer as Deezer API & MusicBrainz
    participant Genre as Genre Engine
    participant SpotifyApp as Spotify Desktop Client

    User->>UI: Paste URL Playlist (misal: "https://music.youtube.com/...")
    UI->>Server: POST /api/extract {playlist_id}
    Server->>YTM: get_playlist_details(clean_id)
    YTM-->>Server: Judul, Tracks, & unavailable_count
    Server->>DB: upsert_playlist() & upsert_track() batch
    Server-->>UI: 200 OK {"status": "started"}
    UI-->>User: Tampilkan jumlah lagu & dialog konfirmasi

    User->>UI: Klik "Mulai Pencocokan"
    UI->>Server: POST /api/resolve {playlist_id: "all"}
    Server->>Matcher: run_resolve(stop_event)
    loop Setiap Lagu Pending
        Matcher->>Matcher: normalize_title() & cek penanda pembeda
        Matcher->>Spotify: search_spotify(title, artists) [Tier 1]
        alt Kandidat Ditemukan & Skor >= 0.55
            Matcher->>Matcher: compute_score() via RapidFuzz
            Matcher->>DB: set_match(status='resolved_auto' atau 'needs_review')
        else Tidak Ditemukan / Skor < 0.55
            Matcher->>Deezer: search_deezer() [Tier 2 Fallback]
            Deezer-->>Matcher: ISRC Code & Spotify ID via MusicBrainz
            Matcher->>DB: set_match(status='resolved_auto' (T2_isrc) atau 'failed')
        end
        Matcher-->>UI: on_progress callback -> Live Progress Bar
    end

    opt Pengguna Membuka Review Studio
        User->>UI: Hover Thumbnail Cover Lagu
        UI->>Server: GET /api/preview?video_id=...
        Server->>Deezer: Cek MP3 Preview Stream
        alt Gagal di Deezer
            Server->>Server: Fallback ke Apple iTunes Preview
        end
        Server-->>UI: URL Audio 30 Detik
        UI-->>User: Putar Audio (Chorus/Reff)
        User->>UI: Setujui (Accept) atau Pilih Versi Alternatif
        UI->>Server: POST /api/review atau /api/choose-alternative
        Server->>DB: Update match status='accepted'
    end

    User->>UI: Klik "Salin Semua URI Spotify"
    UI->>Server: GET /api/uris
    Server->>DB: SELECT spotify_id WHERE status IN ('resolved_auto', 'accepted')
    Server-->>UI: Daftar Spotify URI bersih (50-song blocks)
    UI->>User: Salin ke System Clipboard
    User->>SpotifyApp: Buka Playlist Baru di Spotify Desktop
    User->>SpotifyApp: Tekan Shortcut Keyboard [Ctrl + V]
    SpotifyApp-->>User: Seluruh lagu langsung masuk ke playlist Spotify!
```

---

## 5. Deployment & Runtime Topology Diagram

Topologi eksekusi sistem pada lingkungan lokal komputer pengguna:

```mermaid
flowchart LR
    subgraph OS_ENVIRONMENT["KOMPUTER PENGGUNA (Windows / macOS / Linux)"]
        subgraph USER_SPACE["User Space Processes"]
            subgraph PYTHON_PROCESS["Python 3.11+ Process (yt2sp ui)"]
                MAIN_THREAD["Main Thread:<br/>ThreadingHTTPServer (127.0.0.1:5000)"]
                WORKER_1["Background Thread:<br/>Extraction / Matching / Genre Worker"]
                CONN_POOL["Thread-Local DB Connections<br/>(_local.conn)"]
            end
            
            subgraph BROWSER_PROCESS["Web Browser Instance"]
                SPA_TAB["Tab: http://127.0.0.1:5000<br/>Single Page App (DOM, Canvas, Web Audio)"]
            end

            subgraph SPOTIFY_PROCESS["Spotify Desktop App"]
                CLIPBOARD_LISTENER["Clipboard Buffer Ingestion<br/>Native Ctrl+V Hook"]
            end

            subgraph FILESYSTEM["Local File System"]
                DB_FILE["yt2sp.db (SQLite Database)"]
                WAL_FILE["yt2sp.db-wal (Write-Ahead Log)"]
                CONFIG_FILE["config.toml (User Configurations)"]
                OUTPUT_DIR["output/<br/>├── uris/ (*_part001.txt)<br/>└── reports/ (*_report.csv)"]
            end
        end
    end

    SPA_TAB <-->|Loopback HTTP Socket (127.0.0.1)| MAIN_THREAD
    MAIN_THREAD <--> CONN_POOL
    WORKER_1 <--> CONN_POOL
    CONN_POOL <--> DB_FILE
    CONN_POOL <--> WAL_FILE
    PYTHON_PROCESS --> OUTPUT_DIR
    CONFIG_FILE --> PYTHON_PROCESS
    SPA_TAB -.->|Direct Copy| CLIPBOARD_LISTENER
```
