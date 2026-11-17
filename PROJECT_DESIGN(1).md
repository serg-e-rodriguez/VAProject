# Project Design Doc — NC Campaign Ad Intelligence & War Room

**Status:** Draft v2 (Streamlit + Altair) · **Date:** 2026-10-24
**Context:** Academic project (Visual Analytics). Use case: *The Midterms: Political & Issue Advertising.*
**Client persona:** A Democratic nominee's campaign in North Carolina, deciding where to spend its remaining **$2M**.

**Companion docs**
- `GEMINI.md`: project coding standards. It is binding: `uv` only, Python 3.12+, Streamlit, Altair, and Jupyter via `ipykernel`.
- `UI_Design.md`: visuals, tokens, components, and page layouts. Its §11 maps every component to Streamlit and Altair.

This doc covers *what* to build and *how the data and model work*.

---

## 1. Goals, Non-Goals, Assumptions

### 1.1 Goals
1. **Show the ad landscape.** Show where political ad money is going in NC (Google + Meta), by geography, platform, theme, and audience.
2. **Show who sees what.** Connect ad delivery (who sees which messages) to voter reality (who uses which platforms and cares about which issues).
3. **Track the opponent.** Show where the opponent and allies spend, what they say, and what's new.
4. **Map the electorate.** Show registration universes, turnout history, and early-vote progress by district and county.
5. **War Room (main feature).** Let the team simulate allocations of the $2M across geography × channel × audience × week. Show how each plan changes the projected margin and win probability, with honest uncertainty, and recommend the best next dollar.

### 1.2 Non-goals
- A real forecast. The War Room is an **explicit, assumption-driven model**, labeled "Model, not forecast."
- Individual-level voter targeting or display. Voter-file data is **aggregated before it reaches the app**.
- TV spend tracking. This is out of scope for v1; see §13 for a stretch idea.
- Auth, multi-user accounts, a separate backend API, and mobile apps.

### 1.3 Working assumptions (agreed)
| Topic | Decision |
|---|---|
| Tech stack | **Streamlit** app + **Altair** charts, Python **3.12+**, managed with **`uv`** (never `pip`), Jupyter notebooks for exploration (per `GEMINI.md`) |
| Calendar | Treat the election as far enough away to plan multi-week pacing (academic framing). The "weeks to Election Day" setting is user-adjustable. |
| Candidate | Generic Democratic nominee; no specific candidate. |
| State | North Carolina. |
| Default scope | **Statewide** race, **District** view, **Congressional** districts. |
| District types | Selectable: Congressional (14), State Senate (50), State House (120). |
| Geography toggle | District (default) ↔ County (100). |
| Meta access | **Live Ad Library API** (identity-verified token). |
| Win probability | Assumption-driven, with sliders, presets, and Monte Carlo ranges. |
| NCSBE data | Included (registration, history, precinct results, absentee/One-Stop). |
| Theme | Light (default) and Dark, user-toggleable. |

---

## 2. Users & Key Questions

**Primary users:** campaign budget and media strategists.

| Page | Question it answers |
|---|---|
| Overview | Where is the money going, and where are we out-spent relative to how close the race is? |
| Audience Intelligence | Which demographics see which messages, and where are the gaps between what they see and what they care about? |
| Opponent Tracker | What is the other side spending, where, on what message, and what changed recently? |
| Electorate | How many persuadable and mobilizable voters are in each place, and how many have already voted? |
| War Room | If we spend $X here, on this channel, for this audience, in these weeks, how much does it move us, and what's the best plan? |
| Methodology | What are the data sources, what is modeled, and what are the limits? |

---

## 3. System Architecture

