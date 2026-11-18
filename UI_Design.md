# UI Design Spec — Campaign Ad Intelligence & War Room

**Purpose:** Visual and interaction spec for the dashboard, so Antigravity builds a consistent UI.
**Reference style:** The attached reference dashboard (light, card-based, green-accented analytics UI). We copy its *style* — layout, spacing, card treatment, chart feel. We do **not** copy its name, logo, or content.
**Audience:** Campaign budget and media strategists. Every screen should answer "where should the next dollar go, and why?"
**Stack:** Streamlit + Altair (per `GEMINI.md`). Some details below (exact pixel sizes, skeleton loaders, hover sync) are targets that Streamlit can only approximate. **§11 is the authoritative mapping** from each design element to a Streamlit widget, an Altair mark, or injected CSS, and it states where we accept a simpler version.

---

## 1. Design Principles

1. **Calm canvas, loud data.** The background is neutral gray and cards are white. Color appears only where it carries meaning.
2. **One card = one question.** Each card has a title that states what it answers, plus an optional subtitle and an optional filter dropdown in the top-right.
3. **KPIs first, detail below.** Every page opens with a row of KPI cards, then one hero chart, then supporting cards.
4. **Honesty is part of the UI.** Every metric carries a data-fidelity badge (*Observed / Aggregated / Modeled*). Ranges are shown as bands, not single numbers.
5. **Partisan colors are reserved.** Blue and red mean Democrat and Republican *only*. The green brand accent is for UI chrome: navigation, buttons, and focus states.

---

## 2. Layout & Grid

```
┌──────────────────────────────────────────────────────────────────────┐
│  [Logo]  Page Title        [Scope ▾] [District|County]  🔍  🔔  (👤) │  ← Top bar (white card, 72px)
├────────────┬─────────────────────────────────────────────────────────┤
│            │  [KPI]      [KPI]      [KPI]      [KPI]                 │  ← KPI row
│  Sidebar   │  ┌───────────────────────────────────────────────────┐  │
│  (white    │  │                 Hero chart / map                  │  │  ← Hero card (full width)
│   card,    │  └───────────────────────────────────────────────────┘  │
│   240px)   │  ┌──────────────────────┐ ┌──────────────────────────┐  │
│            │  │  Supporting card     │ │  Supporting card         │  │  ← 5/12 + 7/12 split
│  ───────   │  └──────────────────────┘ └──────────────────────────┘  │
│  Help      │                                                         │
│  Settings  │                                                         │
└────────────┴─────────────────────────────────────────────────────────┘
```

| Element | Spec |
|---|---|
| App frame | Outer background `--bg-canvas`, inner padding 24px |
| Top bar | White card, height 72px, radius 16px, spans full width above sidebar + content |
| Sidebar | White card, width 240px (collapses to 72px icon rail below 1200px), full height |
| Content | 12-column grid, 24px gutter, 24px gap between card rows |
| KPI row | 3–4 equal cards (span 3 or 4 columns each) |
| Hero card | Span 12, min height 360px |
| Supporting row | Typical splits: 5/7, 6/6, or 4/4/4 |
| Max content width | 1440px, centered |

---

## 3. Design Tokens

### 3.1 Color

**Surfaces & text**

| Token | Hex | Use |
|---|---|---|
| `--bg-canvas` | `#EEF0F3` | Page background behind the frame |
| `--bg-frame` | `#F6F7F9` | App frame / content background |
| `--surface` | `#FFFFFF` | Cards, top bar, sidebar |
| `--border` | `#ECEEF2` | Card hairlines, dividers, input borders |
| `--text-primary` | `#1B1F29` | Titles, KPI values |
| `--text-secondary` | `#6B7280` | Subtitles, axis labels, captions |
| `--text-muted` | `#9CA3AF` | Placeholders, disabled |

**Brand / UI accent (green, from the reference)**

| Token | Hex | Use |
|---|---|---|
| `--accent` | `#22A06B` | Active nav pill, primary buttons, focus ring, slider fill |
| `--accent-soft` | `#E6F6EE` | Hover backgrounds, selected rows |
| `--accent-gradient` | `#22A06B → transparent` | Area-chart fills for *non-partisan* series (e.g. total market spend) |

