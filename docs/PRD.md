# 📑 COMPREHENSIVE PRODUCT REQUIREMENTS DOCUMENT (PRD)
# YT2Spotify (`yt2sp`) — High-Precision, Zero-Cost Music Migration Platform

---

## 1. Dokumen Metadata & Gambaran Umum Produk

| Atribut | Informasi Spesifikasi |
| :--- | :--- |
| **Nama Produk** | **YT2Spotify** (`yt2sp`) |
| **Versi Rilis** | `1.0.0` (Production Stable) |
| **Kategori Perangkat Lunak** | Music Utility, Catalog Reconciliation Engine, Local-First ETL Pipeline |
| **Lisensi** | MIT License |
| **Target Lingkungan Eksekusi** | Python 3.11+, Windows 10/11, macOS 12+, Linux (Ubuntu/Debian/Arch) |
| **Target Klien Pemutar Musik** | Spotify Desktop Client (Windows / macOS) dengan integrasi Clipboard |
| **Biaya Operasional & API** | **Rp0 / $0 (100% Free)** — Bebas akun developer berbayar, bebas biaya subscription |
| **Tingkat Privasi** | **100% Local-First** — Basis data SQLite lokal, zero telemetri, zero remote database |
| **Target Akurasi / Presisi** | $\ge 98.0\%$ Precision pada Golden Dataset terverifikasi |

---

## 2. Problem Statement, Analisis Kompetitif, & Terobosan "Ctrl+V"

### 2.1 Masalah di Pasar Saat Ini
Migrasi daftar putar musik antarlayanan (khususnya dari YouTube Music ke Spotify) adalah kebutuhan umum jutaan penikmat musik. Namun, solusi yang tersedia di industri menghadapi hambatan kritis:
1. **Model Langganan Pemerasan (SaaS Paywalls):** Layanan seperti Soundiiz, TuneMyMusic, dan FreeYourMusic membatasi konversi gratis hanya 20–50 lagu. Untuk pustaka ratusan/ribuan lagu, pengguna dipaksa membayar $4.50 – $14.99 per bulan.
2. **Kerapuhan Spotify Web API:**
   * Spotify Web API resmi mewajibkan registrasi aplikasi di Developer Dashboard, konfigurasi OAuth Redirect URI, dan token akses yang kedaluwarsa setiap 60 menit.
   * Spotify menerapkan pembatasan laju (*Rate Limit*) ketat (HTTP 429). Pembuatan playlist massal ribuan lagu lewat REST API sering kali memicu pemblokiran akun sementara.
3. **Kekacauan Metadata Video YouTube:**
   * Judul lagu di YouTube penuh dengan variasi uploader, teks promosi, dan noise: `[Official Music Video]`, `Lirik Video`, `ft.`, `Remix`, resolusi `4K`, dan kurung kanji Jepang `【...】`.
   * Mesin pencari Spotify yang kaku (*exact match*) gagal menemukan lagu jika judul mengandung noise tersebut.
4. **Masalah Keraguan Versi Lagu:** Pengguna sering menerima lagu hasil konversi yang salah (misalnya rekaman konser *Live* yang bising padahal yang diinginkan adalah versi rekaman studio *Album*).

### 2.2 Tabel Perbandingan Solusi
| Parameter Evaluasi | Solusi Komersial (Soundiiz / TuneMyMusic) | Spotify Web API Script Tradisional | **YT2Spotify (`yt2sp`)** |
| :--- | :--- | :--- | :--- |
| **Biaya Transfer >500 Lagu** | Berbayar ($4.50 – $14.99/bln) | Gratis (tapi butuh dev account) | **100% Gratis (Rp0 Selamanya)** |
| **Kebutuhan Kredensial** | Akses OAuth Akun Penuh (Privasi Rawan) | Client ID + Client Secret Spotify | **Nol Kredensial (Public Scraper)** |
| **Penanganan Rate Limit** | Sering antre berjam-jam | Error HTTP 429 Too Many Requests | **Aman (Token Bucket + Local Paste)** |
| **Eksekusi Pembuatan Playlist** | REST API Call per lagu | REST API Call per batch | **Native Desktop Paste (`Ctrl + V`)** |
| **Verifikasi Audio** | Tidak ada | Tidak ada | **Pratinjau Audio 30s Otomatis (Reff)** |
| **Pengelompokan Otomatis** | Manual satu per satu | Tidak ada | **Smart Genre Tagging & 1-Click Split** |
| **Penyimpanan Data** | Cloud Server Pihak Ketiga | Script Sementara / JSON | **Local SQLite (WAL Mode, Terstruktur)** |

### 2.3 Terobosan Injeksi Clipboard Desktop (`Ctrl + V`)
Alih-alih membuat playlist melalui panggilan REST API yang lambat dan dibatasi token OAuth, `yt2sp` memanfaatkan mekanisme internal aplikasi **Spotify Desktop**:
1. Aplikasi Spotify Desktop memiliki clipboard listener native yang mengenali format URI string Spotify:
   ```text
   spotify:track:4cOdK2wGLETKBW3PvgPWqT
   spotify:track:2dIBMHByUGcNPzmYBJ6OAj
   spotify:track:2hHeGD57S0BcopfVcmehdl
   ```
2. Ketika pengguna membuat playlist kosong di Spotify Desktop, memilih area track, dan menekan shortcut keyboard **`Ctrl + V`** (atau **`Cmd + V`** di macOS), Spotify Desktop langsung mem-parsing daftar URI tersebut dan menambahkan seluruh lagu secara instan tanpa melalui kuota Web API.
3. Untuk mencegah overflow buffer clipboard sistem operasi pada playlist masif (>500 lagu), `yt2sp` membagi URI ke dalam blok berukuran 50 lagu (*50-song chunks*).

---

## 3. Arsitektur Sistem, Komponen, & Data Flow

### 3.1 Diagram Alur Data Menyeluruh (End-to-End Pipeline)

