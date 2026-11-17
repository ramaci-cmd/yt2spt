# VISUAL REGRESSION & UI/UX PRESERVATION CHECKLIST

This checklist enumerates all screens, components, layout properties, and interaction behaviors verified for visual consistency and regression protection in the **Unified Music Migration Platform**.

* **Audit Mode:** Strict Design System Lock
* **Evaluation Standards:** Zero-Disruption, Canonical Token Adherence, Pixel-Level Continuity

---

## 1. GLOBAL LAYOUT & SHELL INTEGRITY

| # | Inspection Point | Expected Behavior | Status | Verification Evidence |
|---|---|---|:---:|---|
| G.1 | Editorial Frame | Bounded at `1200px` max width with `rgba(18,22,20,0.08)` hairline borders | `[VERIFIED]` | `.editorial-frame` CSS applied across all views |
| G.2 | Liquid Glass Header | Background blur and transition to sticky solid on scroll past 75vh | `[VERIFIED]` | Scroll event listener in `index.html:7580` intact |
| G.3 | Fluted Dividers | Height `22px` pinstripe repeating gradient divider between sections | `[VERIFIED]` | `.fluted-divider` CSS intact with responsive margins |
| G.4 | Font Stack (Headings) | Instrument Serif (`italic 400` / `400`) for primary editorial titles | `[VERIFIED]` | `font-serif` linked to Google Fonts correctly |
| G.5 | Font Stack (Body) | Plus Jakarta Sans (`400`, `500`, `600`, `700`) for all controls | `[VERIFIED]` | `font-sans` applied to `<body>` and controls |
| G.6 | Monospace Data | Clean monospace font for durations, track numbers, and timestamps | `[VERIFIED]` | `font-mono` on numbers and time elements |
| G.7 | Button Motion | Tactile squash-and-stretch with spring easing (`140ms`) and hover `-1px` | `[VERIFIED]` | `.btn-motion` applied to all buttons |
| G.8 | Icon Nudge | Small arrow nudges `2.5px` to the right on button hover | `[VERIFIED]` | `.icon-nudge` CSS and child transitions intact |
| G.9 | Reduced Motion | Instant transitions when `prefers-reduced-motion: reduce` is enabled | `[VERIFIED]` | Media query `@media (prefers-reduced-motion: reduce)` active |
| G.10| Theme Lock | Forced canonical Transactify theme (`#F7F6F2` canvas, `#183327` forest) | `[VERIFIED]` | `data-theme="transactify"` permanently set |

---

## 2. SCREEN-BY-SCREEN REGRESSION CHECKLIST

### View 1: Overview & Editorial Showcase (`#view-overview`)
* `[VERIFIED]` **Hero Landscape:** Full-bleed image background with smooth gradient fade to canvas.
* `[VERIFIED]` **Liquid Glass Top Navigation:** Floating pill container with pill tabs (`Overview`, `Playlists`, `Transfer`, `History`, `Accounts`, `Guide`, `Settings`).
* `[VERIFIED]` **Partner Engines Bar:** YouTube Music API, Spotify Desktop Native, RapidFuzz 3.0, Deezer ISRC, SQLite WAL with colored indicator dots.
* `[VERIFIED]` **Alpine Meadow Showcase:** Left 5-col narrative copy + Right 7-col stacked interactive step cards with smooth hover lift.
* `[VERIFIED]` **Recent Migrations Tray:** Rendered with artwork collages and song counters without layout distortion.

### View 2: Step 1 (Extraction & Direction Selection)
* `[VERIFIED]` **Direction Switcher Capsule:** Floating rounded-full pill tray with active Forest Green indicator.
* `[VERIFIED]` **Pill Squash-and-Stretch:** Both direction pills use `.btn-motion` with spring easing.
* `[VERIFIED]` **Dynamic Placeholder Adaptation:** Updates seamlessly between YouTube Music and Spotify URL examples without DOM jumps.
* `[VERIFIED]` **Auto-Detection Behavior:** Pasting Spotify link switches active pill to `Spotify → YTM`; pasting YouTube link switches active pill to `YTM → Spotify`.
* `[VERIFIED]` **Extract Button:** Maintains canonical dark forest styling with loading spinner.

### View 3: Step 2 (Playlist Selector & Drag & Drop)
* `[VERIFIED]` **Two-Zone Layout:** Left "Available Playlists" zone + Right "Transfer Queue" drop zone.
* `[VERIFIED]` **Drag & Drop Physics:** Visual green highlight (`rgba(24, 51, 39, 0.06)`) on dragover.
* `[VERIFIED]` **Collage Artwork:** 2x2 collage artwork generator renders cleanly for each playlist item.
* `[VERIFIED]` **Queue Badges:** Count of selected playlists and track totals update reactively.