**Semantic / partisan (reserved)**

| Token | Hex | Meaning |
|---|---|---|
| `--dem` | `#2F6FED` | Our side / Democratic |
| `--dem-soft` | `#9CC7F7` | Our side secondary (e.g. last period, lower bound) |
| `--rep` | `#E04848` | Opponent / Republican |
| `--rep-soft` | `#F4A9A9` | Opponent secondary |
| `--swing` | `#8B5CF6` | Battleground (margin ≤ 5%) |
| `--neutral-series` | `#F2C14E` | Third parties / unaligned / "other" |

**Status pills**

| Token | Background / Text | Use |
|---|---|---|
| `--pill-up` | `#E8F0FF` / `#2F6FED` | Positive delta for us (e.g. "+4.7%") |
| `--pill-down` | `#FDECEC` / `#D14343` | Negative delta for us |
| `--pill-neutral` | `#F1F2F4` / `#6B7280` | No change / informational |

**Data-fidelity badges**

| Badge | Background / Text |
|---|---|
| Observed | `#E6F6EE` / `#1E8A5C` |
| Aggregated | `#EEF2FF` / `#4F46E5` |
| Modeled | `#FFF4E0` / `#B26B00` |
| Sample data | `#FDECEC` / `#B42318` (also triggers the full-width banner, §7) |

**Map scales**
- **Margin (diverging):** `--rep` → `#F7F7F7` (tied) → `--dem`. Districts within ±5% get a `--swing` outline.
- **Intensity (sequential, e.g. spend, ad pressure):** `#F0F4FF` → `--dem`, or the red ramp for opponent metrics.

### 3.1b Dark theme

Users can switch the dark theme on and off (see §4.2 and §8). Only the token *values* change between themes; components reference tokens and never hex values, so no component code changes.

**Surfaces & text**

| Token | Light | Dark |
|---|---|---|
| `--bg-canvas` | `#EEF0F3` | `#0B0D12` |
| `--bg-frame` | `#F6F7F9` | `#10131A` |
| `--surface` | `#FFFFFF` | `#171B24` |
| `--surface-raised` (menus, tooltips) | `#FFFFFF` | `#1F2430` |
| `--border` | `#ECEEF2` | `#262B36` |
| `--gridline` | `#EEF0F3` | `#232834` |
| `--text-primary` | `#1B1F29` | `#E8EAF0` |
| `--text-secondary` | `#6B7280` | `#A0A7B4` |
| `--text-muted` | `#9CA3AF` | `#6B7280` |

**Accent & partisan colors** (slightly brighter in dark mode to hold contrast; soft variants become darker tints)

| Token | Light | Dark |
|---|---|---|
| `--accent` | `#22A06B` | `#2BB57A` |
| `--accent-soft` | `#E6F6EE` | `rgba(43,181,122,0.14)` |
| `--dem` | `#2F6FED` | `#5B8DEF` |
| `--dem-soft` | `#9CC7F7` | `#2C4A85` |
| `--rep` | `#E04848` | `#F06363` |
| `--rep-soft` | `#F4A9A9` | `#7A3434` |
| `--swing` | `#8B5CF6` | `#A78BFA` |
| `--neutral-series` | `#F2C14E` | `#F2C14E` |
| Map "tied" midpoint | `#F7F7F7` | `#2A2F3A` |

**Pills & badges in dark mode:** use the text color at 16% opacity as the background, and the text color itself brightened ~10%. Example: Observed is `rgba(43,181,122,0.16)` / `#5FD39E`.

**Elevation:** dark mode drops `--shadow-card` and relies on the 1px `--border`. `--shadow-pop` becomes `0 8px 24px rgba(0,0,0,0.5)`.

**Charts:**
- Gradients fade to transparent, so they work on both themes unchanged.
- Gridlines use `--gridline`.
- The tooltip uses `--surface-raised` with a 1px `--border` and a series-colored left edge, instead of a solid colored bubble.

### 3.2 Typography