```
┌─────────────────────────── INGESTION (uv run python -m …) ───────────────────────────┐
│ Google BQ public ──► SQL transforms                                                    │
│ Meta Ad Library API ──► daily snapshot job                                             │
│ NCSBE files (registration, history, precinct results, absentee) ──► aggregators        │
│ MEDSL 2022 Senate, CCES 2024 (UNC) ──► one-time loaders                                │
│ Reference: district shapes → simplified GeoJSON, county↔DMA crosswalk, seeds           │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            ▼
                   BigQuery project visualanalytics-509422
                   datasets: raw_* → stg → mart
                                            │
                     (optional) export_snapshot → data/cache/*.parquet
                                            │
┌─────────────────────────────── STREAMLIT APP ─────────────────────────────────────────┐
│ app.py (st.navigation)                                                                  │
│   app_pages/*.py  ── UI layout only                                                     │
│        │ calls                                                                          │
│   campaign_intel.data      cached loaders (st.cache_data) → pandas DataFrames           │
│   campaign_intel.model     War Room engine, optimizer, scenarios (pure Python/NumPy)    │
│   campaign_intel.viz       Altair chart factories + light/dark Altair themes            │
│   campaign_intel.ui        top bar, KPI cards, badges, CSS tokens                       │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

**Key architectural rule (from `GEMINI.md`):** data processing lives in the `campaign_intel` package, and the Streamlit pages only lay out the UI.
- Every page calls package functions that return DataFrames or Altair charts.
- No SQL, pandas transforms, or model math appear inside page files.
- The same package functions are imported by notebooks and tests.

### 3.1 Tech stack
| Layer | Choice | Notes |
|---|---|---|
| Package / env manager | `uv` | `uv init --bare`, `uv venv`, `uv add`, `uv run`. Never `pip`. |
| Language | Python 3.12+ | Pinned in `.python-version` and `requires-python` |
| App framework | Streamlit (≥ 1.40) | Uses `st.navigation`/`st.Page`, `st.fragment`, `st.segmented_control`, `st.data_editor`, `st.altair_chart(on_select=…)` |
| Charts & maps | Altair 5 (Vega-Lite) | All charts and choropleths (`mark_geoshape`) |
| Warehouse | BigQuery (`visualanalytics-509422`) | `google-cloud-bigquery` + `db-dtypes`; use `to_dataframe(create_bqstorage_client=False)` |
| Data wrangling | pandas, NumPy, PyArrow | |
| Model | NumPy (vectorized Monte Carlo + greedy optimizer) | |
| Ingestion HTTP | `requests` | Meta API, NCSBE downloads |
| Config | `python-dotenv`, `pyyaml` | `.env` for secrets, YAML for seeds and assumptions |
| Scenario storage | SQLite (stdlib `sqlite3`) at `data/scenarios.db` | Simple and local; optional BigQuery table later |
| Notebooks | Jupyter via `ipykernel` (dev dependency) | Kernel set to the project's `.venv` |
| Geo prep (one-time) | `geopandas` + `pyogrio` (optional `geo` group) | Converts shapefiles to simplified GeoJSON committed to `data/geo/` |
| Tests / lint | `pytest`, `ruff` (dev) | |

### 3.2 Repository layout
```
.
├── pyproject.toml
├── uv.lock
├── .python-version                 # 3.12
├── .env.example                    # META_ACCESS_TOKEN, GCP_PROJECT, … (never commit .env)
├── .streamlit/
│   └── config.toml                 # base theme (light), fonts, layout
├── app.py                          # entry point: st.navigation + shared top bar
├── app_pages/                      # UI layout only (one file per page)
│   ├── overview.py
│   ├── audience.py
│   ├── opponent.py
│   ├── electorate.py
│   ├── war_room.py
│   ├── methodology.py
│   └── settings.py
├── src/campaign_intel/
│   ├── __init__.py
│   ├── config.py                   # settings, env loading, constants
│   ├── state.py                    # session_state keys + defaults + query-param sync
│   ├── data/
│   │   ├── bq.py                   # BigQuery client (st.cache_resource)
│   │   ├── loaders.py              # cached query functions (st.cache_data) → DataFrames
│   │   └── snapshot.py             # export/read local Parquet snapshot
│   ├── ingest/
│   │   ├── google_bq.py
│   │   ├── meta_snapshot.py
│   │   ├── ncsbe_registration.py
│   │   ├── ncsbe_history.py
│   │   ├── ncsbe_results.py
│   │   ├── ncsbe_absentee.py
│   │   └── reference.py
│   ├── processing/
│   │   ├── bands.py                # spend/impression band parsing + aggregation
│   │   ├── themes.py               # message-theme classification
│   │   ├── fundraising.py          # ActBlue/WinRed tagging
│   │   ├── crosswalk.py            # precinct → county/CD/SD/HD
│   │   ├── allocation.py           # modeled ad allocation to districts
│   │   └── survey.py               # weighted CCES estimates + CIs
│   ├── model/
│   │   ├── assumptions.py          # dataclasses + YAML loading + presets
│   │   ├── engine.py               # simulate()
│   │   ├── optimizer.py            # optimize()
│   │   └── scenarios.py            # SQLite CRUD
│   ├── viz/
│   │   ├── themes.py               # registers Altair light/dark themes from tokens
│   │   ├── charts.py               # area_with_band(), grouped_bar(), donut(), heatmap(), …
│   │   └── maps.py                 # choropleth(), drilldown helpers
│   └── ui/
│       ├── styles.py               # CSS tokens (light/dark) injected via st.markdown
│       ├── topbar.py               # render_topbar()
│       └── components.py           # kpi_card(), chart_card(), fidelity_badge(), alert_item()
├── sql/
│   ├── stg/
│   └── mart/
├── seeds/
│   ├── advertiser_sides.csv
│   ├── theme_keywords.yaml
│   └── assumptions_default.yaml
├── data/
│   ├── geo/                        # simplified GeoJSON (committed, small)
│   ├── cache/                      # Parquet snapshot (git-ignored)
│   └── scenarios.db                # git-ignored
├── notebooks/
│   ├── 01_google_bq_eda.ipynb
│   ├── 02_meta_field_check.ipynb
│   ├── 03_ncsbe_crosswalk.ipynb
│   ├── 04_cces_weighting.ipynb
│   └── 05_model_sanity.ipynb
├── tests/
└── docs/
    ├── PROJECT_DESIGN.md
    ├── UI_Design.md
    └── GEMINI.md
```

Pages live in `app_pages/` rather than `pages/` so Streamlit's automatic multipage detection never conflicts with `st.navigation`.

### 3.3 `pyproject.toml`

```toml
[project]
name = "nc-campaign-war-room"
version = "0.1.0"
description = "NC political ad intelligence dashboard and War Room budget simulator (Streamlit + Altair)"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "streamlit>=1.40",
    "altair>=5.4",
    "pandas>=2.2",
    "numpy>=2.0",
    "pyarrow>=17.0",
    "google-cloud-bigquery>=3.25",
    "db-dtypes>=1.3",
    "requests>=2.32",
    "python-dotenv>=1.0",
    "pyyaml>=6.0",
]

