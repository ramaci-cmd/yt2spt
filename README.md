<div align="center">

# 🎵 YT2Spotify (`yt2sp`)

**Fast, 100% Free, Zero-API-Cost YouTube Music to Spotify Playlist Migration Tool.**<br/>
Accurate multi-pass track resolution, instant 30-second audio previews, 2×2 collage playlist artwork, smart genre splitting, and native Spotify Desktop clipboard pasting.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Zero API Cost](https://img.shields.io/badge/API_Cost-%240_%2F_Free-brightgreen.svg)]()
[![Privacy](https://img.shields.io/badge/Privacy-100%25_Local_SQLite-blueviolet.svg)]()
[![Tests](https://img.shields.io/badge/Tests-21%20Passed-success.svg)](tests/)

**No Spotify Developer account needed · No paid tokens or subscription fees · No web login required · 100% local privacy**

[Quick Start](#-quick-start) · [Key Features](#-key-features) · [Interface Previews](#-interface-previews) · [How It Works](#-how-it-works) · [CLI Reference](#-cli-reference) · [Troubleshooting & FAQ](#-troubleshooting--faq)

</div>

---

<details>
<summary><kbd>Table of contents</kbd></summary>

- [🚀 Quick Start](#-quick-start)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Launch the Web Dashboard](#launch-the-web-dashboard)
- [✨ Key Features](#-key-features)
- [📸 Interface Previews](#-interface-previews)
  - [1. Modern Web Dashboard](#1-modern-web-dashboard)
  - [2. Review Studio & Smart Genre Splitter](#2-review-studio--smart-genre-splitter)
  - [3. Playlists Library & 2×2 Collage Artwork](#3-playlists-library--22-collage-artwork)
  - [4. Spotify Desktop Paste Guide](#4-spotify-desktop-paste-guide)
- [⚙️ How It Works](#-how-it-works)
  - [1. Multi-Pass Matching Engine](#1-multi-pass-matching-engine)
  - [2. Dual-Provider Audio Preview (Chorus / Reff)](#2-dual-provider-audio-preview-chorus--reff)
  - [3. Instant Desktop Clipboard Import (`Ctrl + V`)](#3-instant-desktop-clipboard-import-ctrl--v)
- [🖥️ CLI Reference](#-cli-reference)
  - [Command Table](#command-table)
  - [End-to-End Terminal Walkthrough](#end-to-end-terminal-walkthrough)
- [🛡️ Privacy & Security Rails](#-privacy--security-rails)
- [🧱 Tech Stack & Project Layout](#-tech-stack--project-layout)
- [🩺 Troubleshooting & FAQ](#-troubleshooting--faq)
- [📄 License](#-license)

</details>

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.11** or later
- The official **Spotify Desktop Client** (Windows or macOS) for instant `Ctrl + V` playlist pasting
- Any modern web browser (Chrome, Edge, Firefox, Brave)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ramaci-cmd/yt2spt.git
   cd yt2spt
   ```

2. **Create and activate a virtual environment:**
   ```bash
   # Windows (PowerShell)
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install the package in editable mode:**
   ```bash
   pip install -e .
   ```

### Launch the Web Dashboard

Start the local background server:
```bash
yt2sp ui
# Or alternatively: python -m yt2sp.ui.server
```
Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your browser.

> [!TIP]
> Prefer headless automation or cron jobs? `yt2sp` includes a full-featured terminal CLI with the exact same matching engine. See the [CLI Reference](#-cli-reference) below.

---

## ✨ Key Features

- 💸 **100% Free & Zero API Costs ($0 / Rp0):** Direct catalog discovery without paying for third-party subscription transfer services (Soundiiz, TuneMyMusic) or needing complex Spotify Developer API credentials.
- 🎯 **Multi-Pass High-Precision Matcher:**
  - **Aggressive Title Normalization:** Cleans video noise (`[Official Video]`, `ft.`, `Remix`, `4K`, brackets `【...】`, and artist uploader channel names).
  - **Fuzzy Levenshtein Distance:** Evaluates title and artist similarity using high-performance C++ bindings via [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz).
  - **Duration Tolerance Window ($\pm 10\%$):** Safely discriminates full-length studio tracks from truncated video clips or extended DJ sets.
  - **Deezer ISRC Fallback:** Second-pass validation for difficult-to-find international and indie releases.
- 🎧 **Instant 30-Second Audio Previews (Chorus / Reff):** Stream audio samples directly in the browser simply by hovering over any song thumbnail. Powered by an automated fallback cascade (Deezer API $\rightarrow$ iTunes Search API) with zero authentication tokens required.
- 🖼️ **Dynamic 2×2 Collage Playlist Artwork:** Procedural 2×2 grid collage dynamically constructed from the first 4 track thumbnails inside each playlist, wrapped in an interactive retro vinyl sleeve that pulls out on hover.
- 🏷️ **Smart Genre Tagging & 1-Click Splitter:** Automated categorization into Pop, Hip-Hop, Rock, Electronic, R&B, Dangdut, K-Pop, and more. Split massive libraries into focused genre playlists with one click.
- ⚡ **Low-Spec Potato Mode:** Built-in hardware acceleration toggle that disables GPU-heavy blur filters, shimmering skeletons, and visualizer waves for buttery 60 FPS performance on budget laptops.
- 🌐 **6-Language Internationalization:** Seamless on-the-fly switching between **English**, **Indonesian**, **Spanish**, **Japanese**, **Korean**, and **Chinese**.
- 🔒 **100% Local & Private:** All playlist metadata and SQLite databases reside strictly on your own device. Zero telemetry, tracking, or remote database storage.

---

## 📸 Interface Previews

### 1. Modern Web Dashboard
A clean, responsive command center displaying local library health, sync metrics, quick-transfer launchpad, and recently extracted playlists with retro vinyl sleeve cards.

![Dashboard Overview](docs/screenshots/01-dashboard.png)

---

### 2. Review Studio & Smart Genre Splitter
Audit match precision with confidence percentages, stream instant audio previews by hovering over song thumbnails, filter out non-music UGC clips, and split collections into standalone genre playlists in 1 click.

![Review Studio](docs/screenshots/02-review-studio.png)

---

### 3. Playlists Library & 2×2 Collage Artwork
Archive and inspect saved YouTube Music playlists, view dynamic 2×2 collage artworks generated from playlist contents, monitor private/deleted video counters, and perform batch operations.

![Playlists Library](docs/screenshots/03-playlists-library.png)

---

### 4. Spotify Desktop Paste Guide
A step-by-step interactive guide with 1-click clipboard integration, copy-in-batches mode (50 songs per chunk), and troubleshooting tips for Spotify Desktop.

![Help & Guide](docs/screenshots/04-guide.png)

---

## ⚙️ How It Works

### 1. Multi-Pass Matching Engine

```
YouTube Music Track
       │
       ▼
[ Title Sanitization & Normalization ]
  • Strip '[Official Music Video]', 'ft.', 'Lyrics', '4K', 'MV'
  • Clean Japanese/Chinese brackets '【...】'
  • Remove uploader channel name suffixes
       │
       ▼
[ Tier 1: Spotify Direct Catalog Scraper ]
  • Query Spotify internal web catalog without Developer API keys
  • RapidFuzz fuzzy token sort ratio on (Title + Artist)
  • Validate duration within ±10% or ±12 seconds
       │
       ├─► Score ≥ 0.85 ──► [ Resolved Auto (T1) ]
       │
       ▼
[ Tier 2: Deezer ISRC Bridge Fallback ]
  • Search Deezer metadata catalog for official ISRC code
  • Re-query Spotify catalog using exact ISRC identifier
       │
       ├─► Found & Verified ──► [ Resolved Auto (T2) ]
       │
       ▼
[ Tier 3: Needs Review / User Selection ]
  • Flagged for 1-click confirmation or alternative picking in Review Studio
```

### 2. Dual-Provider Audio Preview (Chorus / Reff)
When hovering over any track thumbnail in the Review Studio or Track Library, `yt2sp` streams an instant 30-second audio preview of the song's chorus:
1. First tries Deezer's high-bitrate MP3 preview endpoint.
2. If unavailable, falls back automatically to Apple's iTunes Search API preview stream.
3. Completely free, requires zero credentials, and includes built-in debounce and caching to ensure rapid streaming.

### 3. Instant Desktop Clipboard Import (`Ctrl + V`)
Instead of making slow, rate-limited REST API calls to create Spotify playlists (which frequently trigger 429 errors or require expired OAuth tokens), `yt2sp` exploits a native Spotify Desktop feature:
1. `yt2sp` formats matched songs into standard Spotify URIs: `spotify:track:xxxxxxxxxxxxxxxxxxxxxx`.
2. Click **"Copy All Spotify URIs"** or **"Copy in 50-Blocks"**.
3. Create a new empty playlist in **Spotify Desktop**, click the playlist tracks area, and press **`Ctrl + V`** (or **`Cmd + V`** on macOS).
4. All tracks appear in your Spotify playlist immediately!

---

## 🖥️ CLI Reference

### Command Table

| Command | Description |
| :--- | :--- |
| `yt2sp init` | Initialize local SQLite schema (`yt2sp.db`) and default configuration |
| `yt2sp ui` | Launch the modern browser dashboard on `http://127.0.0.1:5000` |
| `yt2sp extract <URL>` | Extract track metadata from a public or unlisted YouTube Music playlist |
| `yt2sp resolve` | Run the multi-pass matcher against Spotify's catalog for all pending tracks |
| `yt2sp review` | Interactive terminal UI to inspect matches, listen to audio previews, and resolve conflicts |
| `yt2sp export` | Copy Spotify URIs to system clipboard (ready for `Ctrl + V`), or export to CSV / TXT |
| `yt2sp tag_genre` | Auto-detect genres across library using dual iTunes + Deezer APIs |
| `yt2sp split` | Generate individual genre-specific playlist URI blocks |
| `yt2sp status` | Display library statistics, match counts, and accuracy confidence metrics |
| `yt2sp auth_ytm` | Set up browser authentication headers to extract personal "Liked Music" |
| `yt2sp reset_cmd` | Safely wipe local database and start fresh |

### End-to-End Terminal Walkthrough

```bash
# 1. Initialize local database
yt2sp init

# 2. Extract songs from any YouTube Music playlist
yt2sp extract "https://music.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxx"

# 3. Match against Spotify's catalog
yt2sp resolve

# 4. Automatically categorize tracks into genres
yt2sp tag_genre

# 5. Export matched Spotify URIs directly to clipboard
yt2sp export --clipboard

# 6. Open Spotify Desktop, create a playlist, and press Ctrl + V!
```

---

## 🛡️ Privacy & Security Rails

- **Zero Remote Storage:** Your playlist history, song names, and database entries are stored exclusively in `yt2sp.db` on your local filesystem.
- **No OAuth Secrets Stored:** You never need to supply Spotify client secrets or log in to a third-party server.
- **No Telemetry:** `yt2sp` does not collect usage analytics, telemetry, or IP logs.
- **Safe Resumption:** If an extraction or matching run is interrupted, re-running the command resumes right where it left off without duplicating tracks.

---

## 🧱 Tech Stack & Project Layout

```
yt2sp/
├── yt2sp/
│   ├── cli.py             # Rich + Typer terminal command interface
│   ├── config.py          # Configuration loader
│   ├── extract/
│   │   ├── parser.py      # Title normalizer, noise cleaner, and regex filters
│   │   └── ytm.py         # YouTube Music API extractor
│   ├── resolve/
│   │   ├── matcher.py     # Multi-pass matching pipeline
│   │   ├── spotify.py     # Spotify catalog scraper
│   │   └── score.py       # RapidFuzz similarity scoring & duration validation
│   ├── genre/
│   │   └── tagger.py      # iTunes + Deezer genre categorization
│   ├── store/
│   │   ├── db.py          # SQLite database layer & 2x2 collage queries
│   │   └── models.py      # Data structures
│   └── ui/
│       ├── server.py      # Native Python HTTP API server
│       ├── index.html     # Modern web dashboard with Tailwind CSS & Lucide icons
│       └── i18n.js        # Multi-lingual translations (EN, ID, ES, JA, KO, ZH)
├── docs/
│   └── screenshots/       # Application interface preview captures
├── tests/                 # Pytest test suite (21 unit & integration tests)
└── pyproject.toml         # Python packaging configuration
```

---

## 🩺 Troubleshooting & FAQ

<details>
<summary><strong>Q: Why doesn't Ctrl + V work when I paste into Spotify Web Player?</strong></summary>

> **A:** Web browsers run in a sandboxed security environment that blocks web apps from reading raw multi-line clipboard track URI lists. You **must use the official Spotify Desktop app** (Windows or macOS) for `Ctrl + V` pasting to work.
</details>

<details>
<summary><strong>Q: How does audio preview work without Spotify or Deezer API keys?</strong></summary>

> **A:** `yt2sp` queries public 30-second audio sample endpoints hosted by Deezer CDN and Apple iTunes Search API. These public endpoints stream compressed 30s chorus snippets for catalog discovery without requiring user authentication.
</details>

<details>
<summary><strong>Q: What does "(1 private/removed)" mean next to my playlist?</strong></summary>

> **A:** YouTube Music occasionally displays an aggregate track count in the playlist header that includes videos made private or deleted by their original uploader. `yt2sp` detects this mismatch, informs you of the exact unavailable count, and ports all available songs seamlessly.
</details>

<details>
<summary><strong>Q: Can I transfer my personal "Liked Songs"?</strong></summary>

> **A:** Yes! Run `yt2sp auth_ytm` in your terminal to authenticate your session with YouTube Music, then run `yt2sp extract --liked`.
</details>

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.

---

<div align="center">
<sub>Built with precision by <strong><a href="https://github.com/ramaci-cmd">ramaci-cmd</a></strong></sub>
</div>