- **Font:** `Mulish` (Google Fonts), falling back to `Nunito Sans`, then `system-ui`. It is a rounded, geometric sans like the reference.
- **Numbers:** use `font-variant-numeric: tabular-nums` everywhere numbers align (KPIs, tables, axes).

| Role | Size / Weight / Line height |
|---|---|
| Page title (top bar) | 20 / 700 / 28 |
| Card title | 16 / 700 / 24 |
| Card subtitle | 12 / 400 / 16, `--text-secondary` |
| KPI value | 24 / 800 / 32 |
| KPI label | 13 / 600 / 18 |
| Body / table | 14 / 400 / 20 |
| Axis labels, legend, captions | 11–12 / 500 / 16 |
| Pill / badge text | 11 / 600 / 14 |

### 3.3 Spacing, radius, elevation

| Token | Value |
|---|---|
| Spacing scale | 4, 8, 12, 16, 24, 32, 48 |
| Card padding | 20px (KPI cards 16px) |
| `--radius-card` | 16px |
| `--radius-control` | 10px (inputs, dropdowns, nav pill) |
| `--radius-pill` | 999px |
| `--shadow-card` | `0 1px 2px rgba(16,24,40,0.04)` with a 1px `--border` |
| `--shadow-pop` | `0 8px 24px rgba(16,24,40,0.12)` (tooltips, menus) |

---

## 4. Core Components

