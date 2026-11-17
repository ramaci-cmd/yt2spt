# 05. SOURCE CODE & IMPLEMENTATION DOCUMENTATION
# YT2Spotify (`yt2sp`) — High-Precision, Zero-Cost Music Migration Platform

---

## 1. Actual Project Directory Structure

Berikut adalah struktur pohon direktori fisik aktual repositori `yt2sp` v1.3.7 beserta peran fungsional setiap modul:

```
yt-spt/
├── config.toml                      # Konfigurasi parameter matching, rate limit, & chunk size
├── pyproject.toml                   # Definisi paket setuptools, dependensi, & entrypoints CLI
├── CHANGELOG.md                     # Catatan riwayat versi terstruktur dari v1.0.0 s/d v2.0.0
├── README.md                        # Panduan visual proyek, CLI, & preview antarmuka
├── LICENSE                          # Lisensi open-source The Unlicense (Public Domain)
├── .gitignore                       # Pola pengabaian git (db, virtualenvs, auth cache)
│
├── yt2sp/                           # Direktori Paket Sumber Kode Utama
│   ├── __init__.py                  # Inisialisasi paket, version string ('2.0.0'), & engine name
│   ├── config.py                    # Loader toml dengan rekursif deep-merge fallback
│   ├── cli.py                       # Antarmuka terminal Typer + Rich (extract, resolve, export --ytm)
│   │
│   ├── sources/                     # [NEW] Modul Ekstraksi Sumber (Spotify)
│   │   ├── __init__.py              # Package marker & export
│   │   └── spotify_extract.py       # Ekstraksi Spotify playlist via spotifyscraper tanpa developer token
│   │
│   ├── destinations/                # [NEW] Modul Resolusi & Penulisan Tujuan (YouTube Music)
│   │   ├── __init__.py              # Package marker & export
│   │   ├── ytm_resolver.py          # Pencarian kandidat lagu & alternatif aransemen di YouTube Music
│   │   └── ytm_writer.py            # Pembuatan playlist & injeksi lagu otomatis ke akun YouTube Music
│   │
│   ├── ytm/                         # Modul Ekstraksi YouTube Music (Legacy & Fallback Provider)
│   │   ├── __init__.py              # Package marker
│   │   └── extract.py               # Wrapper ytmusicapi, regex cleaner, audit video terhapus
│   │
│   ├── match/                       # Modul Normalisasi & Penilaian String
│   │   ├── __init__.py              # Package marker
│   │   ├── normalize.py             # Pembersih 17 pola noise & penjaga 15 penanda pembeda
│   │   └── score.py                 # Algoritma fuzzy scoring RapidFuzz & penalti durasi/marker
│   │
│   ├── resolve/                     # Modul Resolusi Katalog & Kategorisasi
│   │   ├── __init__.py              # Package marker
│   │   ├── rate_limiter.py          # Token bucket rate limiter & exponential backoff jitter
│   │   ├── spotify_resolver.py      # Klien pencarian spotifyscraper (legacy bidirectional bridge)
│   │   ├── deezer_resolver.py       # Fallback Tier 2: Deezer search, ISRC & MusicBrainz bridge
│   │   ├── genre.py                 # Validasi silang genre multi-sumber (iTunes + Deezer)
│   │   └── pipeline.py              # Orkestrator pencocokan Spotify -> YouTube Music batch
│   │
│   ├── store/                       # Modul Lapisan Akses Data SQLite
│   │   ├── __init__.py              # Package marker
│   │   └── db.py                    # Schema migrations, PRAGMA WAL tuning, DDL provider-neutral, CRUD
│   │
│   ├── export/                      # Modul Pemformatan & Ekspor
│   │   ├── __init__.py              # Package marker
│   │   ├── writer.py                # Pemecah URI ke file teks blok 50 lagu berformat bersih
│   │   └── report.py                # Pembuat laporan CSV ber-BOM UTF-8 dengan link web search
│   │
│   └── ui/                          # Modul Antarmuka Web Dashboard Lokal
│       ├── __init__.py              # Package marker
│       ├── server.py                # ThreadingHTTPServer, REST API endpoints (/api/export-ytm, dll)
│       ├── index.html               # Single Page Application (Transactify warm editorial design)
│       └── i18n.js                  # Kamus lokalisasi 6 bahasa (ID, EN, ES, JA, KO, ZH)
│       ├── __init__.py              # Package marker
│       ├── server.py                # ThreadingHTTPServer, REST API, anti-CSRF, ETag, & Gzip
│       ├── index.html               # Single Page Application (7 views, 7 modals, Tailwind CSS)
│       ├── i18n.js                  # Kamus lokalisasi 6 bahasa (ID, EN, ES, JA, KO, ZH)
│       └── assets/                  # Aset gambar lokal untuk cover demo & visualizer
│           ├── album_cover.jpg
│           ├── alpine_meadow.jpg
│           └── hero_landscape.jpg
│
├── tests/                           # Modul Pengujian Otomatis (Pytest)
│   ├── test_db.py                   # Uji CRUD database, cascade deletion, & sampling artwork
│   ├── test_export.py               # Uji validasi Spotify URI & pembagian blok file teks
│   ├── test_genre.py                # Uji pembersihan kueri, heuristik, & validasi silang genre
│   ├── test_normalize.py            # Uji pembersihan noise regex & perlindungan distinctive marker
│   ├── test_resolve.py              # Uji singleton SpotifyClient & mocking resolusi ISRC
│   └── test_score.py                # Uji skor fuzzy, penalti marker, & ambang batas klasifikasi
│
└── docs/                            # Dokumentasi & Aset Tangkapan Layar
    ├── PRD.md                       # Draf awal PRD versi 1.0.0
    └── screenshots/                 # 5 Tangkapan layar antarmuka beresolusi tinggi
        ├── 01-dashboard.png
        ├── 02-review-studio.png
        ├── 03-playlists-library.png
        ├── 04-guide.png
        └── 05-mobile-responsive.png
```

