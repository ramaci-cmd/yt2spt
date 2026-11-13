# Changelog

Semua perubahan penting pada proyek **YT2Spotify (yt2sp)** didokumentasikan di berkas ini.
Format ini mengacu pada [Keep a Changelog](https://keepachangelog.com/id/1.0.0/) dan mematuhi [Semantic Versioning](https://semver.org/).

---

## [1.3.5] - 2026-11-14

### Diperbaiki (Fixed)
- **Pembersihan Prefiks Nomor Lagu Fleksibel (`No.`, `#`, `Track`)**:
  - Mendukung input lagu dengan format `No. 7 — `, `No 1. `, `#1 - `, atau format nomor lainnya tanpa merusak pembacaan judul lagu.
  - Aman dari kesalahan pemotongan judul lagu yang mengandung format jam/waktu seperti `1:15 AM`.
- **Penghapusan Pemisahan Lagu Berbasis Simbol Liar**:
  - Menghapus pemisahan judul/artis menggunakan simbol `=`, `:`, `;`, `,`, `.` yang sebelumnya merusak judul lagu dengan koma (misal: *Space, Circumstances, Time, and Events*), titik (*Entah...*), atau titik dua (*1:15 AM*). Pemisah judul lagu kini hanya menggunakan pemisah standar (`—`, `–`, `-`, `|`).
  - Memperbaiki deteksi nama playlist agar tidak lagi menganggap setiap baris lagu sebagai nama playlist baru saat menempelkan daftar lagu massal.

---

## [1.3.4] - 2026-11-14

### Diperbaiki (Fixed)
- **Pencocokan Lagu Multibahasa & Unicode di Smart Group Playlist Builder**:
  - Memperbaiki bug di mana daftar lagu yang ditempel keliru dicocokkan ke lagu yang sama (misal: *ヨイハナビ*).
  - Normalisasi teks kini mempertahankan karakter Unicode huruf dan angka (`\p{L}\p{N}`) sehingga judul berbahasa Jepang, Korea, Mandarin, dan karakter non-ASCII lainnya tidak terhapus menjadi string kosong.
  - Menambahkan pengaman panjang karakter minimum (`_strMatch`) untuk mencegah string kosong atau pendek menghasilkan kecocokan semu (*false-positive substring match*).
  - Mendukung deteksi judul dan artis dua arah (baik format `Judul — Artis` maupun sebaliknya).

---

## [1.3.3] - 2026-11-14

### Ditambahkan (Added)
- **Kemudahan Menutup Popup / Modal Layar Penuh (Escape & Backdrop Click)**:
  - Seluruh modal popup (`modal-copy-tracks`, `modal-group-splitter`, `modal-stats`, `modal-alternatives`, `modal-manual`, `modal-chunks`, `modal-delete-track`) kini dapat ditutup instan hanya dengan menekan tombol **`Escape` (Esc)** pada keyboard.
  - Menutup modal juga dapat dilakukan cukup dengan mengklik area latar belakang / luar kartu modal (*backdrop click*), tanpa harus mengarahkan kursor dan mengklik tombol "X".

---

## [1.3.2] - 2026-11-14

### Ditambahkan & Ditingkatkan (Added & Improved)
- **Parser Teks Cerdas Bebas Format (Smart Group Playlist Builder)**:
  - Kebal terhadap spasi berlebih dan jeda baris kosong ganda (*multi-line breaks*).
  - Judul playlist dideteksi secara cerdas: jika baris pertama tidak cocok dengan lagu di pustaka, baris tersebut langsung dijadikan judul playlist. Jika langsung berupa lagu, otomatis masuk ke grup default.
  - Mendukung input lagu vertikal (cukup Enter ke bawah) tanpa perlu nomor urut di depan.
  - Mendukung berbagai simbol pemisah judul dan artis: `=`, `:`, `;`, `.`, `,`, `—`, `–`, `-`.
  - Peningkatan pencocokan multibahasa/transliterasi (romaji katakana/kanji) via `ascii_title` dan `ascii_result` di endpoint `/api/tracks`.

---

## [1.3.1] - 2026-11-13

### Diperbaiki (Fixed)
- **Parser Deteksi Grup AI (Smart Group Playlist Builder)**:
  - Memperbaiki bug regex Unicode di mana karakter angka nomor urut (`1.`, `2.`, `3.`) terdeteksi sebagai emoji header grup.
  - Memastikan seluruh lagu di bawah kategori terkelompokkan dengan benar ke dalam `rawTracks` masing-masing grup.
- **Salin Semua URI Spotify**:
  - Tombol "Salin Semua URI Spotify" kini menyalin seluruh baris URI Spotify (`spotify:track:...`) dari semua grup secara bersih tanpa komentar markdown `# Header`. Hal ini menghilangkan masalah pada Spotify Desktop di mana aplikasi Spotify membatalkan paste atau hanya menempel 1 lagu teratas jika terdapat karakter `#`.
- **Pencocokan Lagu Cerdas**:
  - Menambahkan pembagian format tanda pisah (*dash split*) untuk mengenali format `Artis – Judul` maupun `Judul – Artis` terhadap database perpustakaan lagu lokal.

---

## [1.3.0] - 2026-11-13

### Ditambahkan (Added)
- **Fitur Pembatalan Matching (Cancel Progress)**:
  - Dukungan `stop_event` pada pipeline matching (`yt2sp/resolve/pipeline.py`).
  - Endpoint baru `POST /api/cancel` pada server UI.
  - Tombol aksi "Batalkan" di Step 4 saat proses pencocokan berlangsung dan pada floating background monitor widget.
- **Modal Salin & Pemisah Lagu dengan Prompt AI**:
  - Toolbar pengaturan 3-kolom: Sumber Lagu (*Hanya Terpilih, Filter Saat Ini, Semua Library*), Format Teks (*Hanya Judul, Artis - Judul, Judul - Artis*), dan Nomor Urut.
  - Kartu pemilihan mode prompt AI (*Normal Mix Musik, Kustom Genre, Kurasi Niche, Freeform*).
  - Kotak pratinjau interaktif yang menampilkan thumbnail cover album dan badge genre lagu.
  - Tombol toggle untuk beralih antara tampilan visual dan teks mentah prompt AI.
- **Integrasi Smart Group Playlist Builder**:
  - Parser teks hasil AI untuk mendeteksi header kategori/genre/mood secara otomatis.
  - Pencocokan cerdas (*fuzzy matcher*) judul lagu dari output AI ke database hasil pencarian Spotify lokal.
  - Tombol 1-klik "Salin Semua URI Spotify" untuk langsung ditempel (*Ctrl + V*) ke aplikasi Spotify Desktop, serta opsi membuat playlist langsung di aplikasi.
- **Sinkronisasi Versi Dinamis**:
  - Penambahan endpoint `GET /api/version` dan penyertaan `version_badge` pada `GET /api/status`.
  - Badge versi di halaman Overview kini terhubung langsung ke `yt2sp.__version__` secara dinamis.

### Diperbaiki (Fixed)
- **Bug Step 4 Stuck di 100%**: Memisahkan pembacaan status background job `genre` agar tidak menimpa status `resolve`, serta menambahkan tombol navigasi manual saat proses selesai.
- **Bug Tombol Melayang di Overview**: Menghapus duplikasi tag footer modal dan menyeimbangkan hierarki penutup `<div>` pada antarmuka web.
- **Sinkronisasi Versi Global**: Memperbarui nomor versi di `pyproject.toml`, `yt2sp/__init__.py`, dan seluruh kamus terjemahan `i18n.js` ke `1.3.0`.

---

## [1.0.0] - 2026-11-12

### Ditambahkan (Added)
- Rilis perdana YT2Spotify (yt2sp).
- Migrasi playlist dari YouTube Music ke Spotify tanpa biaya token API resmi Spotify (menggunakan *spotifyscraper* dan *ytmusicapi*).
- Multi-pass matcher (ISRC Deezer + Spotify search heuristic).
- Antarmuka web modern dengan dukungan tema gelap/terang/neon/kaca dan Mode Kentang (*Potato Mode*) untuk laptop spek rendah.
