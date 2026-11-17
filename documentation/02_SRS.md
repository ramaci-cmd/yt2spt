# 02. SYSTEM & SOFTWARE REQUIREMENTS SPECIFICATION (SRS)
# Spotify2YTM (`sp2yt` / `yt2sp` v2.0.0) — High-Precision Reverse Migration Platform (Spotify → YouTube Music)

---

## 1. System Overview

### 1.1 Gambaran Umum Sistem & Cara Kerja
Spotify2YTM (`sp2yt` / `yt2sp`) beroperasi sebagai pipeline *Extract, Transform, Reconcile, Load* (ETL) lokal yang memigrasikan pustaka musik dari Spotify ke YouTube Music. Sistem berjalan sepenuhnya di komputer lokal pengguna (*on-premises / local-first*), memanfaatkan antarmuka baris perintah (CLI) atau peramban web modern yang terhubung ke server HTTP lokal ringan.

```
[Spotify Playlist] ──(spotifyscraper)──► [Ingestion Engine]
                                               │
                                               ▼
                                    [SQLite 3 WAL Local DB]
                                           ▲          │
                                           │          ▼
[Public Web APIs] ◄────────────── [Matching & Resolver Engine]
(YouTube Music/iTunes/Deezer)                 │
                                               ▼
                                    [Review & Reconciliation Studio]
                                               │
                                               ▼
                              [YouTube Music Playlist Writer API]
                                               │
                                               ▼
                             [YouTube Music User Library Playlist]
```

### 1.2 Batasan Sistem (System Boundaries)
* **Lingkungan Host:** Sistem dieksekusi sebagai proses Python lokal pada mesin pengguna (Windows, macOS, Linux).
* **Komunikasi Eksternal:** Sistem melakukan panggilan HTTP keluar (HTTPS) hanya ke:
  - `open.spotify.com` / Spotify Public Endpoints (ekstraksi playlist tanpa token developer via `spotifyscraper`).
  - `music.youtube.com` / `youtubei` (pencarian katalog lagu/video, pembuatan playlist, dan penambahan item via `ytmusicapi`).
  - `api.deezer.com` (fallback genre dan pratinjau audio).
  - `itunes.apple.com` (kategorisasi genre dan fallback pratinjau audio).
* **Target Output:** Playlist YouTube Music resmi yang dibuat langsung di akun pengguna melalui sesi `ytm_auth.json`.

---

## 2. Technology Stack Inventory

Seluruh tumpukan teknologi diverifikasi secara langsung dari berkas konfigurasi repositori ([pyproject.toml](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/pyproject.toml), [config.toml](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/config.toml), dan *source code*).

### 2.1 Bahasa Pemrograman & Runtime
| Komponen | Spesifikasi | Alasan Pemilihan & Bukti di Repositori |
| :--- | :--- | :--- |
| **Python** | Version $\ge 3.11$ (Teruji di 3.14) | Mendukung modul standar modern `tomllib`, pengetikan statis `from __future__ import annotations`, dan performa eksekusi runtime tinggi. |
| **JavaScript** | Vanilla ES6+ | Menghilangkan kebutuhan NodeJS/NPM build step; dieksekusi langsung oleh peramban modern di [yt2sp/ui/index.html](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/index.html). |
| **HTML5 & CSS3** | Modern Standards | Menggunakan token variabel CSS (`:root`), Flexbox, CSS Grid, dan dukungan akselerasi GPU. |

### 2.2 Dependensi Inti Python (`Dependencies`)
Diverifikasi dari `pyproject.toml`:

```toml
dependencies = [
    "ytmusicapi>=1.12",
    "spotifyscraper>=3.9",
    "rapidfuzz>=3",
    "unidecode>=1.3",
    "typer>=0.12",
    "rich>=13",
    "requests>=2.31",
]
```

1. **`ytmusicapi` ($\ge 1.12$):** Pustaka reverse-engineered API YouTube Music internal. Memungkinkan pembacaan playlist publik, unlisted, dan liked songs tanpa kuota ketat Google Cloud Console.
2. **`spotifyscraper` ($\ge 3.9$):** Modul pencarian katalog web internal Spotify tanpa token developer atau client secret resmi.
3. **`rapidfuzz` ($\ge 3$):** Implementasi algoritma jarak Levenshtein dan *Token Set Ratio* berkinerja tinggi yang ditulis menggunakan C++ bindings, mengevaluasi ratusan string dalam beberapa milidetik.
4. **`unidecode` ($\ge 1.3$):** Transliterasi teks Unicode ke representasi ASCII murni (misal: aksen Latin, romaji, kanji dasar).
5. **`typer` ($\ge 0.12$):** Framework CLI modern berbasis Python type hints untuk membangun perintah terminal yang intuitif.
6. **`rich` ($\ge 13$):** Pustaka visualisasi terminal untuk merender progress bar animasi, tabel status berwarna, dan pesan interaktif.
7. **`requests` ($\ge 2.31$):** Klien HTTP fleksibel yang digunakan oleh dependensi pendukung.