---

## 2. File-by-File Technical Deep Dive

Bagian ini menguraikan setiap fungsi, signature, konstanta, dan tanggung jawab teknis dari setiap file di repositori:

---

### 2.1 `yt2sp/__init__.py`
* **Lokasi:** [yt2sp/__init__.py](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/__init__.py)
* **Konstanta Penting:**
  - `__version__ = "1.3.7"`: Versi aktif yang dibaca secara dinamis oleh antarmuka web melalui endpoint `/api/version` dan perintah CLI `yt2sp --version`.
  - `__engine__ = "Multi-Pass"`: Penanda arsitektur mesin pencocokan bertingkat.

---

### 2.2 `yt2sp/config.py`
* **Lokasi:** [yt2sp/config.py](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/config.py)
* **Tanggung Jawab:** Membaca parameter pengguna dari `config.toml` dengan fallback aman ke konfigurasi default sistem.
* **Konstanta `_DEFAULT_CONFIG`:**
  - `resolve.rate_per_minute: 30` (ditingkatkan ke `120` di `config.toml` kerja)
  - `resolve.backoff_base: 2.0`, `resolve.backoff_max: 120.0`
  - `match.auto_accept_threshold: 0.85` (disesuaikan ke `0.80` di `config.toml`)
  - `match.review_threshold: 0.60` (disesuaikan ke `0.55` di `config.toml`)
  - `match.title_weight: 0.6`, `match.artist_weight: 0.4`
  - `match.duration_tolerance_pct: 0.10` ($\pm 10\%$)
  - `export.chunk_size: 50`
* **Fungsi Utama:**
  - `_deep_merge(base: dict, override: dict) -> dict`: Algoritma rekursif untuk menggabungkan kamus konfigurasi bertingkat tanpa menghilangkan kunci default yang tidak didefinisikan pengguna.
  - `load_config(path: Path | None = None) -> dict`: Membaca file TOML menggunakan `tomllib` (Python 3.11+) dengan fallback ke `tomli`.

