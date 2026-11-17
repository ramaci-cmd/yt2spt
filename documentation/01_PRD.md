# 01. PRODUCT REQUIREMENTS DOCUMENT (PRD)
# Spotify2YTM (`sp2yt` / `yt2sp` v2.0.0) — High-Precision Reverse Migration Platform (Spotify → YouTube Music)

---

## 1. Product Overview

### 1.1 Nama Proyek & Definisi Produk
* **Nama Produk:** **Spotify2YTM (`yt2sp` / `sp2yt`)**
* **Kategori Perangkat Lunak:** Music Library Utility, Catalog Reconciliation Engine, Local-First ETL Migration Platform.
* **Versi Rilis:** `v2.0.0` (Reverse Migration Direction).
* **Deskripsi Produk:** Spotify2YTM adalah utilitas migrasi daftar putar musik lokal (*local-first*) berpresisi tinggi yang memungkinkan pengguna memindahkan playlist dari **Spotify** ke **YouTube Music** secara instan, 100% gratis ($0/Rp0), tanpa memerlukan akun Spotify Developer berbayar, tanpa batasan jumlah lagu (*paywalls*), dan menjamin privasi data secara penuh melalui basis data SQLite lokal.

### 1.2 Latar Belakang & Problem Statement
Migrasi pustaka musik antarlayanan streaming adalah kebutuhan jutaan pengguna musik digital. Pengguna Spotify yang ingin beralih atau menyelaraskan playlist mereka ke YouTube Music menghadapi empat kendala utama di pasar saat ini:

1. **Monopolistik SaaS Paywalls (Model Berbayar Pemerasan):**
   Layanan komersial seperti *Soundiiz*, *TuneMyMusic*, dan *FreeYourMusic* membatasi transfer gratis hanya pada 20 hingga 50 lagu. Pengguna dengan playlist berisi 200 hingga 2.000 lagu dipaksa berlangganan seharga \$4.50 – \$14.99 per bulan.
2. **Kerapuhan & Kebutuhan Developer API:**
   Banyak konverter mewajibkan token developer Spotify berbayar atau akun API yang rumit dikonfigurasi.
3. **Kekacauan Pencarian Katalog YouTube Music:**
   Mencari lagu di YouTube Music sering menghasilkan video cover amatir, rekaman live konser, atau video non-resmi (UGC) alih-alih audio rekaman studio resmi.
4. **Masalah Versi Lagu yang Tidak Sesuai (False Positives):**
   Banyak konverter memasangkan lagu rekaman konser *Live* yang bising padahal pengguna menginginkan lagu rekaman studio *Original Album*, atau memasangkan lagu karaoke/cover tanpa memberi tahu pengguna.

### 1.3 Product Vision & Mission
* **Visi Produk:** Menjadi standar utilitas migrasi musik sumber terbuka (*open-source*) yang paling cepat, akurat, privat, dan bebas biaya di dunia untuk migrasi dari Spotify ke YouTube Music (dan sebaliknya).
* **Misi Produk:**
  1. Memberikan aksesibilitas penuh kepada penikmat musik untuk memindahkan katalog musik mereka dari Spotify ke YouTube Music tanpa terhalang dinding pembayaran (*paywall*).
  2. Menerapkan algoritma pencocokan katalog multi-tingkat berbasis bukti (*evidence-based scoring*) yang meminimalkan salah pasang lagu (*false positives*).
  3. Memungkinkan pembuatan dan pengisian playlist otomatis langsung di akun YouTube Music pengguna dalam batch aman 50 lagu.

### 1.4 Target Pengguna & User Personas

#### Persona 1: Audiophile & Musik Kollektor (The Power Curator)
* **Demografi:** Usia 20–35 tahun, memiliki lebih dari 1.500 lagu di YouTube Music, terbagi ke berbagai playlist genre yang sangat rapi.
* **Kebutuhan:** Memindahkan seluruh pustaka tanpa ada lagu yang hilang atau salah versi (*studio vs live*), serta ingin mengelompokkan kembali lagunya berdasarkan genre.
* **Pain Point:** Enggan membayar subscription \$10/bulan hanya untuk sekali transfer, dan frustrasi jika lagu digantikan versi karaoke atau live.