### 2.3 Pustaka Standar Python Tanpa Dependensi Eksternal
* **`sqlite3`:** Mesin basis data transaksional relasional bawaan Python.
* **`http.server.ThreadingHTTPServer`:** Server HTTP multi-thread bawaan untuk melayani API REST dan file statis Web UI tanpa ketergantungan Flask, FastAPI, atau Uvicorn.
* **`urllib.request` & `urllib.parse`:** Panggilan jaringan ringan ke iTunes, Deezer, MusicBrainz, dan Spotify oEmbed.
* **`gzip`:** Kompresi HTTP on-the-fly untuk menghemat bandwidth transfer lokal.
* **`hashlib`:** Pembuatan MD5 checksum untuk header HTTP ETag (HTTP 304 Caching).
* **`concurrent.futures.ThreadPoolExecutor`:** Eksekusi panggilan multi-sumber secara paralel (misal: validasi silang iTunes dan Deezer secara bersamaan $\le 4$ detik).

### 2.4 Pustaka Frontend Pihak Ketiga (CDN Injected)
Diverifikasi dari tag `<head>` di [yt2sp/ui/index.html](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/index.html):
* **Tailwind CSS (`cdn.tailwindcss.com`):** Framework utilitas CSS instan tanpa proses kompilasi lokal.
* **Lucide Icons (`unpkg.com/lucide@latest`):** Koleksi ikon SVG modern dan konsisten untuk seluruh antarmuka.
* **Canvas Confetti (`cdn.jsdelivr.net/npm/canvas-confetti@1.9.2`):** Efek perayaan visual saat proses transfer atau pencocokan 100% selesai.
* **Web Fonts:** Font serif editorial bergaya majalah *Newsreader* dan sans-serif *Plus Jakarta Sans* dari Google Fonts.

---

## 3. Data & Storage Specification

### 3.1 Engine & Konfigurasi Penyimpanan
* **Engine:** SQLite versi 3.x.
* **Nama Berkas:** `yt2sp.db` (disertai berkas bantu `yt2sp.db-wal` dan `yt2sp.db-shm` saat aktif).
* **Lokasi Default:** Direktori kerja aktif saat eksekusi dijalankan.
* **Mode Jurnal:** **WAL (Write-Ahead Logging)** — Pembacaan (*read*) dari thread dashboard tidak memblokir penulisan batch (*write*) dari proses matching background.