---

### 2.3 `yt2sp/store/db.py`
* **Lokasi:** [yt2sp/store/db.py](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/store/db.py)
* **Tanggung Jawab:** Mengelola seluruh transaksi data SQLite, penguncian thread, performa I/O memori, dan integritas relasional.
* **Variabel Modul:** `DB_PATH = Path("yt2sp.db")`, `_local = threading.local()` (penyimpanan koneksi unik per-thread).
* **Fungsi-Fungsi Kunci:**
  - `_get_conn() -> sqlite3.Connection`: Membuka koneksi per-thread, mengatur `row_factory = sqlite3.Row`, dan mengeksekusi 6 PRAGMA performa (`WAL`, `NORMAL`, `foreign_keys=ON`, `cache_size=-64000`, `temp_store=MEMORY`, `mmap_size=268435456`).
  - `init_db(db_path: Path | None = None) -> None`: Membuat 7 tabel (`playlists`, `tracks`, `playlist_tracks`, `matches`, `api_cache`, `runs`, `golden`) dan 7 indeks performa jika belum ada.
  - `upsert_playlist(yt_playlist_id: str, title: str, track_count: int, unavailable_count: int = 0) -> int`: Menyimpan atau memperbarui metadata playlist dan mengembalikan ID numerik primary key.
  - `get_playlist_sample_video_ids(playlist_id: int, limit: int = 4) -> list[str]`: Mengambil 4 ID video teratas untuk dirender menjadi **2x2 Collage Artwork**.
  - `upsert_track(video_id: str, title: str, artists: list[str], album: str, duration_ms: int, video_type: str) -> None`: Menyimpan lagu secara unik global dengan deduplikasi `ON CONFLICT(video_id) DO NOTHING`.
  - `upsert_playlist_track(playlist_id: int, video_id: str, position: int) -> None`: Menghubungkan playlist dengan track beserta nomor posisi urutan lagu.
  - `set_match(video_id: str, *, spotify_id: str | None, tier: str, score: float, status: str, ...)`: Memperbarui hasil pencocokan lagu secara aman melalui klausul `INSERT ... ON CONFLICT(video_id) DO UPDATE SET`.
  - `get_pending_tracks(playlist_id: int | None = None) -> list[sqlite3.Row]`: Mengambil lagu yang statusnya masih `NULL` atau `'pending'`.
  - `reset_unresolved_tracks_to_pending(...) -> int`: Mengembalikan status lagu gagal atau yang belum diterima kembali ke antrean matching.
  - `delete_playlists(playlist_ids: list[int]) -> int`: Menghapus sejumlah playlist sekaligus, membersihkan lagu yatim (*orphan tracks & matches*) via subkueri `NOT IN (SELECT video_id FROM playlist_tracks)`, dan mengeksekusi `VACUUM`.
  - `delete_tracks(video_ids: list[str], playlist_id: int | None = None) -> int`: Menghapus lagu dari playlist spesifik atau permanen dari seluruh pustaka dengan sanitasi orphan record.

---

