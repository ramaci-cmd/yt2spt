# UI/UX DESIGN SYSTEM LOCK & VISUAL REGRESSION REPORT
**Definitive Design System Audit, Asset Inventory, & Visual Regression Protection**

* **Project:** `yt2sp` Unified Music Migration Platform
* **Theme System:** Transactify Luxury Editorial Theme (`data-theme="transactify"`)
* **Audit Scope:** HTML layout, CSS custom properties, Tailwind tokens, animations, transitions, typography, iconography, component behaviors, responsive breakpoints.

---

## 1. CANONICAL COLOR PALETTE & DESIGN TOKENS

The application uses an editorial luxury color system inspired by organic nature tones, tactile paper canvas, and precise interface contrasts. All tokens are locked and preserved without alteration.

### Core Canvas & Surface Tokens

| Token Name | CSS Custom Property | Exact Hex / RGBA | Role / Usage |
| :--- | :--- | :--- | :--- |
| **Canvas Background** | `--color-canvas` | `#F7F6F2` | Page background, editorial framing |
| **Pure Surface** | `--color-surface` | `#FFFFFF` | Card containers, floating pills, modals |
| **Soft Surface / Warm Tray** | `--color-soft-surface` | `#F1F1EB` / `#F2F1EC` | Embedded containers, table trays, drag zones |
| **Forest Green (Primary)** | `--color-forest` | `#183327` | Primary buttons, active pill tabs, active states |
| **Forest Hover** | `--color-forest-hover` | `#234939` | Hover state for primary action buttons |
| **Sage Light** | `--color-sage` | `#E8F2EC` | Subtle accent highlights, active tag backgrounds |
| **Sage Text** | `--sageText` | `#1E5638` | Text inside sage badges |
| **Main Text (Primary)** | `--color-main-text` | `#20251F` | High-contrast headings, active icons |
| **Text Secondary** | `--text-secondary` | `#526058` | Subheadings, section descriptions, table text |
| **Muted Text** | `--color-muted-text` | `#737B73` / `#84938B` | Timestamps, placeholders, inactive icons |
| **Border Neutral** | `--color-border` | `#E7E7DF` | Card borders, dividers, subtle separators |
| **Editorial Hairline** | (Tailwind inline) | `rgba(18, 22, 20, 0.08)` | Frame boundaries, table dividers |
| **Modal Overlay** | `--color-overlay-dark` | `rgba(18, 22, 20, 0.65)` | Backdrop blur for modals |

### Platform & Semantic Status Tokens

| Brand / Status | Exact Hex | Contrast Standard | Usage in Unified Platform |
| :--- | :--- | :--- | :--- |
| **Spotify Green** | `#1DB954` | WCAG AA compliant on dark/light | Spotify target badges, Spotify copy button |
| **YouTube Music Red** | `#FF3545` | Vibrant accent | YouTube Music source badges, YTM export button |
| **Status Success** | `#2B8A57` | Soft forest emerald | Auto-matched checkmarks, success toast |
| **Status Warning** | `#D97706` | Warm amber | Needs Review cards, ambiguous match badge |
| **Status Error** | `#DC2626` | Deep red | Missing tracks, rejected items, error toast |
| **Terracotta Accent** | `#9C5B3E` / `#FBF2EC` | Warm rust tint | Smart splitter mood & genre tags |

---

## 2. TYPOGRAPHY SPECIFICATIONS

The typography hierarchy pairs an editorial serif for expressive narrative headings with a high-legibility geometric sans-serif for interface controls.

### Font Families & Imports
* **Google Fonts Import URL:**
  ```html
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap" rel="stylesheet">
  ```
* **Serif Headings (`font-serif`):**
  * Family: `'Instrument Serif', Georgia, serif`
  * Weights: Normal (`400`), Italic (`italic 400`)
  * Usage: Hero titles ("Bring All Your Tracks Together", "Organize Your", "Move Music"), section accents.