### 3.2 PRAGMA Tuning Performa Ekstrem
Diverifikasi dari [yt2sp/store/db.py:21-26](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/store/db.py#L21-L26):
```sql
PRAGMA journal_mode=WAL;          -- Pembacaan dan penulisan konkuren tanpa lock contention
PRAGMA synchronous=NORMAL;         -- Optimalisasi flush disk tanpa mengorbankan integritas data
PRAGMA foreign_keys=ON;           -- Menjaga integritas relasional relasi playlist_tracks
PRAGMA cache_size=-64000;         -- Alokasi buffer cache RAM sebesar 64 MB
PRAGMA temp_store=MEMORY;         -- Menyimpan tabel sementara & operasi sort di memori RAM
PRAGMA mmap_size=268435456;       -- 256 MB Memory-Mapped I/O untuk throughput read instan
```

---

## 4. API Specification Overview

Server lokal menyediakan antarmuka REST API JSON melalui protokol HTTP/1.1 pada `http://127.0.0.1:5000`.

### 4.1 Ringkasan Katalog Endpoint

| Method | Endpoint Path | Tujuan Fungsional | Caching Policy | File Referensi |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/api/version` | Mengambil nomor versi dan engine aktif | In-Memory (No-Cache) | [server.py:214](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/server.py#L214) |
| **GET** | `/api/status` | Statistik status matching dan background job | In-Memory TTL 1.0s | [server.py:223](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/server.py#L223) |
| **GET** | `/api/playlists` | Daftar playlist, breakdown genre, & 4-sample IDs | In-Memory TTL 2.0s | [server.py:239](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/server.py#L239) |
| **GET** | `/api/tracks` | Daftar lagu dengan filter status, genre, & search | In-Memory TTL 2.0s | [server.py:275](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/server.py#L275) |
| **GET** | `/api/uris` | Spotify URIs terpecah ke dalam chunk 50 lagu | In-Memory TTL 2.0s | [server.py:347](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/server.py#L347) |
| **GET** | `/api/missing` | Daftar lagu gagal, ditolak, atau butuh review | Dynamic DB Query | [server.py:392](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/server.py#L392) |
| **GET** | `/api/alternatives` | Pencarian 8 variasi versi lagu di Spotify | On-Demand Search | [server.py:423](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/server.py#L423) |
| **GET** | `/api/preview` | URL streaming pratinjau audio 30 detik (reff) | In-Memory TTL 24 Jam | [server.py:440](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/server.py#L440) |
| **GET** | `/api/task-status` | Polling status thread background saat ini | In-Memory State | [server.py:563](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/server.py#L563) |
| **POST** | `/api/cancel` | Menghentikan paksa background matching/extract | Direct Mutation | [server.py:593](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/server.py#L593) |
| **POST** | `/api/extract` | Memulai thread penarikan playlist YouTube | Background Thread | [server.py:606](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/server.py#L606) |
| **POST** | `/api/resolve` | Memulai thread pencocokan katalog Spotify | Background Thread | [server.py:687](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/server.py#L687) |
| **POST** | `/api/tag-genre` | Memulai thread validasi silang genre | Background Thread | [server.py:767](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/server.py#L767) |
| **POST** | `/api/review` | Aksi manual review (accept, reject, manual ID) | Direct DB Mutation | [server.py:806](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/server.py#L806) |
| **POST** | `/api/choose-alternative` | Memilih satu lagu dari daftar rekomendasi alternatif | Direct DB Mutation | [server.py:916](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/server.py#L916) |
| **POST** | `/api/reset` | Mengosongkan data database ke kondisi nol | Direct DB Mutation | [server.py:943](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/server.py#L943) |
| **POST** | `/api/delete-playlist` | Menghapus satu atau banyak playlist (kaskade) | Direct DB Mutation | [server.py:952](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/server.py#L952) |
| **POST** | `/api/delete-track` | Menghapus lagu dari playlist atau database global | Direct DB Mutation | [server.py:984](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/server.py#L984) |
| **POST** | `/api/create-grouped-playlist` | Membuat playlist kustom hasil parser AI | Direct DB Mutation | [server.py:1014](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/server.py#L1014) |

*Rincian payload, skema JSON, dan response error didokumentasikan secara menyeluruh di [07_DATABASE_AND_API_SPECIFICATION.md](07_DATABASE_AND_API_SPECIFICATION.md).*

---

## 5. Security & Safety Specification

### 5.1 Pertahanan Anti-CSRF (Cross-Site Request Forgery)
Karena server lokal berjalan pada port statis (`5000`) tanpa session cookie atau login token, website berbahaya di internet berpotensi mengeksekusi request JavaScript (`fetch('http://127.0.0.1:5000/api/reset', {method: 'POST'})`) jika pengguna sedang membuka browser.

**Implementasi Pertahanan:**
Server mengimplementasikan metode `_is_safe_origin()` di [yt2sp/ui/server.py:125-133](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/server.py#L125-L133):
```python
def _is_safe_origin(self) -> bool:
    origin = self.headers.get("Origin")
    if not origin:
        return True  # Direct browser request / same-origin
    try:
        parsed = urllib.parse.urlparse(origin)
        return parsed.hostname in ("127.0.0.1", "localhost", "::1")
    except Exception:
        return False
```
Jika ada request dengan header `Origin` dari domain luar (misal: `https://evil-site.com`), server langsung memutus koneksi dengan respons **`403 Forbidden`**.

### 5.2 Sanitasi Input & Proteksi Path Traversal
* **Ekstraksi Playlist ID:** Input URL disaring via regex `[?&]list=([a-zA-Z0-9_-]+)` di `clean_playlist_id()`.
* **Sanitasi File Ekspor:** Karakter berbahaya pada judul playlist dibersihkan menggunakan regex `[\\/:*?"<>|]` di [writer.py:28](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/export/writer.py#L28) untuk mencegah eksploitasi pembuatan berkas di luar folder `output/`.
* **Static File Serving:** Pengambilan aset statis dibatasi secara ketat hanya pada berkas yang berada di dalam pohon direktori modul UI menggunakan objek `Path.resolve()`.

### 5.3 Manajemen Kredensial & Nol Rahasia (Zero-Secrets)
* Sistem tidak menyimpan `client_secret`, password, atau token OAuth jangka panjang.
* Berkas `ytm_auth.json` (jika dibuat oleh pengguna untuk mengakses Liked Songs pribadi) hanya disimpan secara lokal dan telah didaftarkan pada [.gitignore](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/.gitignore) sehingga tidak akan terunggah secara tidak sengaja ke git repository publik.