### 2.4 `yt2sp/ytm/extract.py`
* **Lokasi:** [yt2sp/ytm/extract.py](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ytm/extract.py)
* **Tanggung Jawab:** Berkomunikasi dengan backend YouTube Music melalui pustaka `ytmusicapi`.
* **Fungsi-Fungsi Kunci:**
  - `clean_playlist_id(raw_input: str) -> str`: Menggunakan `urllib.parse` dan regex `[?&]list=([a-zA-Z0-9_-]+)` untuk mengekstrak ID murni dari link web browser, share link mobile `youtu.be`, atau string mentah.
  - `get_ytm(auth_path: Path | None = None) -> YTMusic`: Menginisialisasi objek `YTMusic`. Menggunakan kredensial file `ytm_auth.json` jika ada, atau mode unauthenticated jika tidak ada.
  - `get_playlist_details(ytm: YTMusic, playlist_id: str) -> PlaylistResult`: Mengambil judul playlist, array tracks, dan menghitung `unavailable_count = max(0, total_reported - len(tracks))` untuk mendeteksi lagu yang dihapus/diprivat oleh pengunggah YouTube.
  - `parse_track(raw: dict) -> dict[str, Any] | None`: Memvalidasi keberadaan `videoId`, memisahkan array nama musisi, nama album, tipe video, dan mengonversi format durasi teks (`m:s` atau `h:m:s`) ke milidetik via `_parse_duration_ms()`.
  - `get_liked_songs(ytm: YTMusic) -> list[dict]`: Mengambil hingga 5.000 lagu dari koleksi *Liked Music* pribadi pengguna (membutuhkan file autentikasi `ytm_auth.json`).

---

### 2.5 `yt2sp/match/normalize.py`
* **Lokasi:** [yt2sp/match/normalize.py](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/match/normalize.py)
* **Tanggung Jawab:** Menghilangkan noise promosi video YouTube namun menjaga penanda pembeda aransemen lagu.
* **Konstanta `DISTINCTIVE_MARKERS`:**
  - Berisi 15 penanda penting: `"live"`, `"acoustic"`, `"remix"`, `"cover"`, `"instrumental"`, `"karaoke"`, `"slowed"`, `"sped up"`, `"nightcore"`, `"lofi"`, `"lo-fi"`, `"unplugged"`, `"demo"`, `"radio edit"`, `"extended"`.
* **Konstanta `_NOISE_RE`:**
  - Regex yang memfilter 17 pola noise: `official music video`, `official audio`, `lyric video`, `visualizer`, `lyrics`, `music video`, `mv`, `hd`, `4k`, `remastered`, `explicit version`, `clean version`, dll.
* **Fungsi-Fungsi Kunci:**
  - `has_distinctive_marker(text: str) -> set[str]`: Mengembalikan himpunan penanda pembeda yang terdeteksi di dalam string.
  - `normalize_title(title: str, *, keep_feat: bool = False) -> str`:
    * Tahap 1: Menghapus klausul `feat.` / `ft.` via `_FEAT_RE`.
    * Tahap 2: Menghapus isi tanda kurung `(...)` dan `[...]` HANYA jika isinya bukan penanda pembeda (menggunakan closure `_strip_parens`).
    * Tahap 3: Menghapus kata noise via `_NOISE_RE`.
    * Tahap 4: Mengonversi aksen Unicode ke ASCII menggunakan `unidecode`.
    * Tahap 5: Menghapus karakter non-alfanumerik (`[^a-z0-9\s]`) dan merapikan spasi.
  - `normalize_artist(artist: str) -> str`: Menghapus feat, mengonversi ke ASCII lowercase, dan membuang karakter non-alfanumerik.

---

### 2.6 `yt2sp/match/score.py`
* **Lokasi:** [yt2sp/match/score.py](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/match/score.py)
* **Tanggung Jawab:** Menghitung skor probabilitas kecocokan antara metadata YouTube Music dan hasil pencarian Spotify.
* **Konstanta:** `_DISTINCTIVE_PENALTY = 0.12` *(diperbarui pada commit 940a18e dari sebelumnya 0.30 agar tidak terlalu menghukum kecocokan valid)*.
* **Fungsi-Fungsi Kunci:**
  - `_best_artist_score(yt_artists: list[str], sp_artist: str) -> float`: Menghitung `fuzz.token_set_ratio` antara setiap nama artis YouTube Music terhadap nama artis Spotify, lalu mengambil nilai maksimum ($0.0 - 1.0$).
  - `compute_score(...) -> tuple[float, str]`:
    * Menghitung $\text{BaseScore} = \text{title\_weight} \times \text{TitleSim} + \text{artist\_weight} \times \text{ArtistSim}$.
    * Mengevaluasi penanda pembeda: Jika ada penanda yang hanya muncul di satu sisi, skor dipotong penalti $-0.12$.
    * Mengevaluasi toleransi durasi: Jika selisih durasi $> 5000\text{ ms}$ DAN ($> 10\%$ atau $> 12000\text{ ms}$), skor dipotong penalti $-0.10$.
    * Mengunci skor akhir pada rentang $[0.0, 1.0]$ dan mengembalikan string alasan penilaian (`reason`).
  - `classify(score: float, *, auto_threshold=0.80, review_threshold=0.55) -> str`: Mengklasifikasikan skor ke status `'resolved_auto'`, `'needs_review'`, atau `'failed'`.