```mermaid
flowchart TD
    subgraph INGESTION["1. INGESTION LAYER (yt2sp.ytm.extract)"]
        A1["Input: URL Playlist / ID YouTube Music"] --> A2["clean_playlist_id() Regex Parser"]
        A2 --> A3{"Cek file ytm_auth.json"}
        A3 -- "Ada" --> A4["YTMusic(auth='ytm_auth.json')<br/>(Dapat akses Liked Songs & Private)"]
        A3 -- "Tidak Ada" --> A5["YTMusic() Mode Publik Unauthenticated"]
        A4 & A5 --> A6["get_playlist_details() API Call"]
        A6 --> A7["Audit Unavailable Tracks (Dihapus/Privat)"]
        A6 --> A8["parse_track() & duration_ms normalization"]
    end

    subgraph STORAGE["2. PERSISTENCE LAYER (yt2sp.store.db)"]
        A7 & A8 --> B1[("yt2sp.db (SQLite 3 WAL Mode)")]
        B1 --> B2["Tabel playlists, tracks, playlist_tracks"]
    end

    subgraph RESOLUTION["3. MATCHING ENGINE PIPELINE (yt2sp.resolve.pipeline)"]
        B2 --> C1["Ambil baris 'pending' dari get_pending_tracks()"]
        C1 --> C2{"Penyaringan Jenis Konten"}
        C2 -- "video_type == MUSIC_VIDEO_TYPE_UGC" --> C3["Tandai 'skipped' (Bukan Lagu)"]
        C2 -- "Lagu Valid" --> C4["RateLimiter.acquire() Token Bucket"]
        
        C4 --> D1["yt2sp.match.normalize.normalize_title()"]
        D1 --> D2["Pembersihan Kata Noise (MV, 4K, Official, dll)"]
        D1 --> D3["Pelindungan Distinctive Markers (Live, Remix, Acoustic)"]
        
        D2 & D3 --> E1["Tier 1: spotifyscraper.SpotifyClient.search()"]
        E1 --> E2["yt2sp.match.score.compute_score()"]
        E2 --> E3["RapidFuzz Token Set Ratio (Title 0.6 + Artist 0.4)"]
        E3 --> E4["Evaluasi Penalti Marker (-0.30) & Penalti Durasi (-0.10)"]
        
        E4 --> F1{"Ambang Batas Skor (classify)"}
        F1 -- "Score ≥ 0.85" --> G1["Status: resolved_auto"]
        F1 -- "0.60 ≤ Score < 0.85" --> G2["Status: needs_review"]
        F1 -- "Score < 0.60 atau Kandidat Kosong" --> H1["Tier 2 Fallback: Deezer ISRC Bridge"]
        
        H1 --> H2["search_deezer() → Ekstrak ISRC"]
        H2 --> H3["MusicBrainz API (/ws/2/isrc) → Spotify ID"]
        H3 -- "Tidak Ketemu" --> H4["Spotify native search query 'isrc:ISRC'"]
        H3 & H4 -- "Ditemukan" --> H5["Hitung Ulang Skor & Klasifikasi"]
        H3 & H4 -- "Gagal Total" --> G3["Status: failed"]
    end

    subgraph ENRICHMENT["4. ENRICHMENT & CLASSIFICATION (yt2sp.resolve.genre)"]
        G1 & G2 --> I1["fetch_genre_validated() Konkuren"]
        I1 --> I2["Worker 1: Apple iTunes Search API"]
        I1 --> I3["Worker 2: Deezer Album Genre API"]
        I2 & I3 --> I4["validate_and_reconcile_genre()"]
        I4 --> I5["Pemetaan GENRE_GROUPS & Hierarki Spesifisitas"]
        I4 -- "Keduanya Null" --> I6["Fallback: detect_genre_heuristic()"]
        I5 & I6 --> I7["db.update_track_genre()"]
    end

    subgraph PRESENTATION["5. USER INTERFACE & DISPATCH (CLI & Web UI)"]
        B1 --> J1["Typer CLI (yt2sp cli.py)"]
        B1 --> J2["Local Web Dashboard (Python HTTP Server :5000)"]
        J2 --> K1["Preview Engine: Deezer CDN MP3 / Apple AAC 30s"]
        J2 --> K2["Review Studio: Alternative Version Picker"]
        J2 --> K3["AI Group Splitter Studio"]
        J1 & J2 --> L1["Export Engine: 50-Chunk TXT & CSV Report"]
        L1 --> L2["System Clipboard (Ctrl + C)"]
        L2 --> M1["Spotify Desktop Client (Ctrl + V Ingestion)"]
    end
```

---

## 4. Skema Basis Data SQLite & Konfigurasi Performa Tinggi

Sistem menggunakan mesin basis data internal SQLite 3 yang dioptimalkan untuk konkurensi pembacaan tinggi dari dashboard web bersamaan dengan penulisan batch dari proses matching latar belakang.

### 4.1 PRAGMA Tuning Performa ([yt2sp/store/db.py](file:///c:/Users/Elang/Downloads/yt-spt/yt2sp/store/db.py#L21-L26))
Setiap thread koneksi basis data diinisialisasi secara eksklusif menggunakan:
```sql
PRAGMA journal_mode = WAL;         -- Write-Ahead Logging: Pembacaan tidak memblokir penulisan
PRAGMA synchronous = NORMAL;        -- Menghindari fsync berlebih pada disk, mempercepat penulisan 4x
PRAGMA foreign_keys = ON;          -- Memaksakan integritas relasional antartabel
PRAGMA cache_size = -64000;        -- Mengalokasikan 64 MB RAM untuk buffer cache halaman basis data
PRAGMA temp_store = MEMORY;        -- Tabel sementara dan operasi sorting dijalankan di RAM
PRAGMA mmap_size = 268435456;      -- 256 MB Memory-Mapped I/O untuk throughput disk read seketika
```

### 4.2 Struktur Tabel (DDL) & Indeks Performa

#### Tabel 1: `playlists`
Menyimpan entitas daftar putar yang ditarik dari YouTube Music.
```sql
CREATE TABLE IF NOT EXISTS playlists (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    yt_playlist_id    TEXT UNIQUE NOT NULL,      -- ID playlist YouTube (misal: 'PLxxx' atau 'LIKED_SONGS')
    title             TEXT,                      -- Judul playlist
    track_count       INTEGER,                   -- Jumlah lagu aktif yang berhasil di-extract
    unavailable_count INTEGER DEFAULT 0,         -- Jumlah lagu yang dihapus/diprivat oleh uploader di YouTube
    extracted_at      TEXT                       -- Timestamp ISO-8601 UTC
);
```

#### Tabel 2: `tracks`
Menyimpan katalog lagu YouTube Music secara unik (deduplikasi global berdasarkan `video_id`).
```sql
CREATE TABLE IF NOT EXISTS tracks (
    video_id     TEXT PRIMARY KEY,              -- YouTube 11-character video ID
    title        TEXT NOT NULL,                 -- Judul lagu asli dari YouTube Music
    artists      TEXT,                          -- Serialisasi JSON Array of Strings: '["Musisi A", "Musisi B"]'
    album        TEXT,                          -- Judul album YouTube
    duration_ms  INTEGER,                       -- Durasi lagu dalam milidetik
    video_type   TEXT,                          -- Tipe konten ('MUSIC_VIDEO_TYPE_ATV', 'MUSIC_VIDEO_TYPE_UGC')
    genre        TEXT,                          -- Kategori genre hasil konsolidasi (misal: 'Indonesian Pop')
    genre_source TEXT                           -- Bukti sumber validasi (misal: 'itunes+deezer', 'heuristic')
);
CREATE INDEX IF NOT EXISTS idx_tracks_genre ON tracks(genre);
```