[dependency-groups]
dev = [
    "ipykernel>=6.29",
    "pytest>=8.3",
    "ruff>=0.6",
]
geo = [
    "geopandas>=1.0",
    "pyogrio>=0.9",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/campaign_intel"]

[tool.uv]
default-groups = ["dev"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

The `[build-system]` and `src/` layout let `uv` install `campaign_intel` into the venv in editable mode. That makes `import campaign_intel` work identically from Streamlit, notebooks, and tests, with no `sys.path` hacks.

### 3.4 Setup sequence (for the team, per `GEMINI.md`)
1. **Check `uv`:** `uv --version`.
   - If it's missing, install it. On Mac/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`. On Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`.
   - If it's present, update it: `uv self update`.
2. **Initialize the project:** `uv init --bare`. If `--bare` fails, run `uv init` and delete `hello.py`. Then replace the generated `pyproject.toml` with §3.3.
3. **Create the venv:** `uv venv`.
4. **Install core packages:** `uv add streamlit altair pandas`, then `uv add numpy pyarrow google-cloud-bigquery db-dtypes requests python-dotenv pyyaml`.
5. **Install dev and optional packages:**
   - Dev tools: `uv add --dev ipykernel pytest ruff`.
   - One-time geo prep only: `uv add --group geo geopandas pyogrio`.
6. **Install the project:** `uv sync`, which installs `campaign_intel` in editable mode.
7. **Point the notebooks at the venv.** In Antigravity/Jupyter, select the `.venv` interpreter created by `uv` as the notebook kernel.
8. **Authenticate to Google Cloud:** `gcloud auth application-default login`. Then copy `.env.example` to `.env` and fill in the values.
9. **Run the app:** `uv run streamlit run app.py`.

**Other entry points**
| Task | Command |
|---|---|
| Daily Meta snapshot | `uv run python -m campaign_intel.ingest.meta_snapshot` |
| Google transforms | `uv run python -m campaign_intel.ingest.google_bq` |
| NCSBE loads | `uv run python -m campaign_intel.ingest.ncsbe_registration` (and the other `ncsbe_*` modules) |
| Export a Parquet snapshot for an offline demo | `uv run python -m campaign_intel.data.snapshot export` |
| Tests | `uv run pytest` |
| Lint | `uv run ruff check .` |

---

## 4. Data Sources

| # | Source | Access | Native grain | Refresh | Used for |
|---|---|---|---|---|---|
| 1 | Google Political Ads (`bigquery-public-data.google_political_ads`) | Public BigQuery | Ad, advertiser, advertiser×state, advertiser×week, congressional district (aggregate) | Daily (Google), weekly derived | Spend landscape, pacing, formats, targeting |
| 2 | Meta Ad Library API `/ads_archive` (`ad_type=POLITICAL_AND_ISSUE_ADS`) | Verified token | Ad (snapshot) | Daily snapshot | Creatives, themes, demographic and regional delivery, opponent tracking |
| 3 | NCSBE voter registration (statewide) | Public download | Voter → **aggregated** to precinct × party × age × race × gender | Weekly | Universes, precinct→district assignment |
| 4 | NCSBE voter history | Public download | Voter × election → **aggregated** | Per election | Turnout propensity, vote-method splits |
| 5 | NCSBE precinct-sorted results (2022, 2024) | Public download | Precinct × contest × candidate × vote method | One-time | Baselines on current maps |
| 6 | NCSBE absentee / One-Stop files | Public download | Ballot → **aggregated** | Daily during voting | Early-vote tracker |
| 7 | MEDSL 2022 U.S. Senate county returns (`senate_2022.csv`) | CSV | County × candidate × mode | One-time | Cross-check of the NCSBE baseline |
| 8 | CCES 2024 UNC module (`CCES24_UNC_OUTPUT.csv`) | CSV | Respondent (weighted) | One-time | Platform use and issue priorities by demographic (national benchmarks) |
| 9 | District shapes (CD, SD, HD) and county shapes | NCSBE / NCGA / Census | Polygon → simplified GeoJSON | One-time (verify current maps) | Maps |
| 10 | County ↔ DMA crosswalk | Public compiled list | County → DMA | One-time | DMA rollups (Charlotte DMA crosses into SC) |
| 11 | `advertiser_sides` seed (manual) | Team-curated CSV | Advertiser/Page → side | As needed | Us vs. opponent vs. allies |

> **Verify before building:** the current congressional map (including the 2025 redraw of CD 1 and CD 3), the current State Senate and State House maps, and that the voter file's district fields reflect the 2026 maps.

### 4.1 How the app reads data
- **Live mode (default):** `campaign_intel.data.loaders` queries `mart.*` tables in BigQuery.
  - Each loader is decorated with `@st.cache_data(ttl=600)`.
  - The BigQuery client is created once with `@st.cache_resource`.
- **Snapshot mode (demo safety):** the same loaders read `data/cache/*.parquet`.
  - The snapshot is exported by the snapshot script, and `DATA_MODE=snapshot` in `.env` switches to it.
  - It is **real data frozen at a timestamp**, not sample data. The freshness chip shows the snapshot's `as_of`.
- **Loaders return tidy, pre-aggregated DataFrames** sized for charts. Altair embeds data in the page, so nothing above ~5,000 rows should reach a chart. Aggregate first; don't disable Altair's row limit.

---

## 5. Data Model (BigQuery)

Datasets: `raw_google`, `raw_meta`, `raw_ncsbe`, `raw_ref`, `stg`, `mart`.

### 5.1 Geography backbone (the most important tables)

**`mart.geo_units`**: every unit the app can display.
| Column | Type | Notes |
|---|---|---|
| unit_type | STRING | `state`, `county`, `cd`, `sd`, `hd`, `dma`, `precinct` |
| unit_id | STRING | e.g. `CD12`, `SD18`, `HD104`, `37119` (county FIPS), `MECK-001` |
| name | STRING | Display name |
| map_version | STRING | e.g. `CD-2025`, `SD-current`, `HD-current` |

Geometry for the maps is **not** read from BigQuery at runtime. It lives as simplified GeoJSON in `data/geo/{county,cd,sd,hd}.geojson`, keyed by `unit_id`. Simplify to under ~1 MB per file so Altair renders quickly.

**`mart.precinct_crosswalk`**: precinct → county and each district type, weighted.
| Column | Type | Notes |
|---|---|---|
| precinct_id | STRING | County code + precinct code |
| county_fips | STRING | 5-char, zero-padded |
| unit_type | STRING | `cd`, `sd`, `hd` |
| unit_id | STRING | |
| weight | FLOAT64 | Share of the precinct's registered voters in this district. Usually 1.0; below 1 for split precincts |

Built from the voter file: group voters by (precinct, district field) and normalize. **All district-level numbers are produced by joining precinct facts through this table.** County numbers are an exact precinct → county rollup. This guarantees District and County views sum to the same statewide totals.

### 5.2 Election & electorate facts
- **`mart.baseline_results`**: (election, contest, precinct_id, party, vote_method, votes), from NCSBE precinct results. 2022 U.S. Senate is the default baseline; 2024 President and 2020 U.S. Senate are optional.
- **`mart.electorate_agg`**: (precinct_id, party_reg, age_bucket, race, gender, turnout_2022_flag, turnout_propensity_bucket, n_voters).
- **`mart.vote_method_history`**: (precinct_id, election, method, ballots).
- **`mart.early_vote_daily`**: (date, precinct_id, party_reg, age_bucket, method, ballots).
- **`mart.unit_rollup_{county,cd,sd,hd}`**: materialized rollups per unit type, so the app never aggregates precinct data at runtime.

### 5.3 Google facts
- **`stg.google_creatives_nc`**: `creative_stats` filtered to US 2024+, with:
  - `nc_targeted` = geo string contains North Carolina, NC cities/counties, or NC ZIPs
  - `national_targeted` = United States only
  - parsed sub-state targets (`geo_targets_parsed` ARRAY<STRUCT<type, name, unit_id>>)
  - spend min/max and impression min/max parsed to numbers
  - `spend_mid`, with `NULL` upper bounds kept as open-ended
- **`mart.google_advertiser_state_lifetime`**: from `advertiser_geo_spend`. **Labeled lifetime (since 2018); no date dimension.**
- **`mart.google_weekly_nc_specific`**: weekly spend only for advertisers whose state spend is ≥ 90% NC (configurable). These are the only clean NC time series from Google.
- **`mart.google_cd_spend`**: from `geo_spend` (CD level, no advertiser). Check its CD names against the 2025 map for CD 1 and CD 3.

### 5.4 Meta facts (snapshot-keyed, per `GPTReadme.md` §3)
- `raw_meta.ad_library_raw` (ingestion_id, fetched_at, api_version, query_context JSON, archive_ad_id, payload JSON)
- `stg.meta_ads` (one row per ad per snapshot; spend and impression bounds; byline; page; dates; creative arrays; link captions; platforms)
- `stg.meta_demographics` (ad, fetched_at, age, gender, pct)
- `stg.meta_regions` (ad, fetched_at, region, pct)
- `mart.meta_ads_latest` (deduplicated latest snapshot per ad) plus enrichments:
  - `side` (from `advertiser_sides`)
  - `is_fundraising` (link caption matches `actblue.com|winred.com|…` or a donate CTA)
  - `themes` ARRAY<STRING> (§6.2)
  - `nc_share` = `delivery_by_region` pct for North Carolina
  - `nc_spend_est_low/mid/high` = spend bounds × nc_share (**Modeled**)
- `mart.meta_daily_delta`: snapshot diffs, giving new ads per day and changes in spend bands. This is how Meta gets a time series.
- `mart.alerts`: generated alert rows (§10).

### 5.5 Survey facts
- **`mart.cces_benchmarks`**: precomputed **weighted** (`teamweight`) estimates with 95% CIs for platform use × age, platform use × gender, issue position × demographic, and news interest × demographic. Store `n_unweighted` and suppress cells with n < 30.

### 5.6 Seeds
- **`seeds/advertiser_sides.csv`**: `platform, advertiser_or_page_id, name, side (us|opponent|ally_us|ally_opp|neutral), scope (statewide|cd|sd|hd), unit_id, notes`.
- **`seeds/theme_keywords.yaml`**: theme → keyword/regex list.
- **`seeds/assumptions_default.yaml`**: model defaults and ranges (§7.4).

---

## 6. Processing Logic

### 6.1 Spend & impression bands
- Keep `low`, `high`, and `mid` for every banded value; never drop the bounds.
- Open-ended top tiers: `high = NULL`, `mid = low × 1.5` (configurable), and flag `open_ended=true`. The UI shows "≥ $low."
- Aggregations sum low, mid, and high separately and display them as a band. In Altair, the band is a `mark_area` from `y=low` to `y2=high` behind a `mark_line` for `mid`.

### 6.2 Theme classification (Meta creative text)
1. A keyword/regex pass from `theme_keywords.yaml`. Themes: economy/cost of living, abortion/reproductive rights, healthcare, education, immigration, crime/public safety, democracy/elections, guns, energy/climate, veterans, character/attack, fundraising, GOTV/voting info.
2. Optional LLM pass for ads with no keyword hit (batch, cached by ad ID). Store `theme_source` as `keyword` or `llm`.
3. Exclude fundraising and GOTV ads from persuasion-message analysis; show them separately.

### 6.3 Allocating ad data to districts (always **Modeled**)
- **Meta:** NC spend estimate × each unit's share of NC registered voters (default). An alternative weighting by matching demographic delivery to unit demographics is a stretch goal.
- **Google:** if `geo_targets_parsed` resolves to sub-state units, allocate to those units. Otherwise allocate the NC portion by registered-voter share.
- **CD-level `geo_spend`** is shown as **Observed** in CD view only.

### 6.4 Data-quality fixes carried from the review
1. Google NC state spend is **lifetime**; never present it as 2024+.
2. NC ad counts from regex miss nationally targeted ads; show both "NC-targeted" and "national incl. NC."
3. `advertiser_weekly_spend` is national; NC trends come only from NC-specific advertisers.
4. Rename mislabeled columns: the `AR…` values are Google advertiser IDs, not FEC IDs.
5. Gender targeting **is** present in Google US election ads; don't claim otherwise.
6. Meta `target_*` fields: test them; if empty for US ads, hide that table.
7. Pin a currently supported Graph API version. The Ad Library API needs identity verification plus a token, not `ads_management` and similar permissions.
8. Compute vote-method shares from votes, not row counts.
9. MEDSL `totalvotes` is statewide; compute county totals by summing `candidatevotes`.
10. Cast `county_fips` to a 5-char string; drop write-ins in margin calculations.
11. Weight all CCES figures, show CIs, and treat vote/turnout as self-reported. Confirm the platform variable mapping against the official codebook.
12. **No silent fallback data.** If a live source fails, use the last Parquet snapshot with a stale badge, or show sample data with the full-width banner.

---

## 7. War Room Model Specification

The model lives in `campaign_intel.model`. It is pure Python/NumPy with no Streamlit imports, so notebooks and tests can call it directly.

### 7.1 Decision variables
An **allocation** is a pandas DataFrame of line items with columns:
`unit_id, channel, audience, week, dollars`

- `unit_id`: a unit of the current district type (or county in County view).
- `channel ∈ {meta, youtube, search, display, ctv}`.
- `audience ∈ {persuasion, mobilization}`.
- `week ∈ 1..W`, where W = weeks to Election Day (user input; default 8).
- **Constraint:** Σ dollars ≤ budget (default $2,000,000).

### 7.2 Target universes (from `mart.unit_rollup_*`)
- **Persuasion universe P_u:** unaffiliated plus soft-partisan registrants (default: unaffiliated, any age), adjustable in Assumptions.
- **Mobilization universe M_u:** Democratic-registered plus Dem-leaning unaffiliated with low turnout propensity (didn't vote in the 2022 midterm), **minus those who have already voted** when early-vote data exists.
- **Dem share among mobilization targets d_u:** default 0.85 for registered Democrats, configurable.

### 7.3 Per line-item mechanics
For one line item with dollars `x` in unit `u`, channel `c`, audience `a`, week `w`:

1. **Impressions:** `I = x / CPM_c × 1000`
2. **Effective frequency:** `f = (I + I_prior) / U_ua`, where `U_ua` is the universe size and `I_prior` is our impressions already allocated to the same unit and audience. The saturation curve is computed over the combined total.
3. **Reach (saturating):** `R = U_ua × (1 − e^(−k_c × f))`. Marginal reach is the increment from adding this line item.
4. **Opponent pressure (optional):** multiply the effect by `1 / (1 + λ × opp_share_u)`, where `opp_share_u` is the opponent's share of voice in the unit.
5. **Decay:** effects decay before Election Day with a weekly retention ρ. Weight `= ρ^(W − w)`, so late money counts more.
6. **Net votes:**
   - Persuasion: `ΔV = R_new × p_c × decay`, where `p_c` is the net margin shift per reached persuadable voter (votes).
   - Mobilization: `ΔV = R_new × t_c × (2d_u − 1) × decay`, where `t_c` is the turnout lift per reached target.

### 7.4 Default assumptions (all editable; shown on the Methodology page)

| Parameter | Default | Range (Monte Carlo) | Basis |
|---|---|---|---|
| CPM Meta | from data* | ±40% | *median of NC Meta ads (spend_mid / impressions_mid × 1000) |
| CPM YouTube / Display / Search | from data* | ±40% | Same, from Google NC creatives by `ad_type` |
| CPM CTV | $35 | $25–$50 | Assumption |
| Saturation k_c | 0.8 | 0.5–1.2 | Assumption |
| Persuasion p (net votes per reached voter) | 0.002 | 0–0.006 | Low by design; persuasion effects in general elections are close to zero |
| Turnout lift t | 0.003 | 0–0.01 | Low by design; field experiments with digital ads find very small turnout effects |
| Weekly retention ρ | 0.6 | 0.4–0.8 | Ad effects decay quickly |
| Opponent dampening λ | 0 (off) | 0–1 | Optional |
| Polling/baseline error σ (statewide margin) | 3.5 pts | fixed | Assumption |
| District-level extra error σ_d | 2.5 pts | fixed | Assumption |
| Environment shift (vs. baseline) | 0 pts | user slider −10 to +10 | User sets the national environment |

**Presets:**
- **Conservative:** low effects, high CPM.
- **Optimistic:** high effects, low CPM.
- **Mobilization-heavy:** a starting allocation, not a parameter set.

Citations for the defaults go on the Methodology page; the team adds the final references.

### 7.5 Baseline and outcome
- **Baseline margin per unit:** from `baseline_results` for the selected baseline election, plus the environment shift.
- **Expected turnout:** 2022 midterm turnout per unit, with an adjustable multiplier.
- **Projected margin (votes):** baseline margin votes + Σ ΔV.
- **Statewide scope:** sum over all units. The win condition is statewide margin > 0.
- **District-race scope:** the chosen unit only. The win condition is unit margin > 0.
- **Chamber control (legislative types):** count units with margin > 0 against the majority threshold (26/50 Senate, 61/120 House).

### 7.6 Monte Carlo
- N = 5,000 draws (configurable). Each draw samples the uncertain parameters from triangular distributions over the ranges in §7.4, plus a shared statewide error ~ N(0, σ) and independent unit errors ~ N(0, σ_d).
- **Outputs:**
  - Win probability with an 80% interval, computed by bootstrapping over parameter draws.
  - Margin distribution, binned in NumPy to about 50 bins **before** charting.
  - Expected ΔV by unit and channel.
  - Cost per net vote.
- **Always compute the no-spend baseline in the same run** so the UI can show "46% → 49%."

### 7.7 Optimizer ("Auto-optimize next $")
- Greedy marginal allocation in $10k increments (configurable).
- At each step, evaluate the expected ΔV (or Δwin probability, user-selectable) of adding one increment to every feasible (unit, channel, audience, week). Pick the best one and repeat until the budget is spent or no step adds value.
- **Constraints:**
  - per-unit/channel/week caps (default: no single line item above 3× universe impressions per week)
  - optional channel minimums and maximums
  - optional locked line items the user pinned
- **Output:** the recommended allocation plus a diff DataFrame against the current plan, each row with its marginal value.
- **Performance target:** < 2s for 14 units; < 5s for 120 units, using expected-value evaluation during the greedy loop and a full Monte Carlo only on the final plan.

### 7.8 Scenarios
- Save scenarios with: name, scope, district type, assumptions, allocation, and results snapshot.
- Compare 2–3 scenarios side by side (KPIs, win probability band, allocation by unit and channel).
- **Storage:** SQLite at `data/scenarios.db`, one table `scenarios(id, name, created_at, payload_json)`.

### 7.9 Module interfaces

```python
# campaign_intel/model/assumptions.py
@dataclass(frozen=True)
class Assumptions:
    cpm: dict[str, tuple[float, float, float]]   # channel -> (low, mode, high)
    saturation_k: tuple[float, float, float]
    persuasion_p: tuple[float, float, float]
    turnout_t: tuple[float, float, float]
    retention_rho: tuple[float, float, float]
    opp_lambda: float
    sigma_state: float
    sigma_unit: float
    env_shift_pts: float

def load_defaults(path: Path) -> Assumptions: ...
def apply_preset(a: Assumptions, name: Literal["conservative", "optimistic"]) -> Assumptions: ...

# campaign_intel/model/engine.py
@dataclass(frozen=True)
class RaceContext:
    scope: Literal["statewide", "district"]
    unit_type: Literal["cd", "sd", "hd", "county"]
    target_unit: str | None
    weeks: int
    budget: float
    units: pd.DataFrame        # unit_id, baseline_margin_votes, turnout, P_u, M_u, d_u, opp_share

@dataclass(frozen=True)
class SimulationResult:
    win_prob: float
    win_prob_interval: tuple[float, float]
    baseline_win_prob: float
    margin_hist: pd.DataFrame   # bin_start, bin_end, count (pre-binned for Altair)
    delta_votes_by_unit: pd.DataFrame
    delta_votes_by_channel: pd.DataFrame
    cost_per_net_vote: float

def simulate(allocation: pd.DataFrame, ctx: RaceContext, a: Assumptions,
             n_draws: int = 5000, seed: int = 42) -> SimulationResult: ...

# campaign_intel/model/optimizer.py
def optimize(current: pd.DataFrame, ctx: RaceContext, a: Assumptions,
             step: float = 10_000, objective: Literal["votes", "win_prob"] = "votes",
             locks: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (recommended_allocation, diff)."""
```

---

## 8. Streamlit Application Design

Visual details live in `UI_Design.md`, which maps each component to Streamlit/Altair in its §11. This section covers app behavior.

### 8.1 Entry point and navigation
- `app.py` runs, in order:
  1. `st.set_page_config(layout="wide", page_title=…, page_icon=…)`
  2. Inject the CSS tokens (`ui.styles.inject(theme)`).
  3. Register and enable the Altair theme (`viz.themes.enable(theme)`).
  4. Render the top bar.
  5. Build `st.navigation([...])` with `st.Page` entries (with Material icons), and call `.run()`.
- The navigation lives in the sidebar, grouped as "Analyze" (Overview, Audience, Opponent, Electorate), "Plan" (War Room), and "Reference" (Methodology, Settings).

### 8.2 Global state (`campaign_intel.state`)
| Key | Default | Mirrored to URL (`st.query_params`) |
|---|---|---|
| `scope` | `statewide` | yes |
| `target_unit` | `None` | yes |
| `unit_type` | `cd` | yes |
| `geo_mode` | `district` | yes |
| `theme` | `light` | yes (this is how the theme choice persists) |
| `date_range` | last 8 weeks | yes |
| `selected_unit` | `None` (set by map clicks) | yes |
| `allocation` | empty DataFrame | no |
| `assumptions` | defaults | no |
| `seen_alert_ids` | empty set | no |

`state.init()` runs at the top of `app.py`. It reads the query params, fills in the defaults, and writes changes back, so any view is a shareable link.

### 8.3 Interaction patterns
- **Cross-filtering:** maps and bar charts use `st.altair_chart(chart, on_select="rerun", key=…)` with an Altair point selection on `unit_id`. The selection updates `selected_unit`, and other cards filter on it.
- **Drill-down:** clicking a district sets `selected_unit`. The map card then renders that district's counties (zoomed via the projection's fit to those features) with a breadcrumb.
- **War Room responsiveness:**
  - The allocation builder and outcome panel sit inside an `@st.fragment`, so edits rerun only that section, not the whole page.
  - `simulate()` is wrapped in `st.cache_data`, keyed on a hash of the allocation and assumptions.
- **Allocation builder:**
  - The main editor is `st.data_editor` over the allocation DataFrame (columns: unit, channel, audience, week, dollars). It uses `column_config` (`SelectboxColumn`, `NumberColumn(step=10_000, format="$%d")`) and `num_rows="dynamic"`.
  - Quick channel-total sliders above it rescale the rows proportionally.
- **Optimizer:** `st.button("Auto-optimize next $")` runs `optimize()` and shows the diff in `st.dataframe`. **Accept all** and **Accept selected** (via the dataframe's row selection) write the changes into `allocation`.
- **Alerts:** a top-bar `st.popover` lists `mart.alerts` rows newer than `seen_alert_ids`. Opening it marks them seen.
- **Theme toggle:** a top-bar `st.toggle` sets `theme`. It updates `st.query_params` and calls `st.rerun()`. CSS tokens and the Altair theme switch together.

### 8.4 Altair rules (from `GEMINI.md`, applied project-wide)
- **Interactivity:** every chart has tooltips. All x/y charts call `.interactive()` for zoom and pan. Time series bind the x axis (`bind_y=False`) so zooming stays readable.
  - **Exception:** `mark_geoshape` maps can't zoom or pan with scale bindings. Maps get click-to-drill-down zoom (§8.3) instead, and the code comments say so.
- **Strict typing:** every encoding uses an explicit type (`:Q`, `:N`, `:O`, `:T`), e.g. `alt.X("week_start:T")`, `alt.Color("side:N")`.
- **Theme:** charts use our registered `campaign_light` and `campaign_dark` Altair themes, built from the `UI_Design.md` tokens, and render with `st.altair_chart(chart, theme=None, use_container_width=True)`.
  - This is a deliberate departure from the default `theme="streamlit"`: we need the reserved partisan colors and a theme that switches with the app's toggle.
  - Any chart that doesn't need partisan colors may use `theme="streamlit"`.
- **Chart factories:** all charts come from `campaign_intel.viz.charts`, e.g. `area_with_band()`, `grouped_bar()`, `donut()`, `heatmap()`, `histogram()`, `choropleth()`. Pages never build raw Altair specs.
- **Data size:** charts receive pre-aggregated DataFrames under 5,000 rows. GeoJSON is simplified.

### 8.5 Notebooks
- **One notebook per data source**, plus one for model sanity checks (see the layout in §3.2). Notebooks are where the team verifies the open items in §14.
- **Executable cell by cell:** no hidden global state. Each notebook's first cell does all imports from `campaign_intel` and loads its data via package functions.
- **Kernel:** the `.venv` interpreter created by `uv`.

---

## 9. Page Specifications (data → component)

| Page | KPIs (`kpi_card`) | Hero | Supporting |
|---|---|---|---|
| Overview | Total NC ad spend (band), our share of voice, opponent spend last 7d, active ads us vs. them | `choropleth(metric="margin" \| "ad_pressure")` + top-5 battleground list | `area_with_band()` weekly spend us vs. opp; `donut()` platform mix |
| Audience | Top-reached age group, gender split, fundraising ads excluded, themes detected | `heatmap()` theme × age×gender with Us/Opp/Gap `segmented_control` | `grouped_bar()` platform use by age with CI `mark_errorbar`; issue priorities; message-gap cards |
| Opponent | Opp spend 7/30d, new creatives 48h, top theme, top district (modeled) | `area_with_band()` share of voice | Alert list; creative cards (text + "Open in Ad Library" `st.link_button`); advertiser `st.dataframe` |
| Electorate | Registered in scope, unaffiliated share, low-propensity Dems, early votes cast | `choropleth(metric=universe)` | Vote-method `grouped_bar()`; universe table |
| War Room | Budget left, win prob baseline → plan (with interval), Δ net votes, $/net vote | Builder (`data_editor`) + outcome panel (win-prob bar with interval, margin `histogram()` with a 0 rule, marginal votes per $1k bars) | Pacing stacked bars by week × channel; assumptions `expander` with sliders + preset `pills`; scenarios save/compare |
| Methodology | — | Sources table | Model chain diagram (static SVG/markdown), assumptions table, limitations |

Every KPI and chart card shows a fidelity badge (`observed | aggregated | modeled | sample`). `kpi_card()` and `chart_card()` take `fidelity` as a **required** argument.

---

## 10. Ingestion Jobs

All jobs are modules under `campaign_intel.ingest`, run with `uv run python -m …`. Scheduling options: a GitHub Actions cron (`astral-sh/setup-uv`, then `uv run …`) or running manually before demos.

| Job | Schedule | Steps |
|---|---|---|
| `google_bq` | Daily | Run `sql/stg` and `sql/mart` Google transforms; record `last_updated` from the source |
| `meta_snapshot` | Daily (and on demand) | Query `ads_archive` for (a) every Page ID in `advertiser_sides`, (b) keyword searches (`North Carolina`, NC city names, candidate/committee names), with `ad_reached_countries=["US"]`. Page through `paging.next` with backoff on rate limits. Write raw → normalize → strip `access_token` from snapshot URLs → enrich (side, fundraising, themes, nc_share) → compute daily delta → generate alerts |
| `ncsbe_registration` | Weekly | Download the statewide file → aggregate in chunks (`pandas.read_csv(chunksize=…)`) to precinct × party × age × race × gender → **discard row-level data** → load the aggregate; rebuild `precinct_crosswalk` |
| `ncsbe_history` | One-time (per election) | Aggregate to precinct × election × method and turnout-propensity buckets |
| `ncsbe_results` | One-time | Load 2022 and 2024 precinct results → `baseline_results` |
| `ncsbe_absentee` | Daily during early voting | Aggregate → `early_vote_daily`; subtract from mobilization universes |
| `reference` | One-time | Convert shapes to simplified GeoJSON (`geo` group); load the county↔DMA crosswalk and seeds |

**Alert rules (opponent and allies):**
- ≥ 10 new creatives in 48h.
- A new theme appears.
- The opponent's estimated NC spend band rises a tier week over week.
- A new advertiser is mapped to the opponent's side.

---

## 11. Security, Privacy, Ethics

- **Secrets:** tokens and keys live only in `.env`, loaded with `python-dotenv`. `.env` is git-ignored and `.env.example` documents the variable names. Do not put secrets in `.streamlit/secrets.toml` unless that file is also git-ignored.
- **Snapshot URLs:** strip `access_token` from Meta snapshot URLs before storing or displaying them.
- **Voter-file data:** never stored or served at the individual level. Aggregation happens inside the ingestion job. Suppress any aggregate cell with fewer than 10 voters.
- **BigQuery access:** use least privilege (read on `mart` for the app; write only for ingestion).
- **Honest UI:** the "Model, not forecast" ribbon, fidelity badges, visible ranges, a Methodology page, and no silent sample data.
- **Respect platform terms:** comply with Meta Platform Terms and Ad Library API terms, and with NCSBE data-use notices.

---

## 12. Testing & Acceptance Criteria

All tests run with `uv run pytest`.

**Data tests** (against `mart` or the Parquet snapshot):
- The precinct crosswalk weights sum to 1.0 per precinct per district type.
- District totals equal county totals equal the statewide total for baseline votes and registration, for every district type.
- The 2022 Senate statewide totals from NCSBE match MEDSL within 0.1%.
- Every banded field satisfies `low ≤ mid` and (`high` is NULL or `mid ≤ high`).
- No Meta snapshot URL contains `access_token`.
- No mart table has row-level voter data.

**Model tests:**
- Zero spend gives ΔV = 0, and win probability equals the baseline.
- Doubling spend in one unit shows diminishing marginal ΔV (saturation works).
- With equal parameters, the optimizer never chooses a strictly dominated option.
- With fixed random seeds, results are deterministic.
- `simulate()` runs in < 300ms (CD, 5,000 draws); `optimize()` runs within the targets in §7.7.

**Chart tests:**
- Every factory in `viz.charts` returns a chart whose spec includes a tooltip and explicitly typed encodings.
- Every non-map chart includes a scale-binding parameter (it is `.interactive()`).

**UI acceptance** (manual demo checklist):
- All six pages render in Light and Dark with no hard-coded colors.
- The District ↔ County toggle and the district-type switch work on every map page.
- Every metric shows a fidelity badge.
- Switching `DATA_MODE` to a missing source shows the stale badge or the sample banner.
- WCAG AA contrast passes in both themes.
- The app starts with `uv run streamlit run app.py` from a fresh clone after `uv sync`.

---

## 13. Roadmap

| Phase | Deliverables |
|---|---|
| **P0: Foundations** | `uv` project + `pyproject.toml`, package skeleton, `.env`, BigQuery datasets, geography backbone (GeoJSON + precinct crosswalk), CSS tokens + Altair themes, top bar, component helpers |
| **P1: Data** | Google transforms; Meta snapshot job + normalization + enrichment; NCSBE registration, history, and results; CCES benchmarks; `advertiser_sides` seed v1; source notebooks |
| **P2: Read pages** | Overview, Opponent Tracker, Electorate, Audience Intelligence, Methodology |
| **P3: War Room** | Engine + tests; builder (`data_editor`) + outcome panel in a fragment; assumptions + presets; pacing; optimizer + diff; scenarios (SQLite) |
| **P4: Polish** | Alerts popover, cross-filtering, legislative district types at scale, accessibility pass, dark theme QA, Parquet snapshot for demo day, demo script |

**Suggested split for a 3-person team:**
- Data/pipelines: Google + NCSBE + crosswalk + snapshot export.
- Meta + Audience/Opponent pages + chart factories.
- War Room model + War Room page.
- Shared: `ui` components, theming, Methodology.

**Stretch ideas:**
- FCC public political files for Charlotte DMA TV buys.
- Weighting Meta allocation by matching demographics.
- An LLM-generated "daily brief" summarizing opponent changes.
- Exporting a scenario comparison (charts via Altair's built-in save menu).

---

## 14. Open Items to Verify

1. **Maps:** the current congressional map (2025 redraw of CD 1 and CD 3), the current State Senate and House maps, and whether the voter file's district fields match them.
2. **Meta API:** which Graph API version to pin, and which `ads_archive` fields are actually populated for US ads (especially `target_*`). Use notebook 02.
3. **CCES:** the platform variable mapping (`CC24_300b_*`) and the undocumented columns, against the official codebook. Use notebook 04.
4. **Google `geo_spend`:** whether it uses the 2025 CD boundaries.
5. **DMA crosswalk:** its source, and handling of SC counties in the Charlotte DMA.
6. **Methodology:** final citations for the default effect sizes.
7. **Streamlit theming:** whether the installed Streamlit version supports separate light/dark config themes and reading the active theme at runtime. If it does, consider letting native theming drive Streamlit's own widgets while our toggle drives the CSS tokens and Altair theme. Either way, test that every widget is readable in dark mode.