---

### 2.7 `yt2sp/resolve/rate_limiter.py`
* **Lokasi:** [yt2sp/resolve/rate_limiter.py](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/resolve/rate_limiter.py)
* **Tanggung Jawab:** Menjaga laju request scraping agar tidak memicu HTTP 429 Too Many Requests.
* **Kelas `RateLimiter`:**
  - Mengimplementasikan algoritma **Token Bucket** thread-safe dengan penguncian `threading.Lock()`.
  - Dimulai dengan bucket penuh (`rate_per_minute`).
  - Metode `acquire()` melakukan sleep secara presisi sejumlah durasi yang dibutuhkan untuk menghasilkan token baru jika token kosong.
* **Fungsi `backoff_sleep(attempt, base=2.0, max_wait=120.0, jitter=0.5) -> float`:** Menidurkan thread dengan jeda eksponensial ditambah angka acak (*jitter*) untuk menghindari *thundering herd problem*.

---

### 2.8 `yt2sp/resolve/spotify_resolver.py`
* **Lokasi:** [yt2sp/resolve/spotify_resolver.py](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/resolve/spotify_resolver.py)
* **Tanggung Jawab:** Menjalankan pencarian langsung ke katalog internal Spotify via `spotifyscraper` tanpa token developer.
* **Pola Singleton Thread-Safe:** Fungsi `_get_client()` dan `_reset_client()` menggunakan penguncian mutex `_client_lock`.
* **Fungsi `search_spotify(title, artists, top_n=5, max_retries=3) -> list[SpotifyCandidate]`:** Menyusun kueri `"<Title> <PrimaryArtist>"`, mengeksekusi pencarian dengan retry otomatis hingga 3 kali, dan mengembalikan objek `SpotifyCandidate` (`spotify_id`, `uri`, `title`, `artist`, `duration_ms`).
* **Fungsi `find_alternative_versions(...) -> list[dict]`:** Mencari hingga 8 variasi versi lagu di Spotify (Cover, Acoustic, Live, Remix), mengklasifikasikannya ke dalam 3 badge cerdas, dan mengurutkannya berdasarkan relevansi.

---

### 2.9 `yt2sp/resolve/deezer_resolver.py`
* **Lokasi:** [yt2sp/resolve/deezer_resolver.py](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/resolve/deezer_resolver.py)
* **Tanggung Jawab:** Fallback Tier 2 untuk menemukan lagu langka via ISRC code.
* **Fungsi `search_deezer(title, artists, top_n=3) -> list[DeezerCandidate]`:** Memanggil Deezer Public Search API, mengekstrak kode ISRC dari endpoint track detail, dan menyelesaikan ISRC tersebut ke Spotify ID via MusicBrainz API atau kueri Spotify native `isrc:<ISRC>`.

---

### 2.10 `yt2sp/resolve/genre.py`
* **Lokasi:** [yt2sp/resolve/genre.py](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/resolve/genre.py)
* **Tanggung Jawab:** Validasi silang genre multi-sumber (iTunes + Deezer + Heuristik).
* **Konstanta:**
  - `GENRE_GROUPS`: Kamus pemetaan lebih dari 40 sub-genre ke 14 kategori standar (*Indonesian Pop, Dangdut & Koplo, Pop, K-Pop, Rock, Alternative & Indie, Electronic & Dance, Anime, Soundtrack & Classical, dll*).
  - `SPECIFIC_GENRES`: Himpunan genre spesifik yang diprioritaskan di atas genre umum (*Pop, Rock, Asian Music*).