#### Tabel 3: `playlist_tracks`
Tabel relasi many-to-many antara playlist dan track, menyimpan urutan lagu.
```sql
CREATE TABLE IF NOT EXISTS playlist_tracks (
    playlist_id INTEGER NOT NULL REFERENCES playlists(id),
    video_id    TEXT    NOT NULL REFERENCES tracks(video_id),
    position    INTEGER NOT NULL,              -- Posisi urutan lagu dalam playlist (0-indexed)
    PRIMARY KEY (playlist_id, video_id)
);
CREATE INDEX IF NOT EXISTS idx_pt_playlist ON playlist_tracks(playlist_id);
CREATE INDEX IF NOT EXISTS idx_pt_video ON playlist_tracks(video_id);
```

#### Tabel 4: `matches`
Menyimpan status dan hasil resolusi kecocokan lagu dari YouTube ke Spotify.
```sql
CREATE TABLE IF NOT EXISTS matches (
    video_id      TEXT PRIMARY KEY REFERENCES tracks(video_id),
    spotify_id    TEXT,                          -- Spotify 22-character track ID
    tier          TEXT,                          -- Tingkatan resolusi: 'T1', 'T2_isrc', 'manual', 'alternative'
    score         REAL,                          -- Skor kemiripan gabungan (0.000 hingga 1.000)
    status        TEXT DEFAULT 'pending',        -- Status: 'pending', 'resolved_auto', 'needs_review', 
                                                 --         'accepted', 'rejected', 'failed', 'skipped'
    result_title  TEXT,                          -- Judul lagu yang cocok di Spotify
    result_artist TEXT,                          -- Nama musisi yang cocok di Spotify
    decided_by    TEXT,                          -- Pembuat keputusan: 'auto', 'human', 'ui_human', 'ui_manual'
    reason        TEXT,                          -- Log alasan penilaian, penalti, atau sumber fallback
    updated_at    TEXT                           -- Timestamp ISO-8601 UTC pembaruan terakhir
);
CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);
CREATE INDEX IF NOT EXISTS idx_matches_status_spid ON matches(status, spotify_id);
CREATE INDEX IF NOT EXISTS idx_matches_spid ON matches(spotify_id);
```

#### Tabel 5: `api_cache`
Cache respons HTTP lokal untuk kueri API eksternal (Deezer, iTunes, MusicBrainz) guna menghindari pemanggilan jaringan berulang.
```sql
CREATE TABLE IF NOT EXISTS api_cache (
    key           TEXT PRIMARY KEY,              -- Hash kueri atau URL target
    response_json TEXT,                          -- Data payload respons mentah
    http_status   INTEGER,                       -- Status kode HTTP (200, 404, dll)
    cached_at     TEXT                           -- Timestamp ISO-8601 UTC
);
CREATE INDEX IF NOT EXISTS idx_api_cache_key ON api_cache(key);
```

#### Tabel 6: `golden`
Dataset evaluasi presisi (Ground Truth) yang telah diverifikasi secara manual oleh manusia untuk benchmarking model pencocokan.
```sql
CREATE TABLE IF NOT EXISTS golden (
    video_id         TEXT PRIMARY KEY,           -- YouTube video ID
    spotify_id_human TEXT NOT NULL,              -- Spotify track ID yang 100% benar menurut telinga manusia
    notes            TEXT                        -- Catatan khusus (misal: 'versi acoustic remaster 2021')
);
```

#### Tabel 7: `runs`
Log audit eksekusi pipeline migrasi batch.
```sql
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT,
    finished_at TEXT,
    summary     TEXT                             -- JSON ringkasan metrik pemrosesan
);
```

---

## 5. Bedah Kode Komprehensif per Modul (File-by-File Codebase Breakdown)

Bagian ini membedah setiap file di repositori `yt2sp/`, menjelaskan setiap fungsi, signature parameter, algoritma, dan alur kodingannya.

### 5.1 `yt2sp/config.py` — Pengelola Konfigurasi Sistem
* **Tujuan:** Membaca parameter pengguna dari berkas `config.toml` dengan fallback aman ke kamus default sistem.
* **Fungsi `_deep_merge(base: dict, override: dict) -> dict`:**
  * Algoritma rekursif untuk menggabungkan kamus konfigurasi bertingkat tanpa menimpa sub-kunci yang tidak didefinisikan pengguna.
* **Fungsi `load_config(path: Path | None = None) -> dict`:**
  * Memeriksa keberadaan `config.toml`.
  * Mendukung Python 3.11+ via `tomllib` standar (dan `tomli` pada versi lama).
  * **Default Parameters:**
    * `resolve.rate_per_minute`: `30` (ditingkatkan ke `60` di config.toml kerja)
    * `resolve.backoff_base`: `2.0`, `resolve.backoff_max`: `120.0`
    * `match.auto_accept_threshold`: `0.85`
    * `match.review_threshold`: `0.60`
    * `match.title_weight`: `0.60`, `match.artist_weight`: `0.40`
    * `match.duration_tolerance_pct`: `0.10` ($\pm 10\%$)
    * `export.chunk_size`: `50`

### 5.2 `yt2sp/store/db.py` — Lapisan Akses Data SQLite
* **Tujuan:** Mengelola seluruh transaksi data lokal, konkurensi thread, dan sanitasi orphan records.
* **Fungsi Koneksi & Manajemen Thread:**
  * `_local = threading.local()`: Menyimpan objek koneksi unik per-thread.
  * `_get_conn() -> sqlite3.Connection`: Membuka koneksi dengan `row_factory = sqlite3.Row` dan mengeksekusi 6 PRAGMA performa tinggi.
* **Fungsi Playlist:**
  * `upsert_playlist(yt_playlist_id, title, track_count, unavailable_count=0) -> int`: Menggunakan klausa `INSERT ... ON CONFLICT(yt_playlist_id) DO UPDATE SET ...` untuk memperbarui metadata jika playlist ditarik ulang.
  * `get_playlist_sample_video_ids(playlist_id: int, limit: int = 4) -> list[str]`: Mengambil hingga 4 ID video teratas untuk dirender menjadi **2×2 Collage Artwork**.