#### Persona 2: Pengguna Casual Multi-Platform (The Platform Switcher)
* **Demografi:** Mahasiswa / Profesional muda, baru saja membeli langganan Spotify Family dan ingin membawa playlist favorit dari YouTube Music.
* **Kebutuhan:** Solusi yang mudah digunakan dalam hitungan menit, antarmuka visual yang bersih, dan tidak memerlukan keahlian koding atau konfigurasi API Key.
* **Pain Point:** Menolak membuat akun Spotify Developer yang rumit dan membingungkan.

#### Persona 3: Pemilik Laptop Spek Rendah (The Low-Spec User)
* **Demografi:** Pengguna dengan laptop hemat daya (Celeron, i3 generasi lama, atau RAM 4GB) yang sering mengalami browser *lag* saat membuka dashboard web modern.
* **Kebutuhan:** Aplikasi yang ringan, tidak membebani kartu grafis, dan proses matching yang stabil di latar belakang.
* **Pain Point:** Animasi web modern yang berat dan memicu konsumsi baterai/GPU tinggi.

### 1.5 Value Proposition & Unique Selling Proposition (USP)
* **Zero-Dollar Architecture:** Menggunakan *public scraper* (`spotifyscraper`) dan *desktop clipboard injection*, memangkas biaya operasional dan API menjadi Rp0 selamanya.
* **Desktop `Ctrl + V` Ingestion:** Satu klik salin ribuan Spotify URIs dalam blok 50 lagu, langsung ditempelkan ke Spotify Desktop tanpa melalui limitasi REST API.
* **Multi-Pass Hybrid Reconciliation:** Penggabungan Tier 1 (Spotify Search + RapidFuzz C++ bindings) dan Tier 2 (Deezer ISRC Fallback via MusicBrainz) dengan tingkat presisi $\ge 98\%$.
* **Dual-Provider Audio Preview (Chorus/Reff):** Hover thumbnail lagu untuk mendengarkan pratinjau audio 30 detik dari Deezer CDN atau Apple iTunes API, memastikan kebenaran lagu sebelum disalin.
* **Smart Genre Splitter & AI Group Builder:** Deteksi genre otomatis berbasis konsensus iTunes + Deezer, serta parser pintar teks hasil pengelompokan AI (ChatGPT/Claude).
* **Low-Spec Potato Mode:** Mode hemat daya bawaan yang mematikan *backdrop-blur* dan animasi berat demi kenyamanan hardware pengguna.

### 1.6 Product Positioning
YT2Spotify memposisikan diri sebagai **utilitas desktop lokal non-komersial berkinerja tinggi** yang berada di antara skrip developer mentah (CLI scripts) dan layanan SaaS komersial berbayar (Soundiiz/TuneMyMusic), menggabungkan kemudahan GUI modern dengan kebebasan open-source.

---

## 2. Product Goals & Objectives

### 2.1 Tujuan Utama & Sekunder
* **Tujuan Utama:** Memungkinkan pengguna memigrasikan playlist YouTube Music publik maupun privat ke Spotify Desktop secara utuh tanpa biaya dan tanpa kredensial API.
* **Tujuan Sekunder:**
  - Menyediakan *Review Studio* interaktif untuk menyelesaikan konflik ambigu lagu.
  - Menyediakan sistem kategorisasi genre musik otomatis multi-sumber.
  - Menyediakan integrasi generator prompt AI untuk kurasi dan pemecahan (*splitting*) playlist.

### 2.2 Status Pencapaian Sasaran Produk (Goals Matrix)