* **Fungsi `_fetch_both_raw(q, timeout)`:** Menggunakan `concurrent.futures.ThreadPoolExecutor(max_workers=2)` untuk memanggil Apple iTunes Search API dan Deezer Catalog API secara bersamaan dalam waktu $\le 4$ detik.
* **Fungsi `validate_and_reconcile_genre(...) -> GenreValidationResult`:** Menerapkan 5 hierarki rekonsiliasi: Kesepakatan Penuh (Confidence 1.0), Resolusi Spesifisitas Subgenre (Confidence 0.92), Sumber Tunggal (Confidence 0.85), Fallback Heuristik (Confidence 0.75), dan Uncategorized (Confidence 0.0).

---

### 2.11 `yt2sp/resolve/pipeline.py`
* **Lokasi:** [yt2sp/resolve/pipeline.py](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/resolve/pipeline.py)
* **Tanggung Jawab:** Orkestrator utama pencocokan katalog batch.
* **Fungsi `run_resolve(...) -> dict`:**
  - Mengambil lagu pending dari database.
  - Memeriksa flag pembatalan `stop_event.is_set()` pada setiap iterasi lagu.
  - Melewati (*skip*) video non-musik (`MUSIC_VIDEO_TYPE_UGC`).
  - Menjalankan pencarian Tier 1 (Spotify) dengan pembatasan token bucket.
  - Jika skor $< 0.55$ atau tidak ada hasil, otomatis memicu Tier 2 (Deezer ISRC Fallback).
  - Memperbarui tabel `matches` dan memicu callback `on_progress` untuk memperbarui progress bar antarmuka pengguna.

---

### 2.12 `yt2sp/export/writer.py` & `report.py`
* **`writer.py`:**
  - `validate_uri(uri: str) -> bool`: Regex validator format Spotify URI `^spotify:track:[A-Za-z0-9]{22}$`.
  - `write_uri_blocks(...) -> list[Path]`: Memecah daftar URI per 50 baris (`chunk_size=50`) ke dalam file teks `output/uris/<Playlist>_part001.txt`.
* **`report.py`:**
  - `write_csv_report(...) -> Path`: Menghasilkan laporan CSV ber-BOM UTF-8 (`utf-8-sig`) di `output/reports/<Playlist>_report.csv` lengkap dengan tautan pencarian langsung Spotify.

---

### 2.13 `yt2sp/ui/server.py`
* **Lokasi:** [yt2sp/ui/server.py](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/server.py)
* **Tanggung Jawab:** Server HTTP lokal tanpa dependensi eksternal (`http.server.ThreadingHTTPServer`), anti-CSRF, ETag caching, Gzip compression, TTL API cache, dan orkestrasi background threads.
* **Fitur-Fitur Kunci:**
  - Melayani 12 endpoint REST API JSON.
  - Mengelola `_job_state`, `_job_lock`, dan `_job_cancel_event`.
  - Menyediakan proxy pratinjau audio 30 detik (`/api/preview`) dengan fallback Deezer $\rightarrow$ iTunes dan TTL 24 jam.
  - Menyediakan penautan manual Spotify ID dengan auto-fetch judul dan cover via Spotify oEmbed API.

---

### 2.14 `yt2sp/cli.py`
* **Lokasi:** [yt2sp/cli.py](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/cli.py)
* **Tanggung Jawab:** Antarmuka baris perintah (CLI) berbasis Typer dan Rich.
* **13 Sub-Perintah CLI:** `init`, `auth_ytm`, `extract`, `resolve`, `review`, `export`, `tag_genre`, `split`, `status`, `golden`, `smoke_test`, `ui`, `reset_cmd`.