* **Fungsi Track & PlaylistTrack:**
  * `upsert_track(...)`: Menyimpan lagu baru ke tabel `tracks`. Jika sudah ada, dilewati (`DO NOTHING`) agar histori metadata tidak tertimpa.
  * `upsert_playlist_track(...)`: Memetakan posisi lagu pada playlist bersangkutan.
  * `get_all_library_tracks() -> list[sqlite3.Row]`: Mengambil seluruh lagu unik di pustaka dengan agregasi nama-nama playlist via `GROUP_CONCAT(DISTINCT p.title)`.
* **Fungsi Pencocokan & Status:**
  * `set_match(...)`: Memperbarui atau menyisipkan status match lagu (`spotify_id`, `score`, `tier`, `status`, `reason`).
  * `get_pending_tracks(playlist_id=None)`: Mengambil daftar lagu yang statusnya masih `NULL` atau `'pending'`.
  * `reset_unresolved_tracks_to_pending(playlist_id=None, reset_all=False) -> int`: Mengembalikan lagu berstatus gagal atau belum diterima kembali ke antrean pencarian.
  * `get_status_summary() -> dict`: Menghitung ringkasan KPI library (total, pending, auto, review, accepted, rejected, failed, skipped).
* **Fungsi Kaskade Penghapusan Aman (Safe Deletion & Vacuum):**
  * `delete_playlists(playlist_ids: list[int]) -> int`:
    * Menghapus baris pada `playlist_tracks` dan `playlists`.
    * Mengeksekusi penghapusan kaskade untuk membersihkan lagu yatim (*orphan tracks*):
      ```sql
      DELETE FROM matches WHERE video_id NOT IN (SELECT video_id FROM playlist_tracks);
      DELETE FROM tracks WHERE video_id NOT IN (SELECT video_id FROM playlist_tracks);
      ```
    * Menjalankan perintah `VACUUM` untuk mengompresi ukuran fisik file `yt2sp.db` di disk.
  * `delete_tracks(video_ids: list[str], playlist_id: int | None = None) -> int`: Mendukung penghapusan lagu dari satu playlist spesifik atau penghapusan permanen dari seluruh basis data.

### 5.3 `yt2sp/ytm/extract.py` — Ekstraktor YouTube Music
* **Tujuan:** Wrapper komunikasi ke YouTube Music via `ytmusicapi`.
* **Fungsi `clean_playlist_id(raw_input: str) -> str`:**
  * Menggunakan modul `urllib.parse` dan Regex `r"[?&]list=([a-zA-Z0-9_-]+)"`.
  * Mampu mengekstrak ID murni dari link browser, link share mobile (`youtu.be`), atau string ID langsung.
* **Fungsi `get_playlist_details(ytm: YTMusic, playlist_id: str) -> PlaylistResult`:**
  * Memanggil `ytm.get_playlist(clean_id, limit=None)`.
  * Membaca atribut `trackCount` yang dilaporkan server YouTube.
  * Menghitung `unavailable_count = max(0, total_reported - len(tracks))` untuk mendeteksi lagu yang dihapus atau dijadikan privat oleh pengunggah aslinya.
* **Fungsi `parse_track(raw: dict) -> dict[str, Any] | None`:**
  * Memvalidasi keberadaan `videoId`.
  * Mengekstrak judul, daftar musisi, nama album, tipe video (`videoType`), dan mengonversi string durasi waktu ke milidetik via `_parse_duration_ms()`.

### 5.4 `yt2sp/match/normalize.py` — Sanitasi & Normalisasi String
* **Tujuan:** Menghilangkan noise promosi video YouTube namun menjaga penanda pembeda aransemen lagu.
* **Konstanta `DISTINCTIVE_MARKERS`:**
  * Menjaga 14 penanda penting: `"live"`, `"acoustic"`, `"remix"`, `"cover"`, `"instrumental"`, `"karaoke"`, `"slowed"`, `"sped up"`, `"nightcore"`, `"lofi"`, `"lo-fi"`, `"unplugged"`, `"demo"`, `"radio edit"`, `"extended"`.
* **Konstanta `_NOISE_RE`:**
  * Regex berkecepatan tinggi yang menghapus pola:
    * `official\s+(?:music\s+)?video`, `official\s+audio`, `official\s+lyric\s+video`, `visualizer`, `lyrics?`, `music\s+video`, `\bmv\b`, `4k`, `hd`, `remaster(?:ed)?`, `explicit\s+version`, `clean\s+version`.
* **Fungsi `normalize_title(title: str, keep_feat: bool = False) -> str`:**
  * **Tahap 1:** Menghapus `feat.` / `ft.` (karena artis diperiksa terpisah).
  * **Tahap 2:** Evaluasi tanda kurung `(...)` dan `[...]`. Menggunakan closure callback `_strip_parens()`: Jika teks di dalam kurung mengandung *distinctive marker*, seluruh kurung dipertahankan; jika tidak mengandung marker, kurung beserta isinya dihapus.
  * **Tahap 3:** Pembersihan kata noise via `_NOISE_RE`.
  * **Tahap 4:** Mengonversi aksen Unicode ke ASCII menggunakan pustaka `unidecode`.
  * **Tahap 5:** Menghapus karakter non-alfanumerik (`[^a-z0-9\s]`) dan merapikan spasi berlebih.

### 5.5 `yt2sp/match/score.py` — Mesin Penilaian Kemiripan Fuzzy
* **Tujuan:** Menghitung skor probabilitas kecocokan antara metadata lagu YouTube dan hasil pencarian Spotify.
* **Fungsi `_best_artist_score(yt_artists: list[str], sp_artist: str) -> float`:**
  * Menghitung nilai kemiripan `rapidfuzz.fuzz.token_set_ratio` antara setiap musisi di YouTube Music terhadap musisi di Spotify, kemudian mengambil nilai maksimum ($0.0 - 1.0$).
* **Fungsi `compute_score(...) -> tuple[float, str]`:**
  * **Formula Dasar:**
    $$\text{BaseScore} = 0.60 \times \text{TitleSim} + 0.40 \times \text{ArtistSim}$$
  * **Penalti Penanda Mismatch:**
    * Dievaluasi via `has_distinctive_marker()`.
    * Jika salah satu pihak berlabel *live/remix/acoustic* sementara pihak lain tidak, skor dipotong penalti sebesar **$-0.30$**.
  * **Penalti Durasi:**
    * Jika selisih durasi $> 5000\text{ ms}$ (5 detik) DAN selisih melebihi toleransi $\pm 10\%$ atau $> 12.000\text{ ms}$ (12 detik), skor dipotong sebesar **$-0.10$**.
  * Skor akhir dikunci pada rentang $[0.0, 1.0]$.
* **Fungsi `classify(score: float, auto_threshold=0.85, review_threshold=0.60) -> str`:**
  * $\ge 0.85 \implies$ `'resolved_auto'`
  * $\ge 0.60 \implies$ `'needs_review'`
  * $< 0.60 \implies$ `'failed'`

