# 00. PROJECT OVERVIEW & EXECUTIVE SUMMARY
# Spotify2YTM (`sp2yt` / `yt2sp` v2.0.0) — High-Precision, Reverse Migration Platform (Spotify → YouTube Music)

---

## 1. Executive Summary

**Spotify2YTM (`yt2sp` / `sp2yt`)** adalah sistem perangkat lunak desktop dan web lokal (*local-first utility*) yang dirancang untuk mengekstrak, merekonsiliasi, mengkategorisasi, dan memigrasikan daftar putar musik (*playlists*) dari **Spotify** ke **YouTube Music** dengan tingkat presisi tinggi ($\ge 98\%$ target presisi), **tanpa biaya langganan API pihak ketiga ($0 / Rp0)**, dan **tanpa memerlukan akun Spotify Developer** berbayar.

Aplikasi ini merupakan hasil reverse-engineering dan refactoring terarah terhadap ekosistem YT2Spotify v1.3.7 menjadi sistem migrasi berlawanan arah (**Spotify sebagai Source** dan **YouTube Music sebagai Destination**). Dengan memanfaatkan scraper katalog publik Spotify tanpa token developer (`spotifyscraper`), multi-pass candidate scoring di YouTube Music via `ytmusicapi.search(filter='songs')` dengan fallback ke video resmi, scoring fuzzy RapidFuzz dengan toleransi durasi dan deteksi penanda pembeda, audio preview 30 detik, serta automated playlist creation dan chunked track ingestion ke YouTube Music (`ytmusicapi.create_playlist` dan `add_playlist_items`), sistem memungkinkan transfer ribuan lagu secara instan, akurat, dan aman dari pemblokiran *rate limit*.

Dokumen ini adalah **Single Source of Truth (SSOT)** arsitektur, spesifikasi teknis, dan logika bisnis dari repositori setelah refactoring arah migrasi.

---

## 2. Identitas & Metadata Proyek

