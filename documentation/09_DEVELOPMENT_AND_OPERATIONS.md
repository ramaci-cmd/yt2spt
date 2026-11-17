# 09. DEVELOPMENT, OPERATIONS & FEATURE DEPENDENCY MAPPING
# YT2Spotify (`yt2sp`) — High-Precision, Zero-Cost Music Migration Platform

---

## 1. Development Environment Setup

### 1.1 Persyaratan Sistem (Prerequisites)
* **Sistem Operasi:** Windows 10/11, macOS 12+, atau Linux (Ubuntu 20.04+, Debian 11+, Arch).
* **Python Environment:** Python 3.11 atau lebih baru (teruji kompatibel penuh pada Python 3.14).
* **Spotify Client:** Aplikasi resmi **Spotify Desktop Client** (Windows/macOS) untuk memanfaatkan fitur penempelan clipboard `Ctrl + V`.
* **Git:** Versi 2.30+ untuk kontrol versi.

### 1.2 Langkah Instalasi Lokal Cepat
Jalankan perintah berikut di PowerShell atau terminal bash:

```bash
# 1. Klon repositori
git clone https://github.com/ramaci-cmd/yt2spt.git
cd yt2spt

# 2. Buat dan aktifkan virtual environment
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate

# 3. Instal paket dalam mode editable beserta dependensinya
pip install -e .
```

### 1.3 Perintah Operasional CLI
Setelah instalasi, perintah CLI `yt2sp` tersedia secara global dalam virtual environment:

| Perintah Terminal | Tindakan Operasional |
| :--- | :--- |
| `yt2sp init` | Inisialisasi skema basis data `yt2sp.db` dan membuat `config.toml` bawaan jika belum ada. |
| `yt2sp ui` | Menjalankan server web dashboard lokal pada `http://127.0.0.1:5000` dan otomatis membuka browser. |
| `yt2sp extract <URL>` | Mengekstrak metadata daftar lagu dari URL YouTube Music ke database lokal. |
| `yt2sp resolve` | Menjalankan proses pencocokan katalog Spotify untuk semua lagu yang berstatus pending. |
| `yt2sp review` | Membuka antarmuka interaktif terminal untuk mengaudit lagu `needs_review`. |
| `yt2sp export --clipboard`| Menyalin seluruh URI lagu yang telah disetujui langsung ke clipboard sistem operasi. |
| `yt2sp tag-genre` | Menjalankan validasi silang genre otomatis untuk seluruh lagu di database. |
| `yt2sp split` | Menghasilkan file blok URI Spotify terpisah untuk setiap kategori genre. |
| `yt2sp status` | Menampilkan tabel statistik perpustakaan lokal di konsol terminal. |
| `yt2sp smoke-test` | Menghasilkan 5 lagu kurasi ke clipboard untuk menguji fitur `Ctrl + V` Spotify Desktop. |
| `yt2sp reset-cmd` | Mengosongkan data database lokal dengan konfirmasi keamanan terminal. |

---

## 2. Maintenance & Troubleshooting Runbook

### 2.1 Matriks Penanganan Masalah Umum (Troubleshooting Matrix)

| Gejala Masalah | Kemungkinan Penyebab | Langkah Solusi & Pemulihan |
| :--- | :--- | :--- |
| **Error `HTTP 403 Forbidden` saat panggil API lokal** | Klien memanggil endpoint dengan header `Origin` selain `localhost` atau `127.0.0.1`. | Pastikan mengakses UI melalui alamat `http://127.0.0.1:5000` atau `http://localhost:5000`. Cek fungsi `_is_safe_origin()` di `server.py`. |
| **Ekstraksi Playlist Mengembalikan 0 Lagu** | Playlist bersifat privat atau link tidak valid. | Ubah playlist YouTube menjadi **Publik** atau **Unlisted**. Jika ingin menarik Liked Songs akun pribadi, jalankan `yt2sp auth-ytm` untuk membuat `ytm_auth.json`. |
| **Penempelan `Ctrl + V` di Spotify Hanya Memasukkan 1 Lagu** | Teks clipboard mengandung karakter non-URI seperti komentar markdown `# Header`. | Gunakan tombol "Salin Semua URI Spotify" yang mengekspor URI bersih tanpa komentar baris, atau salin melalui tab 50-chunk modal. |
| **Spotify Membeku (*Freeze*) saat Menempelkan Banyak Lagu** | Terlalu banyak lagu (>500 lagu) disalin sekaligus ke clipboard sistem operasi. | Gunakan fitur ekspor blok 50 lagu (`chunk_size = 50`) di `output/uris/` atau modal chunks di UI. |
| **Pencarian Spotify Berulang Kali Mengalami Timeout** | IP pengguna dibatasi oleh scraping filter atau koneksi internet tidak stabil. | Sesuaikan parameter `rate_per_minute` di `config.toml` (turunkan ke 30-60) dan pastikan `backoff_sleep()` berjalan. Sesi akan otomatis di-reset oleh `_reset_client()`. |
| **Ukuran Berkas `yt2sp.db` Sangat Besar** | Berkas SQLite menyimpan banyak ruang kosong setelah penghapusan massal. | Sistem otomatis menjalankan `VACUUM` pada penghapusan playlist; atau jalankan manual lewat script Python: `db._get_conn().execute("VACUUM")`. |