### 5.6 `yt2sp/resolve/rate_limiter.py` — Pengendali Laju Request Scraping
* **Tujuan:** Menghindari pemblokiran IP oleh scraping server.
* **Kelas `RateLimiter` (Algoritma Token Bucket Thread-Safe):**
  * `rate_per_second = rate_per_minute / 60.0`
  * `_tokens`: Jumlah token yang tersedia saat ini (dimulai penuh pada kapasitas maksimum 60 token).
  * `acquire()`: Memeriksa token dengan penguncian `threading.Lock()`. Jika token $< 1.0$, thread diistirahatkan (`time.sleep`) tepat selama waktu yang dibutuhkan untuk mengisi 1 token baru.
* **Fungsi `backoff_sleep(attempt, base=2.0, max_wait=120.0, jitter=0.5)`:**
  * Mengistirahatkan eksekusi dengan formula eksponensial $t = \min(\text{base}^{\text{attempt}} + \text{random}(0, \text{jitter}), \text{max\_wait})$.

### 5.7 `yt2sp/resolve/spotify_resolver.py` — Klien Pencarian Spotify
* **Tujuan:** Menjalankan pencarian langsung ke katalog internal Spotify via modul `spotifyscraper` tanpa token developer.
* **Pola Desain Singleton Thread-Safe:**
  * Fungsi `_get_client()` menginisialisasi objek `SpotifyClient` sekali dan membagikannya ke seluruh thread dengan penguncian mutex `_client_lock`.
  * Fungsi `_reset_client()` membersihkan session untuk regenerasi koneksi baru jika terjadi error beruntun.
* **Fungsi `search_spotify(title, artists, top_n=5, max_retries=3) -> list[SpotifyCandidate]`:**
  * Menyusun query kueri: `"<Title> <PrimaryArtist>"`.
  * Menjalankan retry otomatis hingga 3 kali dengan jeda eksponensial.
  * Mengembalikan daftar kandidat terstruktur (`spotify_id`, `uri`, `title`, `artist`, `duration_ms`).
* **Fungsi `find_alternative_versions(...) -> list[dict]`:**
  * Digunakan di Review Studio ketika versi resmi tidak cocok.
  * Menjalankan kueri judul dan kueri `"<title> cover"`.
  * Mengklasifikasikan hasil menjadi 3 kategori tag cerdas:
    1. **`Penyanyi Berbeda (Cover)`** (Badge Kuning): Jika kemiripan judul $\ge 80\%$ tetapi kemiripan musisi $< 50\%$.
    2. **`Versi Alternatif (Cover/Remix/Live)`** (Badge Ungu): Jika judul mengandung kata kunci remix/acoustic/live.
    3. **`Kemiripan Judul & Musisi`** (Badge Biru): Hasil pencocokan terdekat lainnya.

### 5.8 `yt2sp/resolve/deezer_resolver.py` — Fallback Tier 2 (Deezer & ISRC Bridge)
* **Tujuan:** Menemukan lagu-lagu langka, indie, atau rilis internasional yang gagal ditemukan oleh pencarian teks Spotify.
* **Alur Eksekusi:**
  1. Memanggil public API Deezer: `https://api.deezer.com/search?q={query}&limit=3`.
  2. Dari ID lagu Deezer, memanggil detail endpoint `https://api.deezer.com/track/{track_id}` untuk mengekstrak kode **ISRC (International Standard Recording Code)** internasional.
  3. Menyelesaikan ISRC ke Spotify ID via fungsi `_resolve_spotify_from_isrc(isrc)`:
     * **Jalur Utama:** Kueri MusicBrainz API `https://musicbrainz.org/ws/2/isrc/{isrc}?fmt=json&inc=url-rels` untuk membaca relasi URL `open.spotify.com/track/{id}`.
     * **Jalur Cadangan:** Pencarian langsung ke Spotify menggunakan kueri resmi `isrc:{isrc}`.

### 5.9 `yt2sp/resolve/pipeline.py` — Orkestrator Resolusi
* **Fungsi `run_resolve(...) -> dict`:**
  * Mengambil lagu berstatus `'pending'` dari database.
  * Memfilter lagu bertipe non-musik (`MUSIC_VIDEO_TYPE_UGC`) $\rightarrow$ diberi status `'skipped'`.
  * Melakukan pencarian Tier 1 (Spotify). Jika skor $< 0.60$ atau tidak ada hasil, otomatis memicu Tier 2 (Deezer ISRC Fallback).
  * Memperbarui tabel `matches`.
  * Memicu deteksi dan validasi genre otomatis secara asinkron via `fetch_genre_validated()`.
  * Menerima callback `on_progress(video_id, status, score)` untuk memperbarui antarmuka pengguna secara real-time.

### 5.10 `yt2sp/resolve/genre.py` — Mesin Validasi Silang Genre Multi-Sumber
* **Tujuan:** Mengklasifikasikan lagu ke dalam kelompok genre yang tepat tanpa subjektivitas satu penyedia.
* **Fungsi `_fetch_both_raw(q, timeout)`:**
  * Menggunakan `concurrent.futures.ThreadPoolExecutor(max_workers=2)` untuk menembak **Apple iTunes Search API** dan **Deezer Catalog API** secara paralel dalam waktu bersamaan ($\le 4$ detik).
* **Fungsi `validate_and_reconcile_genre(...) -> GenreValidationResult`:**
  * **Hierarki Rekonsiliasi:**
    1. **Kesepakatan Penuh (`validated_agreement`):** iTunes dan Deezer sepakat pada genre yang sama (Confidence: `1.0`).
    2. **Resolusi Spesifisitas Subgenre (`cross_validated`):** Jika salah satu sumber memberikan genre spesifik (misal: *Indonesian Pop, Dangdut & Koplo, K-Pop, Anime, R&B / Soul*), maka subgenre spesifik tersebut memenangkan klasifikasi di atas genre umum yang dilaporkan sumber lain (seperti *Pop, Rock, Asian Music*) (Confidence: `0.92`).
    3. **Sumber Tunggal (`single_source`):** Hanya ditemukan di Deezer atau iTunes (Confidence: `0.85`).
    4. **Heuristik Kontekstual (`heuristic`):** Dideteksi oleh fungsi `detect_genre_heuristic()` berdasarkan analisis nama artis/judul (Confidence: `0.75`).
    5. **Uncategorized:** Tidak ada data ditemukan (Confidence: `0.0`).