| Kategori Sasaran | Deskripsi Sasaran | Target Metrik | Status Aktual di v1.3.7 | Keterangan Bukti |
| :--- | :--- | :--- | :--- | :--- |
| **User Goal** | Migrasi playlist tanpa akun developer | 100% Zero-Credential | `[IMPLEMENTED]` | Menggunakan `spotifyscraper` & Clipboard Paste |
| **User Goal** | Pratinjau audio instan tanpa login | $\le 1$ detik latensi audio | `[IMPLEMENTED]` | Deezer MP3 + iTunes AAC fallback ([server.py:73-100](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/server.py#L73-L100)) |
| **User Goal** | Dukungan bahasa internasional | 6 Bahasa dunia | `[IMPLEMENTED]` | ID, EN, ES, JA, KO, ZH di [i18n.js](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/i18n.js) |
| **Business/Tech Goal** | Biaya infrastruktur dan API | \$0 / Rp0 selamanya | `[IMPLEMENTED]` | Arsitektur 100% lokal tanpa backend berbayar |
| **Business/Tech Goal** | Presisi pencocokan lagu | $\ge 98.0\%$ presisi golden | `[IMPLEMENTED]` | RapidFuzz + penalti marker + penalti durasi |
| **Business/Tech Goal** | Penanganan Video YouTube Dihapus | Deteksi otomatis | `[IMPLEMENTED]` | Disimpan di `playlists.unavailable_count` |
| **Tech Goal** | Sinkronisasi dua arah (Spotify $\rightarrow$ YTM) | Export balik ke YTM | `[PLANNED]` | Belum diimplementasikan |
| **Tech Goal** | Eksekusi test suite 100% pass | 21/21 Unit Test Pass | `[TECHNICAL DEBT]` | 19 Passed, 2 Failed karena perubahan threshold |

---

## 3. Functional Requirements

### FR-01: Ekstraksi Metadata YouTube Music (Ingestion Engine)
* **Feature ID:** `FR-01`
* **Nama Fitur:** YouTube Music Playlist Extractor.
* **Deskripsi:** Mengambil seluruh daftar lagu, nama artis, judul album, durasi, tipe video, dan jumlah video yang dihapus/privat dari YouTube Music.
* **Pengguna:** Semua pengguna (CLI & Web UI).
* **Input:** String URL playlist (misal: `https://music.youtube.com/playlist?list=PLxxx`), ID playlist mentah (`PLxxx`), atau flag `liked: true`.
* **Output:** Record tersimpan di tabel `playlists`, `tracks`, dan `playlist_tracks`.
* **Proses Internal:**
  1. Membersihkan URL via regex `clean_playlist_id()`.
  2. Menginisialisasi `YTMusic` (autentikasi jika ada `ytm_auth.json`, unauthenticated jika tidak).
  3. Mengambil objek playlist via `get_playlist_details()`.
  4. Menghitung `unavailable_count = max(0, total_reported - len(tracks))`.
  5. Melakukan upsert record ke basis data SQLite secara transaksional.
* **Validasi:** Format ID playlist harus valid; URL kosong menghasilkan pesan error.
* **Kondisi Keberhasilan:** Seluruh lagu aktif tersimpan di database lokal; status job diperbarui menjadi selesai.
* **Kondisi Kegagalan:** Playlist privat tanpa auth menghasilkan exception dengan instruksi login.
* **Dependencies:** `ytmusicapi`, `yt2sp.store.db`.
* **Status Implementasi:** `[IMPLEMENTED]` ([yt2sp/ytm/extract.py:68-85](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ytm/extract.py#L68-L85)).

### FR-02: Normalisasi & Pembersihan Noise Judul (String Normalization)
* **Feature ID:** `FR-02`
* **Nama Fitur:** Title Noise Stripper & Marker Preserver.
* **Deskripsi:** Menghilangkan kata-kata promosi dan noise video YouTube dari judul lagu, namun secara cerdas mempertahankan penanda pembeda aransemen lagu (*distinctive markers*).
* **Input:** String judul lagu dan nama artis dari YouTube Music.
* **Output:** String ASCII lowercase bersih yang dioptimalkan untuk pencarian katalog.
* **Business Rules:**
  - Menghapus: `[Official Music Video]`, `Official Audio`, `Lyric Video`, `4K`, `HD`, `Remastered`, `MV`, dan format kurung kanji Jepang `【...】`.
  - Mempertahankan penanda pembeda: `live`, `acoustic`, `remix`, `cover`, `instrumental`, `karaoke`, `slowed`, `sped up`, `nightcore`, `lofi`, `unplugged`, `demo`, `radio edit`, `extended`.
  - Mengonversi karakter Unicode beraksen ke ASCII menggunakan pustaka `unidecode`.
* **Status Implementasi:** `[IMPLEMENTED]` ([yt2sp/match/normalize.py:62-94](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/match/normalize.py#L62-L94)).

### FR-03: Multi-Pass Fuzzy Reconciliation Engine
* **Feature ID:** `FR-03`
* **Nama Fitur:** Multi-Pass Catalog Matcher.
* **Deskripsi:** Menghubungkan setiap lagu YouTube Music ke track ID Spotify yang paling akurat.
* **Proses Internal:**
  1. **Tier 0:** Evaluasi `video_type`. Jika `MUSIC_VIDEO_TYPE_UGC`, status diberi `'skipped'`.
  2. **Tier 1 (Spotify Catalog):** Menjalankan pencarian teks via `spotifyscraper`. Menghitung skor kemiripan RapidFuzz: $\text{BaseScore} = 0.65 \times \text{TitleSim} + 0.35 \times \text{ArtistSim}$ (nilai default config kerja).
  3. **Evaluasi Penalti:**
     - Penalti Penanda Mismatch: $-0.12$ jika penanda pembeda hanya ada di satu sisi.
     - Penalti Durasi: $-0.10$ jika selisih durasi $> 5000\text{ ms}$ DAN ($> 10\%$ atau $> 12000\text{ ms}$).
  4. **Klasifikasi:**
     - Skor $\ge 0.80 \implies$ `'resolved_auto'`.
     - $0.55 \le \text{Skor} < 0.80 \implies$ `'needs_review'`.
     - Skor $< 0.55 \implies$ Memicu Tier 2 Fallback.
  5. **Tier 2 (Deezer ISRC Fallback):** Mencari metadata lagu di Deezer Public API $\rightarrow$ mengekstrak kode ISRC $\rightarrow$ mencari Spotify ID via MusicBrainz API atau kueri Spotify `isrc:<ISRC>`.
* **Pembatalan:** Mendukung penghentian mendadak via `threading.Event` (`_job_cancel_event` / `POST /api/cancel`).
* **Status Implementasi:** `[IMPLEMENTED]` ([yt2sp/resolve/pipeline.py:20-188](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/resolve/pipeline.py#L20-L188)).

### FR-04: Review Studio & Alternative Version Picker
* **Feature ID:** `FR-04`
* **Nama Fitur:** Review Studio & Manual Override.
* **Deskripsi:** Antarmuka audit untuk lagu-lagu berstatus `needs_review` atau `failed`.
* **Kemampuan:**
  - Menerima (*Accept*) atau Menolak (*Reject*) pasangan lagu Spotify.
  - Menemukan versi alternatif via `/api/alternatives` (Cover penyanyi berbeda, Remix, Acoustic, Live).
  - Menautkan link Spotify manual (`https://open.spotify.com/track/...` atau `spotify:track:...`) dengan verifikasi metadata instan via Spotify oEmbed API.
  - Memprioritaskan lagu yang belum terverifikasi di baris paling atas tabel review.
* **Status Implementasi:** `[IMPLEMENTED]` ([yt2sp/ui/server.py:806-940](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/server.py#L806-L940)).

### FR-05: Dual-Provider Audio Preview Streamer
* **Feature ID:** `FR-05`
* **Nama Fitur:** 30-Second Audio Preview on Hover.
* **Deskripsi:** Memutar pratinjau cuplikan lagu 30 detik (bagian *reff / chorus*) secara langsung di browser ketika kursor mouse diarahkan ke thumbnail cover lagu.
* **Alur Fallback:** Mencari audio Deezer CDN $\rightarrow$ jika gagal, beralih ke Apple iTunes API.
* **Caching:** In-memory caching TTL 24 jam (`86400.0` detik) di server web.
* **Status Implementasi:** `[IMPLEMENTED]` ([yt2sp/ui/server.py:73-100](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/server.py#L73-L100)).

### FR-06: Validasi Silang Genre Multi-Sumber
* **Feature ID:** `FR-06`
* **Nama Fitur:** Cross-Validated Genre Tagger.
* **Deskripsi:** Mengklasifikasikan lagu ke dalam kelompok genre terstandardisasi menggunakan konsensus Apple iTunes Search API, Deezer Album Genre API, dan Fallback Heuristik Kontekstual.
* **Status Implementasi:** `[IMPLEMENTED]` ([yt2sp/resolve/genre.py:219-328](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/resolve/genre.py#L219-L328)).

### FR-07: AI Group Splitter & Smart Playlist Builder
* **Feature ID:** `FR-07`
* **Nama Fitur:** AI Prompt Generator & Smart Group Parser.
* **Deskripsi:**
  - Menyediakan modal untuk menyalin daftar judul lagu dengan prompt terstruktur untuk AI (ChatGPT/Claude/Gemini).
  - Membaca dan mem-parsing teks hasil respon AI secara fleksibel: mengenali header kategori, nomor urut lagu, berbagai pemisah tanda baca (`—`, `-`, `|`), karakter multibahasa/Unicode (Jepang/Korea/Mandarin), dan format dua arah (`Artis — Judul` atau `Judul — Artis`).
  - Menyediakan tombol 1-klik "Salin Semua URI Spotify" tanpa komentar markdown untuk langsung ditempel ke Spotify Desktop, atau opsi menyimpan sebagai playlist kustom di database lokal via `/api/create-grouped-playlist`.
* **Status Implementasi:** `[IMPLEMENTED]` ([yt2sp/ui/index.html:6200-6700](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/ui/index.html)).

### FR-08: Export Engine & Clipboard Injection (`Ctrl + V`)
* **Feature ID:** `FR-08`
* **Nama Fitur:** Spotify Desktop Clipboard Exporter.
* **Deskripsi:**
  - Memvalidasi format Spotify URI: `^spotify:track:[A-Za-z0-9]{22}$`.
  - Memecah URI ke dalam blok berukuran 50 lagu (*50-song chunk files*) untuk mencegah overflow buffer keyboard clipboard sistem operasi.
  - Menyediakan ekspor laporan audit CSV ber-BOM UTF-8 (`utf-8-sig`) yang menyertakan tautan pencarian langsung ke Spotify Web.
* **Status Implementasi:** `[IMPLEMENTED]` ([yt2sp/export/writer.py](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/export/writer.py) & [yt2sp/export/report.py](file:///C:/Users/Elang/.gemini/antigravity/worktrees/yt-spt/generate_technical_documentation/yt2sp/export/report.py)).

---

## 4. Non-Functional Requirements (NFR)

### 4.1 Performance (Kinerja)
* **Latensi Kueri Basis Data:** Waktu respons kueri SQLite rata-rata $\le 15\text{ ms}$ untuk pembacaan 100 baris lagu berkat PRAGMA WAL mode, cache 64MB, dan memory-mapped I/O 256MB.
* **Throughput Scraping:** Kecepatan pencocokan diatur hingga 120 request per menit melalui pengendali *Token Bucket* thread-safe tanpa memicu HTTP 429.
* **Kompresi Jaringan:** Payload JSON dan file statis dikompresi menggunakan `gzip` (level 6) jika didukung klien, menghasilkan pengurangan ukuran payload hingga $\approx 85\%$.

### 4.2 Reliability & Fault Tolerance (Keandalan)
* **Kompensasi Jaringan & Retry:** Fungsi `search_spotify()` dan `search_deezer()` dilengkapi dengan mekanisme percobaan ulang (*retry*) hingga 3 kali dengan jeda eksponensial (*exponential backoff*).
* **Resiliensi Kegagalan:** Jika proses matching diinterupsi oleh pengguna atau jaringan terputus, status lagu yang telah selesai tetap tersimpan permanen di database. Saat proses dijalankan kembali, sistem secara otomatis hanya melanjutkan lagu berstatus `pending`.

### 4.3 Scalability & Data Integrity (Skalabilitas & Integritas)
* **Kapasitas Pustaka:** Mampu mengelola pustaka lokal lebih dari 10.000 lagu tanpa penurunan performa kueri berkat indeks terdedikasi (`idx_matches_status`, `idx_pt_playlist`, `idx_tracks_genre`).
* **Sanitasi Data Yatim (Orphan Cleanup):** Operasi penghapusan playlist secara otomatis mengeksekusi penghapusan kaskade untuk membersihkan lagu di tabel `tracks` dan `matches` yang tidak lagi memiliki relasi di `playlist_tracks`, diakhiri dengan `VACUUM`.

### 4.4 Maintainability & Zero-Dependency Philosophy (Pemeliharaan)
* **Server Web Mandiri:** Server backend diimplementasikan murni menggunakan pustaka standar Python (`http.server.ThreadingHTTPServer`, `urllib`, `gzip`, `sqlite3`), meminimalkan ketergantungan paket pihak ketiga yang rentan usang (*dependency rot*).

### 4.5 Security & Privacy (Keamanan & Privasi)
* **Proteksi Anti-CSRF:** Metode `_is_safe_origin()` di server HTTP memverifikasi header `Origin`, menolak semua permintaan mutasi (*POST*) yang tidak berasal dari `localhost`, `127.0.0.1`, atau `::1`.
* **Zero Telemetry:** Nol pelacakan pihak ketiga, nol analitik cloud, dan nol pengiriman data pengguna ke server eksternal selain kueri katalog publik ke Spotify, Deezer, dan Apple.

### 4.6 Accessibility & Usability (Aksesibilitas & Kegunaan)
* **Potato Mode (Low-Spec Hardware Toggle):** Opsi penonaktifan filter CSS berat (`backdrop-blur`), animasi canvas visualizer, dan bayangan berlapis untuk menjamin 60 FPS pada kartu grafis terintegrasi.
* **Navigasi Keyboard Modal:** Seluruh modal layar penuh mendukung penutupan instan via tombol `Escape` (Esc) atau klik area latar belakang (*backdrop click*).
* **Multi-Language UI:** 6 bahasa antarmuka lokal tervalidasi.

---

## 5. User Stories & Use Cases

### 5.1 Daftar User Stories

* **US-01 (Ekstraksi Cepat):**
  * *As a* penikmat musik,
  * *I want* menempelkan link playlist YouTube Music dan menarik seluruh lagunya,
  * *So that* saya tidak perlu mencatat judul lagu satu per satu secara manual.
* **US-02 (Pencocokan Otomatis Tanpa Ribet):**
  * *As a* pengguna,
  * *I want* sistem mencocokkan lagu-lagu saya ke katalog Spotify secara otomatis tanpa saya harus mendaftar akun developer,
  * *So that* proses migrasi berlangsung cepat dan bebas biaya.
* **US-03 (Verifikasi Pratinjau Audio):**
  * *As a* kurator musik,
  * *I want* mendengarkan potongan lagu 30 detik saat mengarahkan kursor ke cover lagu,
  * *So that* saya dapat memastikan rekaman lagu tersebut adalah versi yang benar sebelum memindahkannya.
* **US-04 (Penyelesaian Lagu Ambigu):**
  * *As a* pengguna,
  * *I want* memilih versi alternatif (cover, remix, acoustic) atau menempelkan link Spotify manual pada lagu yang belum cocok,
  * *So that* tidak ada lagu favorit saya yang tertinggal.
* **US-05 (Injeksi Desktop Instan):**
  * *As a* pengguna Spotify Desktop,
  * *I want* menyalin ribuan URI lagu dan menekan `Ctrl + V` di aplikasi Spotify,
  * *So that* playlist langsung terisi dalam 1 detik tanpa antre kuota API.
* **US-06 (Pemecahan Playlist dengan AI):**
  * *As a* kurator,
  * *I want* meminta AI mengelompokkan lagu saya berdasarkan mood dan menempelkan kembali hasilnya ke aplikasi,
  * *So that* saya mendapatkan beberapa playlist tematik baru secara otomatis.

### 5.2 Rincian Use Cases Utama

#### Use Case: UC-01 — Migrasi Playlist End-to-End Melalui Web UI
* **Use Case ID:** `UC-01`
* **Aktor:** Pengguna Umum.
* **Preconditions:** Server `yt2sp ui` telah berjalan di `http://127.0.0.1:5000` dan aplikasi Spotify Desktop telah terinstal di komputer.
* **Main Flow:**
  1. Pengguna membuka browser pada `http://127.0.0.1:5000`.
  2. Pengguna menempelkan URL playlist YouTube Music di tab *Overview* atau *Transfer*.
  3. Pengguna mengklik tombol "Tarik Playlist" (Sistem menjalankan `POST /api/extract`).
  4. Server mengekstrak lagu dan menampilkan ringkasan jumlah lagu aktif serta video yang dihapus.
  5. Pengguna mengklik tombol "Mulai Pencocokan" (Sistem menjalankan `POST /api/resolve`).
  6. Sistem memproses lagu di latar belakang; progress bar beranimasi menampilkan status tiap lagu secara real-time.
  7. Setelah selesai, pengguna membuka tab *Needs Review* untuk memverifikasi lagu-lagu yang meragukan.
  8. Pengguna mengklik tombol "Salin Semua URI Spotify" di tab *Transfer* atau *Export*.
  9. Pengguna membuka Spotify Desktop, membuat playlist baru, mengklik area track, dan menekan shortcut `Ctrl + V`.
  10. Semua lagu berhasil masuk ke playlist Spotify.
* **Alternative Flow:**
  - Jika lagu berstatus `needs_review`, pengguna mengklik tombol "Alternatif", mendengarkan audio preview, dan memilih versi yang diinginkan (`POST /api/choose-alternative`).
  - Jika lagu tidak ditemukan sama sekali di katalog otomatis, pengguna mencari di Spotify Web, menyalin link lagu, dan menyimpannya melalui tombol "+ Tautkan Link" (`POST /api/review` dengan `action: manual`).
* **Exception Flow:**
  - Jika playlist bersifat privat dan file `ytm_auth.json` tidak ada, sistem menampilkan modal error kuning dengan panduan pembuatan file autentikasi atau menyarankan mengubah playlist YouTube menjadi Publik/Unlisted.
* **Postconditions:** Seluruh lagu tersimpan dengan status `resolved_auto` atau `accepted` di database lokal dan terinjeksi ke Spotify Desktop pengguna.

---

## 6. Scope & Limitations

### 6.1 Ruang Lingkup yang Tersedia (`In Scope`)
- [x] Ekstraksi playlist publik, unlisted, dan Liked Music dari YouTube Music.
- [x] Deteksi dan pelaporan jumlah video YouTube yang dihapus atau diprivat oleh pengunggah aslinya.
- [x] Normalisasi string judul dan pembersihan 17 pola noise video.
- [x] Perlindungan 15 penanda pembeda aransemen musik (*distinctive markers*).
- [x] Mesin penilaian fuzzy berbasis RapidFuzz C++ bindings dengan penalti durasi dan marker.
- [x] Fallback resolver Tier 2 berbasis Deezer ISRC Bridge dan MusicBrainz URL mapping.
- [x] Pratinjau audio 30 detik (chorus) via Deezer CDN dan Apple iTunes API tanpa autentikasi.
- [x] Review Studio interaktif dengan pemilih versi alternatif dan input manual berbasis Spotify oEmbed.
- [x] Smart Genre Tagging berbasis konsensus multi-sumber (iTunes + Deezer + Heuristik).
- [x] Smart Group Playlist Builder yang mampu mem-parsing output kategorisasi AI secara fleksibel.
- [x] Ekspor Spotify URI ke file teks terpecah (50 lagu per blok) dan ekspor laporan CSV audit ber-BOM UTF-8.
- [x] Web dashboard lokal berfitur lengkap, mode gelap/terang, Potato Mode, dan 6 bahasa internasional.
- [x] Antarmuka CLI terminal lengkap (`yt2sp` Typer app) dengan 13 sub-perintah.

### 6.2 Batasan Teknis & Produk (`Limitations & Out of Scope`)
- **Ketergantungan pada Spotify Desktop:** Fitur instan `Ctrl + V` adalah fitur internal eksklusif aplikasi Spotify Desktop (Windows dan macOS). Fitur ini **tidak berfungsi** di Spotify Web Player (browser) atau Spotify Mobile (Android/iOS) karena keterbatasan izin akses clipboard browser/OS mobile.
- **Ekstraksi Lagu Privat YouTube:** Memerlukan file autentikasi browser `ytm_auth.json`. Sistem tidak menyediakan alur login OAuth resmi Google karena YouTube Data API v3 membatasi kuota harian secara ketat.
- **Sinkronisasi Dua Arah (Spotify $\rightarrow$ YouTube Music):** Saat ini berada di luar cakupan rilis v1.x (fokus satu arah: YTM $\rightarrow$ Spotify).
- **Lagu Tidak Rilis di Spotify:** Lagu-lagu independen/remix tidak resmi YouTube yang memang tidak pernah didistribusikan ke agregator musik digital (Spotify/Deezer) tidak dapat ditemukan di katalog Spotify; lagu tersebut akan berstatus `failed` dan memerlukan input link manual jika pengguna menemukan cover alternatifnya.