| Atribut Proyek | Nilai Aktual di Repositori | Referensi Sumber Kode |
| :--- | :--- | :--- |
| **Nama Paket** | `yt2sp` (Refactored to Spotify2YTM) | [pyproject.toml](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/pyproject.toml#L6) |
| **Versi Aktif** | `v2.0.0` (Reverse Migration Engine) | [yt2sp/__init__.py](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/__init__.py) |
| **Arah Migrasi** | **Spotify (Source) &rarr; YouTube Music (Destination)** | [yt2sp/sources/spotify_extract.py](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/sources/spotify_extract.py), [yt2sp/destinations/ytm_resolver.py](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/destinations/ytm_resolver.py) |
| **Tipe Mesin** | Multi-Pass Reconciliation & Playlist Writer Engine | [yt2sp/resolve/pipeline.py](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/resolve/pipeline.py) |
| **Lisensi** | The Unlicense (Public Domain - Bebas Atribusi) | [LICENSE](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/LICENSE) |
| **Python Runtime** | Python 3.11+ (Teruji pada Python 3.14) | [pyproject.toml](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/pyproject.toml#L9) |
| **Antarmuka Utama** | 1. Local Web Dashboard (`http://127.0.0.1:5000`)<br/>2. Terminal CLI (`yt2sp` via Typer & Rich) | [yt2sp/ui/server.py](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/server.py)<br/>[yt2sp/cli.py](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/cli.py) |
| **Penyimpanan Data** | SQLite 3 dalam WAL Mode (`yt2sp.db`) | [yt2sp/store/db.py](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/store/db.py) |
| **Biaya API / Cloud** | **$0.00 / Rp0 (100% Gratis & Bebas Kredensial Developer)** | Bebas SaaS Paywalls & Zero Cloud Billing |
| **Kebijakan Privasi** | **100% Local-First** (Zero Telemetri, Zero Data Remote) | Seluruh pustaka tersimpan lokal di perangkat |

---

## 3. Peta Navigasi Dokumentasi (Documentation Suite Index)

Seluruh spesifikasi teknis dan implementasi sistem dipecah menjadi modul-modul dokumentasi berikut:

```
documentation/
├── 00_PROJECT_OVERVIEW.md                 # Dokumen ini: Ringkasan eksekutif, identitas, dan peta panduan
├── 01_PRD.md                              # PART I: Product Requirements Document (Visi, Persona, Fitur, NFR, Scope)
├── 02_SRS.md                              # PART II: Software Requirements Specification (Sistem, Integrasi, Security)
├── 03_SYSTEM_ARCHITECTURE.md              # PART II: Arsitektur Sistem, Komponen, Pipeline, & Diagram Mermaid
├── 04_UI_UX_SPECIFICATION.md              # PART III: Desain Antarmuka, Sistem Token, 7 Views, Modals, Potato Mode
├── 05_SOURCE_CODE_DOCUMENTATION.md        # PART IV: Dokumentasi Struktur Modul, Kelas, Fungsi, & Signature Kode
├── 06_BUSINESS_LOGIC_AND_ALGORITHMS.md    # PART IV: Logika Bisnis, Normalisasi Regex, RapidFuzz, Rate Limiter, AI Parser
├── 07_DATABASE_AND_API_SPECIFICATION.md   # PART II & IV: Skema SQLite WAL, DDL, Indeks, & 12 Endpoint REST API
├── 08_TESTING_AND_QA.md                   # PART V: Hasil Pengujian Otomatis, Analisis 21 Test Case, & Root Cause Regresi
├── 09_DEVELOPMENT_AND_OPERATIONS.md       # PART VI: Panduan Instalasi, Runtime, Troubleshooting, & Dependency Map
├── 10_KNOWN_ISSUES_AND_ROADMAP.md         # PART V & VII: Technical Debt, Implementation Matrix, & Rencana Masa Depan
└── PROJECT_MASTER_DOCUMENTATION.md        # Indeks Master SSOT (Root Index)
```

---

## 4. Filosofi & Nilai Inti Produk

1. **Zero-Friction Zero-Cost:** Tidak ada pengguna yang harus membayar biaya langganan bulanan hanya untuk memindahkan daftar lagu yang merupakan hak milik kurasi mereka.
2. **Local-First & Privacy by Default:** Database, riwayat pencarian, link lagu, dan konfigurasi pengguna tersimpan 100% di mesin lokal pengguna (`yt2sp.db`). Tidak ada server analitik atau pengumpul data pihak ketiga.
3. **Resilience over Fragility:** Menghindari ketergantungan pada endpoint Spotify Developer API yang rentan terkena *quota ban* dan token kedaluwarsa 60 menit dengan memanfaatkan antarmuka *internal web catalog scraper* dan *native desktop clipboard ingestion*.
4. **Accuracy Through Evidence:** Setiap kecocokan lagu dinilai dengan metrik probabilitas terukur (skor RapidFuzz, penalti durasi, penalti penanda pembeda). Jika lagu meragukan, sistem tidak menebak sembarangan melainkan menyajikannya ke *Review Studio* untuk diputuskan oleh pengguna bersama pratinjau audio 30 detik.
5. **High Accessibility & Inclusive Hardware:** Mendukung 6 bahasa antarmuka internasional dan menyediakan fitur *Potato Mode* yang menonaktifkan filter GPU berat agar tetap berjalan lancar pada perangkat berspesifikasi rendah.

---

## 5. Panduan Membaca untuk AI & Agen Pengembang

Jika kamu adalah sistem AI yang ditugaskan untuk melakukan debugging, penambahan fitur, atau refactoring pada repositori ini:
- **Jangan mengubah batas threshold di kode tanpa memperbarui test suite:** Penurunan ambang batas matching pada commit `940a18e` (dari 0.85 ke 0.80) menyebabkan 2 tes di `tests/test_score.py` gagal. Baca selengkapnya di [08_TESTING_AND_QA.md](08_TESTING_AND_QA.md) dan [10_KNOWN_ISSUES_AND_ROADMAP.md](10_KNOWN_ISSUES_AND_ROADMAP.md).
- **Pahami isolasi thread pada koneksi SQLite:** Koneksi database menggunakan `threading.local()` dengan PRAGMA WAL mode. Operasi database lintas thread harus memanggil `_get_conn()` di dalam thread yang bersangkutan. Lihat [07_DATABASE_AND_API_SPECIFICATION.md](07_DATABASE_AND_API_SPECIFICATION.md).
- **Pahami pemisahan antara Matching Loop dan Genre Tagging:** Matching loop di `pipeline.py` sengaja **tidak** memanggil API genre agar tidak terjadi penundaan latensi I/O. Genre ditandai melalui endpoint atau thread terpisah `/api/tag-genre`. Lihat [06_BUSINESS_LOGIC_AND_ALGORITHMS.md](06_BUSINESS_LOGIC_AND_ALGORITHMS.md).
- **Perhatikan format Spotify URI Clipboard Paste:** Spotify Desktop menolak penempelan teks jika terdapat karakter markdown seperti `# Header`. URI harus diekspor sebagai baris bersih `spotify:track:<22_char_id>`. Lihat [01_PRD.md](01_PRD.md) dan [06_BUSINESS_LOGIC_AND_ALGORITHMS.md](06_BUSINESS_LOGIC_AND_ALGORITHMS.md).