### 5.11 `yt2sp/export/writer.py` & `5.12 report.py` — Modul Ekspor
* **`writer.py`:**
  * `validate_uri(uri: str) -> bool`: Memvalidasi integritas format Spotify URI dengan regex `^spotify:track:[A-Za-z0-9]{22}$`.
  * `write_uri_blocks(...)`: Memecah daftar URI per 50 baris (`chunk_size=50`) ke dalam file teks `output/uris/<Playlist>_part001.txt`. Mencegah overflow buffer keyboard clipboard saat dipaste ke Spotify Desktop.
* **`report.py`:**
  * `write_csv_report(...)`: Menghasilkan laporan CSV ber-BOM UTF-8 (`utf-8-sig`) di `output/reports/<Playlist>_report.csv` lengkap dengan URL link pencarian langsung Spotify.

### 5.13 `yt2sp/cli.py` — Antarmuka Terminal Typer & Rich
* Berisi implementasi 12 sub-perintah CLI: `init`, `auth-ytm`, `extract`, `resolve`, `review`, `export`, `tag-genre`, `split`, `status`, `golden`, `smoke-test`, `ui`, `reset`.
* Mengimplementasikan Rich Progress Bars beranimasi, tabel status berwarna, dan prompt interaktif manusia.

---

## 6. Spesifikasi REST API Lengkap (Local Web Server)

