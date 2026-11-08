# YT2Spotify (yt2sp)

> **Pindah Playlist YouTube Music ke Spotify — Biaya Rp0 & Tanpa Akun Developer Berbayar.**

YT2Spotify adalah alat bantu migrasi playlist musik lokal yang cepat, aman, dan dirancang khusus agar Anda dapat memindahkan ratusan lagu dari YouTube Music ke Spotify secara presisi tanpa kehilangan urutan trek.

---

## Cuplikan Antarmuka (Screenshots)

### 1. Dashboard Utama & Status Sinkronisasi
Tampilan beranda yang bersih untuk memantau status pustaka musik, playlist terkini, dan akses cepat ke alur transfer baru.

![Dashboard Utama](docs/screenshots/01-dashboard.png)

---

### 2. Review Studio, Skor Kecocokan, & Smart Genre Splitter
Pemeriksaan akurasi kecocokan lagu dengan skor persentase, pemutar audio cuplikan reff 30 detik pada thumbnail, deteksi video UGC/non-musik, dan pemisah playlist otomatis berdasarkan genre.

![Review Studio](docs/screenshots/02-review-studio.png)

---

### 3. Manajemen Pustaka Playlist & Batch Actions
Kelola seluruh playlist YouTube Music yang pernah diekstrak, lakukan seleksi multi-lagu, atau hapus lagu yang tidak diinginkan secara langsung.

![Koleksi Playlist](docs/screenshots/03-playlists-library.png)

---

### 4. Panduan Terintegrasi (Bantuan & Panduan)
Panduan ringkas 3 langkah dasar untuk pengguna awam, dilengkapi indikator panah interaktif untuk membuka panduan teknis mendalam (Tahap A–E).

![Bantuan & Panduan](docs/screenshots/04-guide.png)

---

## Fitur Unggulan

- **Zero-Cost Architecture (Rp0):** Menggunakan teknik pencarian langsung tanpa memerlukan Spotify Developer App atau token API berbayar.
- **Pencocokan Multi-Pass Pintar:**
  - Pembersihan judul cerdas (membersihkan tag `[Official Video]`, `ft.`, `Remix`, bracket Jepang `【...】`, dan nama uploader).
  - Skoring kesamaan berbasis Levenshtein distance ([RapidFuzz](https://github.com/rapidfuzz/RapidFuzz)) pada judul dan artis.
  - Toleransi durasi audio ($\pm 10\%$) untuk membedakan trek asli dari klip singkat atau remix panjang.
- **Audio Preview Instan (Reff 30 Detik):** Dengar cuplikan reff lagu langsung di antarmuka web hanya dengan mengarahkan kursor ke thumbnail lagu (ditenagai dual-provider Deezer + iTunes API).
- **Pengurutan Genre Otomatis:** Deteksi genre otomatis berbasis rule-based dan pemetaan artis/judul.
- **Web UI & CLI:**
  - Antarmuka web modern dengan 4 palet tema (*Modern Dark*, *Emerald Mint*, *Warm Amber*, *Slate Graphite*).
  - Mode Hemat Daya / Laptop Kentang (*Potato Mode*) untuk performa mulus di perangkat spesifikasi rendah.
  - Dukungan multi-bahasa (ID, EN, ES, JA, KO, ZH).
- **Privasi 100% Terjaga:** Database SQLite dan riwayat lagu tersimpan murni di perangkat komputer lokal Anda. Tidak ada data pribadi atau riwayat lagu yang dikirim ke server pihak ketiga.

---

## Instalasi

### Prasyarat
- Python 3.11 atau lebih baru
- Browser modern (Chrome, Edge, Firefox, Brave)

### Langkah Pemasangan

1. **Clone repositori:**
   ```bash
   git clone https://github.com/username/yt-spt.git
   cd yt-spt
   ```

2. **Buat virtual environment dan aktifkan:**
   ```bash
   # Windows (PowerShell)
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependensi:**
   ```bash
   pip install -e .
   ```

---

## Cara Menjalankan

### Melalui Web UI (Direkomendasikan)

Jalankan perintah berikut di terminal:
```bash
python -m yt2sp.ui.server
```
Buka browser Anda dan kunjungi: **`http://127.0.0.1:5000`**

#### Alur Kerja di Web UI:
1. **Langkah 1 (Ekstrak):** Masukkan link playlist YouTube Music (Public atau Unlisted), lalu klik **Ambil Metadata**.
2. **Langkah 2 (Review):** Periksa hasil pencocokan lagu. Dengarkan audio preview reff pada thumbnail jika ragu, ganti versi alternatif, atau hapus lagu yang tidak diinginkan.
3. **Langkah 3 (Salin & Tempel ke Spotify):** Salin batch URI lagu (50 URI per blok) dan tempel (`Ctrl + V`) langsung ke playlist baru di Spotify Web / Desktop Player.

---

### Melalui CLI (Terminal)

```bash
# Ekstrak playlist dari YouTube Music
yt2sp extract "https://music.youtube.com/playlist?list=..."

# Jalankan pencocokan ke Spotify
yt2sp match <playlist_id>

# Ekstrak daftar URI untuk ditempel ke Spotify
yt2sp export <playlist_id>
```

---

## Pengujian (Testing)

Proyek ini dilengkapi dengan unit test otomatis:
```bash
pytest
```

---

## Lisensi & Atribusi

Proyek ini dirilis di bawah lisensi MIT. Dibuat untuk tujuan edukasi dan penggunaan pribadi.