### 4.1 Sidebar navigation
- White card. Logo at the top, then nav items with a 20px outline icon and a 14px label. Icons are Google Material Symbols (Streamlit's built-in `:material/…:` icons); the Lucide names below are the visual reference, and §11 gives the Material equivalents.
- **Active item:** solid `--accent` pill, white text and icon, radius 10px. **Hover:** `--accent-soft` background.
- The bottom group is pinned: *Methodology & Data Notes*, *Settings*.

| Nav item | Icon (Lucide) |
|---|---|
| Overview | `layout-dashboard` |
| Audience | `users` |
| Opponent Tracker | `crosshair` |
| Electorate | `vote` |
| **War Room** | `swords` (also gets a small green dot badge, since it is the main feature) |
| Methodology & Data Notes | `book-open` |
| Settings | `settings` |

### 4.2 Top bar
Left to right:
1. Page title.
2. **Scope switcher:** dropdown with *Statewide* (default), or *District race*. Choosing District race opens a two-step picker: chamber (Congressional / State Senate / State House), then the district number.
3. **Geography toggle:** segmented control `District | County`. District is the default; the active segment uses `--accent` text on white with a soft shadow.
4. **District type selector:** small dropdown next to the toggle, visible only in District mode.

   | Option | Districts | Notes |
   |---|---|---|
   | Congressional (default) | 14 | 2026 map, including the 2025 redraw of CD 1 and CD 3 |
   | State Senate | 50 | Current enacted map |
   | State House | 120 | Current enacted map |

   All three are built from the same precinct table, so every type rolls up to the same statewide totals.
5. Search (pill-shaped input with a magnifier icon) for advertisers, Pages, counties, and districts of any type (e.g. "SD 18", "HD 104").
6. **Alerts bell** with a red dot when there are unseen opponent alerts. It opens a dropdown feed.
7. **Data freshness chip**, e.g. "Meta snapshot 2h ago · BigQuery 24 Oct".
8. **Theme toggle:** icon button showing a sun in dark mode or a moon in light mode. One click switches themes.
9. Avatar with user name and role.

**Defaults on load:** Statewide scope · District view · Congressional districts.

### 4.3 KPI card
```
┌─────────────────────────────────────┐
│ (icon) Label            ▁▃▅█  ← mini│  icon: 28px circle, soft tint of series color
│ $1.24M  [+4.7%]                bars │  value + delta pill
│ ▲ vs last 7 days   [Observed]       │  caption + fidelity badge
└─────────────────────────────────────┘
```
- The mini bar sparkline (right side) has 4–6 bars; the last bar is in full color and the rest are `#E5E7EB`. This mirrors the reference.
- **Delta pill color depends on whether the change is good for us, not on its sign.** For example, opponent spend going up shows a red pill.
- **Range values:** when the metric is a band, show the midpoint large and the range small beneath ("$40k–$120k").

### 4.4 Chart card (generic)
- **Header:** title, plus a subtitle that states the data source ("Google Political Ads · weekly").
- **Top-right:** a period dropdown ("Last 8 weeks ▾") and optional series toggles.
- **Body:** the chart, with no outer border on the chart itself.
- **Footer (optional):** fidelity badge and an "ⓘ How this is computed" link to the Methodology page.

### 4.5 Tooltip
- Rounded bubble like the reference, implemented by restyling Vega's tooltip element (`#vg-tooltip-element`) in the injected CSS: `--surface-raised` background, `--text-primary` text, radius 10px, `--shadow-pop`. It has no caret, and is the same color for every chart, since Vega tooltips can't change color per series.
- The tooltip contains the value plus context, e.g. "$8,361 · week of 6 Oct". If the value is a band, show "range $5k–$12k".
- A vertical guide line and a white-filled point marker sit on the hovered x-position.

### 4.6 Other components
| Component | Notes |
|---|---|
| Segmented control | Used for District/County and Persuasion/Mobilization |
| Dropdown | Pill-ish (radius 10), light border, chevron |
| Fidelity badge | Small pill; hovering shows a one-line explanation |
| Data table | Zebra-free with 1px row dividers, sticky header, right-aligned numbers, sortable |
| Slider | `--accent` fill, 20px thumb with a white border, value shown in a bubble while dragging |
| Map card | GeoJSON choropleth with a legend and a "Reset view" button; hovering shows a tooltip and clicking drills down |
| Alert item | Icon, one-line headline, timestamp, and "View ads →" link |
| Creative card | Advertiser + date, first lines of copy, spend band, top demographic, theme tag pills, and an "Open in Ad Library" button. There is no thumbnail: Meta's snapshot URL and Google's ad URL are web pages, not images |
| Empty state | Simple line illustration plus one sentence about what will appear and why it's empty |

---

## 5. Chart Styling Rules

| Chart type | Style (matching the reference) |
|---|---|
| Area / line (time series) | Smooth monotone curve, 2px stroke, vertical gradient fill (series color at 30% → 0%), dashed horizontal gridlines `#EEF0F3`, no vertical gridlines |
| Range bands | Spend/impression bounds drawn as a translucent band (15% opacity) behind the midpoint line |
| Bar (grouped) | Rounded top corners (6px), grouped pairs use the strong and soft variant of the same color (us = `--dem` + `--dem-soft`), 8px gap within a group |
| Donut | Thickness ~30% of radius, 2px white gap between segments, legend on the right with colored dot + label + % |
| Heatmap (theme × demographic) | Single-hue sequential ramp, cell value shown on hover, row/column labels 12px |
| Choropleth | Diverging margin scale or sequential intensity (see §3.1), 1px white borders between shapes |

**General chart rules**
- **Axes:** labels only, no axis lines.
- **Values:** abbreviate ($1.2M, 45k).
- **Legend:** top-right of the card, as clickable chips that toggle series.
- **Library:** Altair only (§11.3 gives the exact marks and properties for each style above).
- **Every chart has tooltips. Every x/y chart supports zoom and pan** via `.interactive()`. Maps are the one exception: they zoom by drill-down (click a district to zoom to its counties).

---

## 6. Page Layouts

Every page has the same skeleton: **KPI row, then hero card, then supporting cards.**

### 6.1 Overview
- **KPIs:** Total NC political ad spend (Google + Meta, banded) · Our share of voice · Opponent spend, last 7 days · Active ads, us vs. them.
- **Hero:** District map (or county map, depending on the toggle) colored by baseline margin, with an ad-pressure overlay toggle. A side panel lists the top 5 battleground districts.
- **Supporting:** Weekly spend area chart (us vs. opponent, range bands) · Platform mix donut (Meta / YouTube / Search / Display).

### 6.2 Audience Intelligence ("who sees what")
- **KPIs:** Top-reached age group · Gender split of delivery · Fundraising ads excluded (count) · Themes detected.
- **Hero:** Theme × demographic heatmap, with a toggle for Us / Opponent / Gap.
- **Supporting:**
  - Grouped bars: platform use by age cohort, from the weighted survey, with confidence-interval whiskers.
  - Issue priorities by demographic, from the survey.
  - "Message gap" callout cards, e.g. "18–34 women: high cost-of-living concern, low economic-message delivery."

### 6.3 Opponent Tracker
- **KPIs:** Opponent spend, last 7/30 days · New creatives, last 48h · Top theme · Top district by estimated delivery.
- **Hero:** Share-of-voice over time (stacked or dual area, us vs. them).
- **Supporting:** Alert feed · Creative library grid with filters (theme, platform, date, spend band) · Advertiser table (committee, side, spend band, ad count).

### 6.4 Electorate
- **KPIs:** Registered voters in scope · Unaffiliated share (persuasion pool) · Low-propensity Democrats (mobilization pool) · Early votes cast (when early voting is open).
- **Hero:** District/county map of the selected universe (persuasion, mobilization, or already voted).
- **Supporting:** Vote-method split from the 2022 history (early / Election Day / absentee) · Universe size table by district.

### 6.5 War Room (main feature)
```
┌─────────────────────────────────────────────────────────────────────┐
│ KPI: Budget left $2.00M │ Win prob 46% → 49% (range 41–55) │ Δ net votes │ $/net vote │
├──────────────────────────────┬──────────────────────────────────────┤
│ ALLOCATION BUILDER           │ OUTCOME                              │
│ • Channel-total sliders      │ • Win-probability bar + range band   │
│   (Meta / YouTube / Search / │ • Margin distribution (Monte Carlo   │
│   Display / CTV)             │   histogram, 0 line highlighted)     │
│ • Editable table of line     │ • Marginal votes per $1k by district │
│   items: unit · channel ·    │   (horizontal bars, sorted)          │
│   audience · week · $        │                                      │
│ • Remaining-budget meter     │ [ Auto-optimize next $ ]  (primary)  │
├──────────────────────────────┴──────────────────────────────────────┤
│ PACING: weekly spend plan (stacked bars by channel) vs. weeks left  │
├─────────────────────────────────────────────────────────────────────┤
│ ASSUMPTIONS (collapsible): CPM, saturation, persuasion rate,        │
│ turnout lift, polling error — sliders + preset chips                │
│ [Conservative] [Optimistic] [Mobilization-heavy]                    │
├─────────────────────────────────────────────────────────────────────┤
│ SCENARIOS: saved scenario cards → select 2–3 → side-by-side compare │
└─────────────────────────────────────────────────────────────────────┘
```
- **Scaling the allocation builder:** with 14 congressional districts, every district is a row. With 50 or 120 legislative districts, the builder shows the top 15 districts ranked by marginal votes per $1k, plus an "Add district" search. Unlisted districts sit under a collapsed "All other districts" row with one combined slider.
- **What "win" means depends on scope:** Statewide scope uses the statewide margin. District-race scope uses the margin in the chosen district. For legislative chambers, an optional "Chamber control" view counts projected seats against the majority threshold (26 of 50 in the Senate, 61 of 120 in the House).
- **Instant feedback:** the builder and outcome panel live in one Streamlit fragment, so an edit reruns only that section. Results are cached per allocation, so returning to an earlier plan is instant. A small spinner shows while a new simulation runs.
- **Win probability always shows its range.** It is never displayed as a lone number.
- **The optimizer explains itself.** After it runs, it shows the recommended changes as a diff list ("+$120k Meta → CD 13, mobilization").
- **A "Model, not forecast" ribbon** sits under the page title, linking to the Methodology page.

### 6.6 Methodology & Data Notes
- A single readable column, max 760px wide.
- Sections: Data sources table (source, level, refresh, fidelity) · Model chain diagram · Default assumptions with citations · Known limitations.
- Long text sits on a white card; there are no charts beyond the model diagram.

---

## 7. States & Feedback

| State | Treatment |
|---|---|
| Loading | `st.spinner` inside the card while its data loads (Streamlit has no native skeletons). Cached data makes most loads instant after the first |
| Empty | Short sentence plus a hint ("No opponent ads in this district in the selected period") |
| Error / source down | Card-level inline message with retry; other cards keep working |
| Sample / fallback data | **Full-width amber-red banner** at the top: "Showing SAMPLE data — live source unavailable." Every affected card gets the *Sample data* badge |
| Stale data | Freshness chip turns amber when a snapshot is more than 24h old |
| Drill-down | Breadcrumb in the hero card: `Statewide › CD 12 › Mecklenburg (part)` or `Statewide › State House › HD 104 › Mecklenburg (part)` |

---

## 8. Interaction Details

- **Geography toggle:** switching District ↔ County keeps the current selection where possible. A selected county inside CD 12 stays highlighted, and split counties show a striped pattern in District mode.
- **District type switch:** changing Congressional → State Senate → State House redraws the map and resets any district filter. It keeps county selections, showing which new districts overlap them.
- **Dense maps (State House, 120 districts):**
  - Labels appear only when zoomed in.
  - Hovering shows the district number.
  - A "Show as ranked list" toggle next to the map gives a sortable table of districts, which is easier to scan than 120 small shapes.
- **Data fidelity by district type:**
  - Ad data is never available natively for state legislative districts, so Meta and Google figures there are always *Modeled*.
  - Electorate figures (voter file) and baselines (precinct results) remain *Aggregated*.
- **Cross-filtering:** clicking a district on any map filters the other cards on the same page, and a chip shows the active filter ("CD 12 ✕").
- **Hover sync:** applies only to charts drawn as one combined Altair chart (`vconcat`/`hconcat` sharing a selection parameter), e.g. weekly spend stacked over weekly new ads. Separate cards don't sync on hover; they sync on click via cross-filtering.
- **Theme switching:**
  - The top-bar toggle flips Light ↔ Dark. Streamlit reruns the page, and the CSS tokens and Altair theme switch together.
  - Settings offers *Light* (default) or *Dark*. "Match system" is not offered, because Streamlit can't reliably read the OS setting from our own code.
  - The choice is saved in the URL (`?theme=dark`), so it survives refreshes and shared links. There is no `localStorage` in Streamlit.
  - Charts and maps re-render with the new theme from cached data, without refetching.
  - Chart downloads (Altair's "…" menu) use the active theme. Switch to Light before exporting for print.
- **Motion:** keep it minimal. A 150ms CSS transition on hover states is fine; there are no chart animations.

---

## 9. Accessibility

- **Contrast:** text meets WCAG AA (4.5:1) in **both** themes. Card titles and KPI values exceed it. Re-check the partisan colors and badge pills against dark surfaces.
- **Color is never the only signal:** deltas carry ▲/▼ arrows, maps have patterned outlines for swing districts, and series are distinguishable by label.
- **Color-blind safety:** the blue-red diverging scale is mostly safe; still check charts with a color-blind simulator before demo day.
- **Keyboard:** Streamlit widgets are keyboard-accessible by default. Our CSS keeps a visible 2px `--accent` focus ring. Map regions are mouse-only, so every map has a companion district/county select box and a ranked table.
- **Charts:** each chart card has a "View as table" `st.expander` showing the same DataFrame in `st.dataframe`.

---

## 10. Responsive Behavior

| Breakpoint | Behavior |
|---|---|
| Wide screens | `layout="wide"`, with content capped at 1440px via CSS |
| Laptop | Same layout; Streamlit columns shrink proportionally |
| Narrow | Streamlit stacks columns automatically and the sidebar collapses behind its toggle. The War Room order becomes Builder → Outcome → Pacing. Laptop/desktop is the primary target |

---

## 11. Implementation in Streamlit + Altair (for Antigravity)

### 11.1 Theming foundation
- **One source of truth for tokens:** `campaign_intel/ui/styles.py` holds a Python dict per theme (`LIGHT`, `DARK`) with every token from §3 and §3.1b. Two things are generated from it:
  1. **CSS:** `inject(theme)` writes a `<style>` block via `st.markdown(..., unsafe_allow_html=True)`. It defines the tokens as CSS variables and restyles Streamlit's containers: page and sidebar background, `st.container(border=True)` cards (radius 16px, `--border`, `--shadow-card`), buttons, inputs, tabs, popovers, and the Vega tooltip (`#vg-tooltip-element`).
  2. **Altair themes:** `campaign_intel/viz/themes.py` registers `campaign_light` and `campaign_dark`. Each sets the font, background (transparent), axis label colors, `--gridline` dashed gridlines, no domain lines, legend styling, and the categorical range (`--dem`, `--rep`, `--neutral-series`, …).
- **Never hard-code hex values** in pages or chart factories. Read them from the token dict.
- **`.streamlit/config.toml`:** set `[theme] base = "light"`, `primaryColor = "#22A06B"`, `backgroundColor = "#F6F7F9"`, `secondaryBackgroundColor = "#FFFFFF"`, `textColor = "#1B1F29"`, and the font. These are the light defaults; dark mode is applied by our CSS on top.
- **Font:** Mulish, loaded via `@import url('https://fonts.googleapis.com/css2?family=Mulish:wght@400;500;600;700;800&display=swap')` in the injected CSS. Also set `"font": "Mulish"` in both Altair themes.
- **Dark mode:**
  - The top-bar toggle sets `st.session_state.theme` and `st.query_params["theme"]`, then calls `st.rerun()`.
  - `inject("dark")` swaps every CSS variable, and `alt.theme.enable("campaign_dark")` swaps the chart theme. Use `alt.themes.enable(...)` on Altair versions before 5.5.
  - Charts render with `st.altair_chart(chart, theme=None, use_container_width=True)` so our theme, not Streamlit's, controls them.
  - **Test every widget type in dark mode.** Streamlit's internal widget styles can resist CSS overrides; fix any unreadable one with a targeted selector.

### 11.2 Component mapping

| Design element (§4) | Streamlit implementation |
|---|---|
| App frame + grid | `st.set_page_config(layout="wide")`; rows via `st.columns([...], gap="medium")`; max width capped by CSS |
| Card | `st.container(border=True)`, restyled by CSS. Card title via `st.markdown("#### …")` + `st.caption(source)` |
| Sidebar navigation | `st.navigation({...}, position="sidebar")` with `st.Page(..., icon=":material/…:")`. Active-item green pill styled via CSS |
| Top bar | `ui.topbar.render_topbar()`: a bordered container with `st.columns`, containing title, scope `st.selectbox`, `st.segmented_control` (District / County), district-type `st.selectbox`, searchable `st.selectbox` (search), `st.popover` (alerts bell with count), freshness chip (HTML pill), `st.toggle` (theme) |
| KPI card | `ui.components.kpi_card(label, value, delta, good_direction, fidelity, band=None, spark=None)`. Renders the label, value, delta pill and fidelity badge with HTML, plus a tiny Altair bar sparkline (4–6 bars, last bar colored). `st.metric` may be used if the custom card proves fiddly, as long as the badge stays |
| Delta pill | HTML span with the pill tokens; ▲/▼ arrow included; color by "good for us," not by sign |
| Fidelity badge | `ui.components.fidelity_badge(kind)`: an HTML pill with a `title=` tooltip explaining it. **A required argument** in `kpi_card()` and `chart_card()` |
| Segmented control | `st.segmented_control` |
| Preset chips | `st.pills` |
| Dropdown | `st.selectbox` |
| Slider | `st.slider` (accent color from `primaryColor`) |
| Data table | `st.dataframe` with `column_config` (`NumberColumn` formats, `ProgressColumn` for shares) |
| Allocation builder | `st.data_editor` with `SelectboxColumn` (unit, channel, audience), `NumberColumn` (week, dollars, step 10,000), `num_rows="dynamic"` |
| Map card | Altair `mark_geoshape` choropleth + `st.altair_chart(on_select="rerun")` for click-to-select; a companion select box for keyboard users |
| Alert item | Rows inside the alerts `st.popover`: icon, headline, relative time, "View ads" button that sets a filter and switches to Opponent Tracker with `st.switch_page` |
| Creative card | Bordered container: advertiser + date, first lines of copy, spend band, theme pills (HTML), `st.link_button("Open in Ad Library", url)` |
| "View as table" | `st.expander` containing `st.dataframe` of the chart's data |
| Sample-data banner | `st.error`-styled full-width HTML banner at the top of the page |
| "Model, not forecast" ribbon | `st.info`-styled HTML ribbon under the War Room title, linking to Methodology via `st.page_link` |
| Breadcrumb | `st.caption` with `›` separators; each crumb is a button that resets `selected_unit` |

**Material icon equivalents for the sidebar (§4.1):**

| Page | Icon |
|---|---|
| Overview | `:material/dashboard:` |
| Audience | `:material/groups:` |
| Opponent Tracker | `:material/my_location:` |
| Electorate | `:material/how_to_vote:` |
| War Room | `:material/strategy:` (fallback `:material/military_tech:`) |
| Methodology | `:material/menu_book:` |
| Settings | `:material/settings:` |

### 11.3 Chart mapping (§5 styles in Altair)

All charts come from factory functions in `campaign_intel/viz/charts.py`. Every encoding is explicitly typed (`:Q`, `:N`, `:O`, `:T`), every chart has a tooltip, and every x/y chart calls `.interactive()`.

| Style | Altair recipe |
|---|---|
| Smooth area with gradient | `mark_area(interpolate="monotone", line={"color": c, "strokeWidth": 2}, color=alt.Gradient(gradient="linear", stops=[alt.GradientStop(color=c, offset=0), alt.GradientStop(color="transparent", offset=1)], x1=1, x2=1, y1=1, y2=0))` |
| Range band + midpoint | `mark_area(opacity=0.15)` with `y="low:Q", y2="high:Q"`, layered under `mark_line(interpolate="monotone")` on `mid:Q` |
| Hover guide + point | A `alt.selection_point(on="pointerover", nearest=True, fields=["week_start"], empty=False)` driving a `mark_rule` and a white-filled `mark_point`, layered on the line |
| Grouped bars | `mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6)` with `xOffset="series:N"`; strong and soft variants of one color |
| Donut | `mark_arc(innerRadius=r*0.7, stroke=surface, strokeWidth=2)` with `theta="share:Q"`, `color="platform:N"`; legend on the right |
| Heatmap | `mark_rect(cornerRadius=3)` with `x="age:O"`, `y="theme:N"`, `color=alt.Color("pct:Q", scale=alt.Scale(scheme=…))`; for the Gap view, a diverging scale centered on 0 |
| Error bars (survey CIs) | `mark_errorbar` with `y="ci_low:Q", y2="ci_high:Q"`, layered on the bars |
| Histogram (Monte Carlo) | Pre-binned DataFrame → `mark_bar` with `x="bin_start:Q", x2="bin_end:Q", y="count:Q"`; bars left of 0 in `--rep-soft`, right in `--dem-soft`; `mark_rule` at x=0 |
| Win-probability bar | Horizontal `mark_bar` from 0 to the plan's win probability, a `mark_rule` for the baseline, and a `mark_errorbar` for the interval |
| Choropleth | `alt.Chart(alt.Data(values=features)).mark_geoshape(stroke=surface, strokeWidth=1)`. Metrics are merged into each feature's `properties` beforehand; encode `color="properties.margin:Q"` with a diverging scale (domain centered on 0), tooltip on `properties.name:N` and the metric. Swing districts are outlined by a second `mark_geoshape(filled=False, stroke=swing)` layer |
| Sparkline (KPI) | Tiny `mark_bar` with no axes, height ~28px, last bar colored |

**Altair limits we accept:**
- Maps don't support scroll-zoom or pan; drill-down provides the zoom.
- Hover sync works only inside one compound chart.
- Charts receive pre-aggregated data under 5,000 rows; the row limit stays on.

### 11.4 Rules for Antigravity
- Build `styles.py`, `viz/themes.py`, `viz/charts.py`, and `ui/components.py` **first**, then compose pages from them. Pages contain layout only.
- The fidelity badge is mandatory: `kpi_card()` and `chart_card()` raise `TypeError` if `fidelity` is missing.
- Verify both themes on every page before marking it done.