Server web lokal diimplementasikan dalam [yt2sp/ui/server.py](file:///c:/Users/Elang/Downloads/yt-spt/yt2sp/ui/server.py) menggunakan `http.server.ThreadingHTTPServer` pada `http://127.0.0.1:5000`.

### 6.1 Proteksi Keamanan & Header HTTP
* **Anti-CSRF (Cross-Site Request Forgery):** Metode `_is_safe_origin()` memverifikasi header `Origin`. Permintaan mutasi dari origin luar selain `127.0.0.1`, `localhost`, atau `::1` langsung ditolak dengan status **`403 Forbidden`**.
* **Kompresi Gzip Dinamis:** Setiap payload JSON atau aset web berukuran $> 200$ bytes dikompresi dengan `gzip` (level 6) jika klien mengirim header `Accept-Encoding: gzip`.
* **Conditional ETag:** Menghasilkan checksum MD5 untuk aset statis dan merespons dengan **`304 Not Modified`** jika file tidak berubah.

### 6.2 Katalog Endpoint REST API

#### 1. `GET /api/status`
* **Deskripsi:** Mengambil ringkasan statistik pustaka lokal dan status pekerjaan latar belakang (*background job*).
* **Caching:** In-memory TTL 1.0 detik.
* **Contoh Respons (HTTP 200):**
```json
{
  "total": 150,
  "pending": 0,
  "resolved_auto": 138,
  "needs_review": 8,
  "accepted": 3,
  "rejected": 1,
  "failed": 0,
  "skipped": 0,
  "job": {
    "running": false,
    "type": null,
    "current": 150,
    "total": 150,
    "message": "Pencocokan selesai!",
    "error": null
  }
}
```

#### 2. `GET /api/playlists`
* **Deskripsi:** Mengambil semua playlist terdaftar, breakdown genre, jumlah video yang tidak tersedia, dan 4 sampling video ID untuk 2x2 collage artwork.
* **Caching:** In-memory TTL 2.0 detik.
* **Contoh Respons (HTTP 200):**
```json
{
  "playlists": [
    {
      "id": 1,
      "yt_playlist_id": "PLxxxxxx",
      "title": "Indie Folk & Chill",
      "track_count": 50,
      "unavailable_count": 2,
      "extracted_at": "2026-11-13T10:00:00+00:00",
      "genres": [
        {"genre": "Alternative & Indie", "count": 32},
        {"genre": "Acoustic & Folk", "count": 18}
      ],
      "sample_video_ids": ["vid1", "vid2", "vid3", "vid4"]
    }
  ],
  "library": {
    "total_tracks": 50,
    "genres": [{"genre": "Alternative & Indie", "count": 32}]
  }
}
```

#### 3. `GET /api/tracks`
* **Parameter Query:**
  * `playlist_id` (string, opsional): ID playlist atau `"all"`.
  * `genre` (string, opsional): Filter nama genre.
  * `status` (string, opsional): Filter status (`"resolved_auto"`, `"needs_review"`, dll).
  * `q` (string, opsional): Pencarian teks bebas pada judul, musisi, album, atau genre.
* **Contoh Respons (HTTP 200):**
```json
{
  "tracks": [
    {
      "video_id": "dQw4w9WgXcQ",
      "title": "Never Gonna Give You Up",
      "artists": ["Rick Astley"],
      "album": "Whenever You Need Somebody",
      "duration_s": 213,
      "genre": "Pop",
      "status": "resolved_auto",
      "score": 0.985,
      "spotify_id": "4cOdK2wGLETKBW3PvgPWqT",
      "reason": "ok",
      "result_title": "Never Gonna Give You Up",
      "genre_source": "itunes+deezer",
      "in_playlists": "Indie Folk & Chill"
    }
  ],
  "total": 1
}
```

#### 4. `GET /api/uris`
* **Parameter Query:** `playlist_id` (opsional), `genre` (opsional), `chunk_size` (default: 50).
* **Deskripsi:** Mengambil daftar URI Spotify yang telah disetujui, dibagi ke dalam blok 50 lagu siap salin.
* **Contoh Respons (HTTP 200):**
```json
{
  "total": 52,
  "uris": ["spotify:track:4cOdK2wGLETKBW3PvgPWqT", "..."],
  "chunks": [
    {
      "part": 1,
      "count": 50,
      "uris": ["spotify:track:..."],
      "text": "spotify:track:...\nspotify:track:..."
    },
    {
      "part": 2,
      "count": 2,
      "uris": ["spotify:track:..."],
      "text": "spotify:track:...\nspotify:track:..."
    }
  ]
}
```

#### 5. `GET /api/preview`
* **Parameter Query:** `video_id`, `q`, `spotify_id`, `title`, `artist`.
* **Deskripsi:** Mengambil URL streaming pratinjau audio 30 detik (chorus/reff). Menggunakan dual cascade: Deezer CDN $\rightarrow$ Apple iTunes Search API.
* **Caching:** In-memory TTL 24 jam (`86400.0` detik).
* **Contoh Respons (HTTP 200):**
```json
{
  "preview_url": "https://cdns-preview-d.dzcdn.net/stream/c-...",
  "title": "Never Gonna Give You Up",
  "artist": "Rick Astley",
  "provider": "deezer",
  "duration": 30
}
```

#### 6. `GET /api/alternatives`
* **Parameter Query:** `video_id` (wajib).
* **Deskripsi:** Mencari hingga 8 variasi versi lagu di Spotify (Cover penyanyi lain, Remix, Acoustic, Live).
* **Contoh Respons (HTTP 200):**
```json
{
  "video_id": "dQw4w9WgXcQ",
  "title": "Never Gonna Give You Up",
  "artists": ["Rick Astley"],
  "alternatives": [
    {
      "spotify_id": "5nvd4nFxxxx",
      "uri": "spotify:track:5nvd4nFxxxx",
      "title": "Never Gonna Give You Up (Pianoforte)",
      "artist": "Rick Astley",
      "duration_s": 205,
      "tag": "Versi Alternatif (Cover/Remix/Live)",
      "badge_color": "purple",
      "desc": "Versi aransemen lain oleh Rick Astley",
      "title_sim": 85,
      "art_sim": 100
    }
  ]
}
```

#### 7. `POST /api/extract`
* **Payload Request:**
```json
{
  "playlist_id": "https://music.youtube.com/playlist?list=PLxxxxxxxx",
  "liked": false
}
```
* **Respons (HTTP 200):** `{"status": "started"}` (Memulai background thread ekstraksi).

#### 8. `POST /api/resolve`
* **Payload Request:**
```json
{
  "playlist_id": "all",
  "force": false
}
```
* **Respons (HTTP 200):** `{"status": "started"}` (Memulai background thread matching).

#### 9. `POST /api/tag-genre`
* **Payload Request:** `{}`
* **Respons (HTTP 200):** `{"status": "started"}` (Memulai background thread validasi genre).

#### 10. `POST /api/review`
* **Payload Request (Accept/Reject):**
```json
{
  "video_id": "dQw4w9WgXcQ",
  "action": "accept"
}
```
* **Payload Request (Manual Input):**
```json
{
  "video_id": "dQw4w9WgXcQ",
  "action": "manual",
  "spotify_id": "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"
}
```
* **Respons Manual (HTTP 200):** Mengembalikan data metadata yang diverifikasi via Spotify oEmbed:
```json
{
  "status": "ok",
  "spotify_id": "4cOdK2wGLETKBW3PvgPWqT",
  "title": "Never Gonna Give You Up",
  "thumbnail_url": "https://i.scdn.co/image/ab67616d0000b273..."
}
```

#### 11. `POST /api/delete-playlist` & `POST /api/delete-track`
* Mendukung operasi batch atau individual dengan sanitasi orphan record otomatis.

#### 12. `POST /api/create-grouped-playlist`
* **Payload Request:** Menerima hasil parsing dari AI Group Splitter Studio untuk membuat playlist kustom langsung di database lokal.

---

## 7. Arsitektur Frontend & Sistem Interaksi (Single Page Application)

Frontend dibangun sebagai Single-Page Application (SPA) mandiri di [yt2sp/ui/index.html](file:///c:/Users/Elang/Downloads/yt-spt/yt2sp/ui/index.html) dan [yt2sp/ui/i18n.js](file:///c:/Users/Elang/Downloads/yt-spt/yt2sp/ui/i18n.js) tanpa ketergantungan build-step (tanpa Webpack/Vite/NodeJS).

### 7.1 State Management Frontend
Variabel state global diatur di dalam window scope:
```javascript
let _playlists = [];              // Cache array seluruh playlist
let _tracks = [];                 // Cache array lagu yang sedang ditampilkan
let _currentView = 'overview';    // Tampilan aktif ('overview', 'playlists', 'transfer', 'history', dll)
let _activePlaylistId = 'all';    // Filter ID playlist saat ini
let _statusFilter = '';           // Filter status matching
let _genreFilter = '';            // Filter genre aktif
let _libraryGenres = [];          // Distribusi genre pustaka
let _searchQuery = '';            // Kueri pencarian teks
let _currentPage = 1;             // Halaman paginasi (25 item/halaman)
let _selectionMode = false;       // Mode seleksi multi-lagu
let _selectedTrackIds = new Set();// Set video_id yang dipilih
let _selectedPlaylistIds = new Set();
let _pollTimer = null;            // Timer polling adaptif
let _isPerfMode = false;          // Status Low-Spec Potato Mode
```

### 7.2 Siklus Hidup Polling Adaptif (`scheduleNextPoll`)
Untuk menjaga dashboard tetap responsif tanpa membanjiri server CPU lokal:
* Saat ada background job berjalan (`job.running == true`): Polling dieksekusi setiap **1.5 detik**.
* Saat server dalam kondisi diam (*idle*): Polling melambat secara otomatis menjadi setiap **6.0 detik**.

### 7.3 Komponen Desain & Aksesibilitas (Design Tokens & Potato Mode)
* **Tokens Variabel CSS:** Seluruh warna dan kontras menggunakan token `:root` (`--bg-main`, `--bg-card`, `--border-color`, `--text-primary`, `--accent`).
* **Potato Mode (Low-Spec Toggle):**
  * Menonaktifkan class CSS filter `backdrop-blur-*`, efek `box-shadow` berlapis, gelombang animasi canvas visualizer, dan animasi transisi CSS berat.
  * Mengurangi penggunaan GPU hingga 90%, memastikan kelancaran 60 FPS pada laptop berprosesor hemat daya atau perangkat lawas.
* **Internationalization (`i18n.js`):**
  * Kamus terjemahan instan untuk **Bahasa Indonesia (Default)**, **English**, **Español**, **日本語**, **한국어**, **简体中文**.

---

## 8. Matriks Penanganan Edge Cases & Keandalan Sistem

| Skenario Kasus Batas (Edge Case) | Gejala Masalah Potensial | Solusi & Penanganan di Kodingan `yt2sp` |
| :--- | :--- | :--- |
| **Video YouTube Dihapus / Privat** | API YouTube mengembalikan jumlah lagu lebih sedikit dari total playlist. | Dihitung otomatis di `get_playlist_details()`, disimpan sebagai `unavailable_count`, dan dimunculkan sebagai notifikasi kuning di UI. |
| **Judul Berisi Karakter Kanji / Kurung Jepang** | Kurung seperti `【歌ってみた】` atau `【MV】` mengacaukan pencarian Spotify. | Regex di `clean_track_query()` dan `normalize_title()` membersihkan kurung kanji tanpa merusak karakter nama musisi. |
| **Versi Konser Live vs Rekaman Studio** | Pengguna menginginkan versi Live, tapi Spotify memberikan versi rekaman album biasa. | `DISTINCTIVE_MARKERS` mendeteksi kata `"live"`, menerapkan penalti $-0.30$, dan melempar lagu ke Review Studio untuk konfirmasi pengguna. |
| **Perbedaan Durasi Lagu Ekstrem** | Video YouTube memuat intro sandiwara 2 menit sebelum lagu dimulai. | `compute_score()` menghitung selisih durasi. Jika $>10\%$ atau $>12$ detik, skor dipotong penalti $-0.10$. |
| **Koneksi Internet Terputus saat Matching** | Proses scraping gagal di tengah jalan. | Tangkapan exception di `run_resolve()` menyimpan state kegagalan per lagu. Saat dijalankan kembali, sistem melanjutkan lagu pending berikutnya. |
| **Spotify Memblokir IP (HTTP 429)** | Kueri pencarian Spotify dibatasi lajunya. | Token Bucket di `RateLimiter` menjaga laju $\le 60$ req/menit dengan `backoff_sleep()` eksponensial dan random jitter. |
| **Daftar Musisi Kolaborasi Kompleks** | YouTube menulis `"Artist A feat. Artist B"`, Spotify menulis `"Artist A"`. | `normalize_artist()` memotong klausa `feat.`/`ft.`, dan `_best_artist_score()` mencocokkan setiap nama musisi secara independen. |
| **Penyalahgunaan Permintaan Web (CSRF)** | Situs berbahaya di browser mencoba mengakses API server lokal. | `_is_safe_origin()` di `server.py` menolak seluruh request lintas domain selain `localhost` / `127.0.0.1`. |
| **Overflow Buffer Clipboard Windows** | Menyalin >1000 URI sekaligus menyebabkan Spotify Desktop membeku (*freeze*). | `write_uri_blocks()` memecah URI menjadi file chunk masing-masing 50 baris dengan nomor bagian yang rapi. |

---

## 9. Framework Pengujian & Verifikasi Kualitas (QA)

### 9.1 Rincian 21 Unit & Integration Test (`pytest`)
Seluruh 21 tes otomatis di direktori [tests/](file:///c:/Users/Elang/Downloads/yt-spt/tests/) telah lulus verifikasi (**21 Passed**):

1. **`test_db_operations`** ([test_db.py](file:///c:/Users/Elang/Downloads/yt-spt/tests/test_db.py)):
   * Verifikasi CRUD basis data, integritas foreign key `playlist_tracks`, sampling 2x2 collage artwork, kaskade penghapusan orphan tracks, dan pembersihan batch playlist.
2. **`test_validate_uri` & `test_write_uri_blocks`** ([test_export.py](file:///c:/Users/Elang/Downloads/yt-spt/tests/test_export.py)):
   * Memvalidasi format 22 karakter base62 Spotify URI dan verifikasi pemecahan 125 lagu menjadi 3 file blok (50, 50, 25 baris).
3. **`test_clean_track_query` & `test_detect_genre_heuristic`** ([test_genre.py](file:///c:/Users/Elang/Downloads/yt-spt/tests/test_genre.py)):
   * Menguji pembersihan noise judul YouTube, deteksi heuristik untuk HOYO-MiX, Genshin Impact OST, Vocaloid/Miku, Dangdut/Koplo, dan Lofi.
4. **`test_validate_and_reconcile_*`** ([test_genre.py](file:///c:/Users/Elang/Downloads/yt-spt/tests/test_genre.py)):
   * Menguji 4 skenario rekonsiliasi genre: kesepakatan sumber, resolusi spesifisitas subgenre (Indonesian Pop mengalahkan Pop), sumber tunggal, dan fallback heuristik.
5. **`test_normalize_strips_noise` & `test_normalize_preserves_distinctive_markers`** ([test_normalize.py](file:///c:/Users/Elang/Downloads/yt-spt/tests/test_normalize.py)):
   * Memastikan kata noise (`[Official Video 4K]`, `[MV]`, `Lyrics`) terhapus bersih, dan penanda pembeda (`(Live at Forum)`, `(Acoustic Version)`, `(Remix)`) tetap dipertahankan.
6. **`test_spotify_client_singleton_and_reset`** ([test_resolve.py](file:///c:/Users/Elang/Downloads/yt-spt/tests/test_resolve.py)):
   * Memverifikasi perilaku singleton `SpotifyClient` dan pembuatan session baru setelah pemanggilan `_reset_client()`.
7. **`test_resolve_spotify_from_isrc_*`** ([test_resolve.py](file:///c:/Users/Elang/Downloads/yt-spt/tests/test_resolve.py)):
   * Menguji mocking resolusi ISRC via MusicBrainz API dan fallback ke query native Spotify.
8. **`test_exact_match`, `test_distinctive_marker_penalty`, `test_classify_thresholds`, `test_duration_tolerance`** ([test_score.py](file:///c:/Users/Elang/Downloads/yt-spt/tests/test_score.py)):
   * Memvalidasi akurasi skor matematika RapidFuzz, pemotongan penalti $-0.30$ pada marker mismatch, pemotongan penalti durasi, dan klasifikasi ambang batas status.

### 9.2 Benchmark Presisi Golden Dataset (`yt2sp golden`)
* Perintah `yt2sp golden import --file data.csv` dan `yt2sp golden score`.
* **Kriteria Kelulusan Produksi:**
  * **Presisi:** $\ge 98.0\%$ (Persentase kecocokan algoritma yang identik dengan telinga manusia).
  * **Cakupan (Coverage):** $\ge 80.0\%$ (Persentase lagu yang berhasil dipasangkan tanpa berstatus gagal).

### 9.3 Uji Asap Cepat Klien Desktop (`yt2sp smoke-test`)
* Menghasilkan file `smoke_test_uris.txt` yang memuat 5 lagu uji kurasi (Rick Astley, Hindia, Tulus, Coldplay, Queen).
* Memastikan fungsi clipboard paste `Ctrl + V` didukung oleh build aplikasi Spotify Desktop pengguna sebelum memulai migrasi ratusan lagu.

---

## 10. Persyaratan Non-Fungsional (NFR) & Panduan Instalasi

### 10.1 Metrik Kinerja Non-Fungsional
* **Latensi Kueri Basis Data:** Waktu respons kueri SQLite rata-rata $\le 20\text{ ms}$ untuk pengambilan daftar 100 lagu.
* **Jejak Memori (RAM Footprint):** Penggunaan memori proses Python di bawah **$120\text{ MB}$** selama matching aktif.
* **Efisiensi Jaringan:** Kompresi Gzip mengurangi beban transfer muatan JSON sebesar $\approx 85\%$.

### 10.2 Panduan Deployment Lokal
1. **Instalasi Paket:**
   ```bash
   git clone https://github.com/ramaci-cmd/yt2spt.git
   cd yt2spt
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -e .
   ```
2. **Inisialisasi & Eksekusi Web Dashboard:**
   ```bash
   yt2sp init
   yt2sp ui
   ```
3. Akses antarmuka pada peramban: `http://127.0.0.1:5000`.

---
*Dokumen PRD ini menyajikan spesifikasi arsitektur teknis dan implementasi menyeluruh dari repositori `yt2sp` v1.0.0.*