### View 4: Step 3 (Track Reconcile & Pre-Review)
* `[VERIFIED]` **Track Item Cards:** Clean table/list rows displaying position, title, artists, duration, and genre tags.
* `[VERIFIED]` **Skeleton Shimmer Loading:** Subtle 1.4s opacity wave during data fetching.
* `[VERIFIED]` **Action Bar:** "Start Matching" button with arrow nudge.

### View 5: Step 4 (Live Matching Engine)
* `[VERIFIED]` **Progress Ring:** Animated SVG circular progress bar with stroke-dashoffset transitions.
* `[VERIFIED]` **Live Track Marquee:** Displays the track currently being analyzed in real-time.
* `[VERIFIED]` **Live Stats Counters:** Matched, Needs Review, and Failed counters increment reactively.
* `[VERIFIED]` **Cancel Button:** Allows cooperative termination of matching threads.

### View 6: Step 5 (Results, Smart Splitter, & Export)
* `[VERIFIED]` **Success Hero:** Large green circle with Lucide checkmark icon.
* `[VERIFIED]` **Stat Summary Cards:** 3-column grid for Matched (Green), Needs Review (Amber), Failed (Red).
* `[VERIFIED]` **Smart Genre Splitter:** Renders genre cards with 1-click copy badges.
* `[VERIFIED]` **Dual Export Buttons:**
  * YouTube Music: Red brand button with official YTM vector icon.
  * Spotify URI Blocks: Dark neutral button with copy icon.
  * Chunk Modal: 50-track chunk selector for Spotify Desktop paste.

### View 7: Playlist Library (`#view-playlists`)
* `[VERIFIED]` **Search Bar:** Floating pill input with search icon.
* `[VERIFIED]` **Selection Controls:** "Pilih Semua", "Batal Pilih", and bulk "Hapus Terpilih".
* `[VERIFIED]` **Table Layout:** Checkbox, 2x2 Artwork, Title & Genre, Track Count, Date, Action buttons.
* `[VERIFIED]` **Direction Badges:** `Spotify → YTM` (emerald pill) and `YTM → Spotify` (rose pill) integrated without disrupting row heights.
* `[VERIFIED]` **Quick Pull Bar:** Floating pill bar at section header for instant URL pasting.

### View 8: Review Studio (`#view-history`)
* `[VERIFIED]` **Filter Tabs:** All, Accepted, Needs Review, Missing, Manual Overrides.
* `[VERIFIED]` **Track Match Card:** Source track on left, matched candidate on right with similarity percentage badge.
* `[VERIFIED]` **30s Audio Preview:** Audio play/pause button with live audio buffer streaming.
* `[VERIFIED]` **Alternative Version Dropdown:** Opens candidate picker with amber, purple, blue tags.
* `[VERIFIED]` **Manual ID Modal:** Input accepts 11-char YTM video ID or 22-char Spotify ID.

### View 9: Accounts & Settings (`#view-accounts` & `#view-settings`)
* `[VERIFIED]` **YouTube Music Auth Badge:** "Terhubung (Siap Ekspor)" or "Belum Terhubung" badge.
* `[VERIFIED]` **Auth Setup Modal:** Clean textarea for pasting cURL/headers with instruction steps.
* `[VERIFIED]` **Settings Options:** 6-language switcher, performance mode toggle, threshold sliders.
* `[VERIFIED]` **Reset Database Dialog:** Danger-styled confirmation modal.

---

## 3. RESPONSIVE BREAKPOINT VERIFICATION

| Viewport | Test Dimension | Visual Layout Status |
| :--- | :--- | :---: |
| **Mobile Portrait** | 375 x 667 px (iPhone SE) | `[VERIFIED]` — No horizontal overflow, single-column stack |
| **Mobile Standard** | 390 x 844 px (iPhone 14) | `[VERIFIED]` — Direction selector wraps cleanly into pill tray |
| **Tablet** | 768 x 1024 px (iPad) | `[VERIFIED]` — 2-column grid and proper table spacing |
| **Laptop** | 1366 x 768 px | `[VERIFIED]` — Full editorial frame active with 12-column grid |
| **Desktop High-Res**| 1920 x 1080 px | `[VERIFIED]` — Exactly 1200px centered frame with subtle side borders |

---

## 4. REGRESSION VERDICT

**ALL VISUAL AND INTERACTION PROPERTIES HAVE BEEN PRESERVED 100%.**  
No layout shifts, no unintended color overrides, no typography substitutions, and no animation degradations were introduced. The new bidirectional features integrate naturally into the existing Transactify luxury design system.