---

## 3. Feature Dependency Mapping (Matriks Dampak Perubahan)

Matriks ini dirancang khusus agar AI lain atau pengembang dapat segera mengetahui berkas dan komponen mana yang berpotensi terdampak ketika suatu fitur diubah:

| Fitur / Komponen | File Implementasi | Modul Terkait | Endpoint / API Terkait | Database Tables | Fitur Lain yang Terdampak |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Normalisasi Judul** | `match/normalize.py` | `match.score`, `resolve.pipeline` | Tidak langsung | `tracks.title` | `compute_score()`, pencarian Spotify, deteksi genre heuristik. |
| **Scoring & Klasifikasi** | `match/score.py` | `resolve.pipeline`, `tests/test_score.py` | `/api/resolve` | `matches.score`, `matches.status` | Ambang batas `needs_review`, antrean Review Studio, jumlah lagu lolos ekspor. |
| **Ekstraksi YouTube** | `ytm/extract.py` | `cli.py`, `ui/server.py` | `/api/extract` | `playlists`, `tracks`, `playlist_tracks` | Jumlah lagu library, sampling 2x2 collage artwork, penghitungan unavailable video. |
| **Pencarian Spotify** | `resolve/spotify_resolver.py` | `resolve.pipeline`, `ui/server.py` | `/api/resolve`, `/api/alternatives` | `matches.spotify_id`, `matches.result_title` | Kualitas kandidat lagu, opsi alternatif di Review Studio. |
| **Deezer ISRC Fallback**| `resolve/deezer_resolver.py` | `resolve.pipeline` | `/api/resolve` | `matches.tier` (`T2_isrc`) | Lagu-lagu rilis internasional dan indie yang gagal di Tier 1. |
| **Deteksi Genre** | `resolve/genre.py` | `ui/server.py`, `cli.py` | `/api/tag-genre`, `/api/tracks` | `tracks.genre`, `tracks.genre_source` | Distribusi genre di dashboard overview, Smart Genre Splitter, filter genre di library. |
| **Orkestrator Matching**| `resolve/pipeline.py` | `ui/server.py`, `cli.py` | `/api/resolve`, `/api/cancel` | `matches`, `runs` | Progress bar UI, tombol pembatalan matching, kecepatan sync. |
| **Layer Database SQLite**| `store/db.py` | Seluruh modul backend | Seluruh endpoint `/api/*` | 7 tabel relasional | Integritas transaksi, konkurensi WAL mode, sanitasi orphan tracks saat hapus. |
| **Ekspor Blok URI** | `export/writer.py` | `ui/server.py`, `cli.py` | `/api/uris` | `matches` (`resolved_auto`, `accepted`) | File chunk di folder `output/uris/`, clipboard paste di Spotify Desktop. |
| **Smart Group Splitter**| `ui/index.html` (JS) | `ui/server.py` | `/api/create-grouped-playlist` | `playlists`, `playlist_tracks` | Pembuatan playlist tematik dari prompt output AI. |
| **Pratinjau Audio 30s** | `ui/server.py` | `resolve/genre.py` | `/api/preview` | `api_cache` | Pemutaran hover preview audio di Review Studio dan Track Library. |