* **Interface Sans (`font-sans`):**
  * Family: `'Plus Jakarta Sans', Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
  * Weights: Regular (`400`), Medium (`500`), Semibold (`600`), Bold (`700`)
  * Letter Spacing: Tracking-tight (`-0.03em`) on titles, tracking-wider (`0.2em`) on uppercase sub-labels.
* **Monospace Data (`font-mono`):**
  * Family: `ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace`
  * Usage: Song durations, step numbers (`01`, `02`), track counters, timestamps.

---

## 3. SPACING, GEOMETRY, & DEPTH

### Spacing Scale
* Base grid unit: 4px.
* Section padding: `px-4 sm:px-8 md:px-12 py-8 md:py-12`.
* Card padding: `p-5 md:p-6` for standard cards; `p-1.5` for floating pills.
* Maximum container width: `max-w-[1200px]` bounded by `.editorial-frame`.

### Border Radius Hierarchy
* **Pill Elements (`rounded-full`):** Floating navigation capsules, search input bars, action buttons, status pills.
* **Outer Trays (`rounded-3xl` / 24px):** Section backgrounds, Alpine meadow overview container, 3-step feature cards.
* **Cards & Modals (`rounded-2xl` / 16px):** Step 1–5 interaction cards, Review Studio cards, playlist detail modals.
* **Inner Controls (`rounded-xl` / 12px):** Inputs, track items, genre splitter chips.
* **Micro Elements (`rounded-lg` / 8px):** Buttons, mini icon containers.

### Elevation & Shadows
* **Card Depth:** `--shadow-card-depth: 0 12px 32px -4px rgba(18, 35, 25, 0.05), 0 2px 8px -2px rgba(18, 35, 25, 0.03);`
* **Elevated Depth:** `--shadow-elevated-depth: 0 20px 48px -6px rgba(18, 35, 25, 0.08), 0 4px 16px -2px rgba(18, 35, 25, 0.04);`
* **Subtle Highlights:** `shadow-sm` on white floating pills; `shadow-xs` on sticky liquid glass header.

---

## 4. ANIMATION & MOTION INVENTORY

All motion in the application adheres to Disney's 12 Principles of Animation, providing tactile, responsive feedback.

| Motion Class / Keyframe | Timing / Easing | Transform Behavior | Usage |
| :--- | :--- | :--- | :--- |
| `.btn-motion` | `140ms cubic-bezier(0.34, 1.45, 0.64, 1)` | Hover: `translateY(-1px)`; Active: `scale(0.97)` | All interactive buttons and direction pills |
| `.icon-nudge` | `200ms cubic-bezier(0.34, 1.45, 0.64, 1)` | Hover: `translateX(2.5px)` | Arrow icons on action buttons |
| `.nav-transition` | `180ms cubic-bezier(0.4, 0, 0.2, 1)` | Opacity, transform, background-color | Table rows, tab switches, hover transitions |
| `.fade-enter` | `220ms cubic-bezier(0.16, 1, 0.3, 1)` | `from: opacity 0, translateY(6px)` to `1, 0` | Page and tab transitions |
| `.skeleton-shimmer` | `1.4s ease-in-out infinite` | `opacity: 0.45` to `0.8` | Loading states for tracks and cards |
| `.fluted-divider` | Static repeating gradient | `repeating-linear-gradient(90deg, ...)` | Tactile pinstripe separator between sections |
| **Liquid Glass Header** | `300ms ease-in-out` | Backdrop blur + opacity change past 75vh | Sticky header scroll adaptation |

---

## 5. ICONOGRAPHY & ASSET INTEGRITY

* **Primary Icon Library:** Lucide Icons (`unpkg.com/lucide@latest`).
* **Stroke Width:** Consistently locked at `1.5` to `2.0px`.
* **Standard Sizes:**
  * Micro icons: `w-3.5 h-3.5` (14px) — table actions, badges, nudges.
  * Inline controls: `w-4 h-4` (16px) — input icons, tab icons.
  * Section icons: `w-5 h-5` (20px) — modal headers.
  * Status hero icons: `w-7 h-7` (28px) — success circle.
* **Brand Vectors:** Custom inline SVGs for Spotify and YouTube Music logos, preserving official aspect ratios.
* **Hero Artwork:** Local high-resolution assets in `ui/assets/` (`hero_landscape.jpg`, `alpine_meadow.jpg`, `album_cover.jpg`).

---

## 6. RESPONSIVE BREAKPOINT INVENTORY

| Breakpoint | Width Trigger | Adaptive Behavior |
| :--- | :--- | :--- |
| **Mobile (`<640px`)** | Default | Single column stack, compact floating header, drawer navigation. |
| **Tablet (`sm: 640px`)** | `>=640px` | 2-column genre grid, horizontal button grouping, wider dividers. |
| **Laptop (`md: 768px`)** | `>=768px` | 12-column editorial grid, side-by-side header layouts, full table view. |
| **Desktop (`lg: 1024px`)** | `>=1024px` | Liquid glass top-nav capsule visible, 3-column feature grid. |
| **Max Frame (`1200px`)** | Bounded | `.editorial-frame` locks max width with subtle left/right hairline borders. |

---

## 7. VISUAL COMPARISON & INTEGRATION VERIFICATION

### What Changed Visually?
The integration was conducted with strict adherence to the **Design System Lock**:
1. **Migration Direction Selector:**
   * Embedded cleanly within Step 1 using the canonical warm tray (`bg-[#F2F1EC]`, `border-black/[0.08]`, `rounded-full`).
   * Active state uses canonical forest green (`bg-[#183327]`, `text-white`).
   * Inactive state uses canonical secondary text (`text-[#526058]`, hover `text-[#121614]`).
   * Animated with the canonical `.btn-motion` squash-and-stretch curve.
2. **Catalog Provider Badges:**
   * Each playlist in the Library list view displays a minimal badge (`Spotify → YTM` in emerald tint, `YTM → Spotify` in rose tint) seamlessly integrated beside the title.
3. **Export Actions:**
   * Maintained all original Spotify export controls ("Salin Semua Link/URI", "Salin per Bagian") while seamlessly displaying the YouTube Music export button when targeting YouTube Music.
4. **Zero-Disruption Header & Navigation:**
   * Top navigation tabs (`Overview`, `Playlists`, `Transfer`, `Review Studio`, `Accounts`, `Guide`, `Settings`) remain 100% identical in position, styling, and behavior.

---

## 8. DESIGN SYSTEM COMPLIANCE VERDICT

| Evaluation Criteria | Requirement | Compliance Verdict |
| :--- | :--- | :--- |
| **Color Tokens** | 100% preservation of hex/rgba variables | **PASSED (Locked)** |
| **Typography Hierarchy** | Instrument Serif + Plus Jakarta Sans | **PASSED (Locked)** |
| **Component Proportions** | Exact padding, margins, and border-radii | **PASSED (Locked)** |
| **Motion Physics** | Disney 12 Principles (`.btn-motion`, spring ease) | **PASSED (Locked)** |
| **Iconography Standard** | Lucide SVGs at 1.5–2.0px stroke | **PASSED (Locked)** |
| **Responsive Integrity** | 1200px editorial frame across mobile/desktop | **PASSED (Locked)** |
| **Existing User Familiarity** | Zero visual disruption or forced redesign | **PASSED (Locked)** |
