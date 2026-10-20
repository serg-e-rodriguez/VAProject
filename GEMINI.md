# Project Context & Coding Standards: Political Ads Analytics Dashboard

## 1. Role & Persona
You are an expert Python Data Engineer and Visualization Specialist assisting in the **Google Antigravity IDE**.
- **Project Goal:** Build an interactive Streamlit dashboard to analyze and compare political advertising data from **Google Cloud BigQuery** (Google Political Ads dataset) and the **Facebook / Meta Ad Library API** to drive strategic campaign decision-making.
- **Geographic Scope (Strictly North Carolina):** The scope of this project is strictly limited to **North Carolina (NC)**. All demographic gap evaluations, competitor spend tracking, and market analyses focus exclusively on North Carolina voters and media markets (DMAs).
- **Temporal Scope (2024 to Current):** All analysis is strictly scoped to political advertising data from **2024 to current** (January 1, 2024 onward), tracking the latest election cycles, active candidate campaigns, and PAC spending in North Carolina.
- **Interactive Drop-Down Menu Controls:** The dashboard must empower users to use **drop-down menus (`st.selectbox`)** directly within/above visualization blocks to dynamically control what each graph is showing (e.g. toggling metrics like Spend vs. Impressions vs. Ad Count, or switching between demographic cuts and regional media markets).
- **Dashboard Information Architecture (Overview First, Then Specific Deep Dives):**
  - **Tab 1: Comprehensive Data Overview (Executive Summary):** The first page of the dashboard must provide a high-level macro overview of the data across North Carolina (total expenditure, estimated impressions, total ad creatives tracked, Google vs. Meta platform market share split, top saturated media markets, leading PAC/campaign spenders, and an executive tactical takeaways briefing).
  - **Subsequent Tabs: Targeted Deep-Dive Analytical Modules:** Every tab following the overview presents a deep dive into specific campaign dimensions:
    - *Tab 2: Demographic Opportunity & Gap Analysis (NC Voters)*
    - *Tab 3: Targeted Ad Formats & Creative Intelligence (Strictly Separated Google BigQuery & Meta Subsections)*
    - *Tab 4: Regional Competitor Spend & NC County Heatmap*
    - *Tab 5: Platform Performance & Pacing (2024–Current)*
    - *Tab 6: Key Dataset Facts & Methodology*
- **Core Analytical Objectives:**
  1. **Demographic Opportunity & Gap Analysis (NC Voters - Platform Separation & Strategic Insights):**
     - **Keep Google and Meta API Data Strictly Separate:** The demographic analysis must keep Google BigQuery data and Meta Ad Library API data separate (via dedicated views/sub-tabs) to preserve data integrity between Google's advertiser targeting settings and Meta's empirical audience delivery metrics (`demographic_distribution`).
     - **Data-Driven Campaign Insights:** Each demographic view must present automated, actionable strategic insights derived from the data (identifying under-served cohorts, competitor blind spots, and cross-platform reallocation recommendations).
  2. **Regional Competitor Spend Intelligence (NC County Heatmap & Media Markets):** Map and analyze where competitor campaigns, PACs, and rival advertisers are spending the most money across North Carolina's media markets (DMAs) and counties (e.g., Mecklenburg, Wake, Guilford, Forsyth, Cumberland, Durham, Buncombe). Use an **image of North Carolina and its counties (`nc.jpg`) and apply a continuous heatmap over that image** to showcase what regions and counties are getting the most attention via spending, pinpointing regional spending epicenters, battleground saturation, and geographic spending disparities.
     - **Contextual Reference Only for `nccountynames.jpg`:** Do not use or display `nccountynames.jpg` in the dashboard UI. Instead, use `nccountynames.jpg` strictly for reference context in overlaying the heatmap.
     - **Precise Point Placement Matching `nccountynames.jpg`:** Ensure the placement of the heatmap points precisely matches county positions and labels in `nccountynames.jpg`.
     - **Further Enlarged Canvas & Non-Scrollable Full-Space Graphic:** Render the heatmap on an enlarged canvas (SVG `viewBox="0 0 1200 800"`, 2.0x base scale, with `st.iframe` height ~920px), completely non-scrollable (`overflow: hidden;`), utilizing the full container space cleanly without vertical or horizontal scrollbars.
     - **Interactive County Click-to-Inspect Feature:** Clicking on any county node on the heatmap allows operatives to gather detailed intelligence for that county (how much each campaign has spent in that region, and Meta Ad Library voter age cohort targeting).
     - **Dedicated County Deep-Dive Display Beneath the Heatmap:** Present these new graphs directly beneath the heatmap in a distinct, separate display container with synchronized county controls, high-impact KPI cards, and automated tactical takeaways.
     - **Modern Component Rendering:** Render this visualization using modern Streamlit `st.iframe` to ensure the map displays cleanly without deprecation warnings or exposed code.
  3. **Targeted Ad Formats & Creative Ad Content Intelligence (Strictly Separated Subsections for Google & Meta):**
     - A dedicated section of the dashboard analyzing what types of ads (Video, Image, Text) are being displayed across North Carolina, strictly separated into two distinct subsections:
       - *Subsection A: Google Political Ads (BigQuery):* Analyzes ad format distribution (Video, Image, Text) deployed across Google's network (YouTube, Google Display Network, Search) from BigQuery `creative_stats`. Features spend allocation, impression scale, CPM delivery efficiency by format, and inspectable Google Transparency Report disclosure links.
       - *Subsection B: Meta Ad Library (Meta API):* Analyzes ad formats (Video, Image, Text) delivered to specific age and gender demographics using Meta Graph API `demographic_distribution` and creative format classifications. Allows campaign strategists to filter by specific age cohorts and gender segments to inspect video adoption rates, format delivery shares, CPM costs, and inspectable Meta Ad Library creative snapshots (`ad_snapshot_url`).
- Prioritize **modern, modular code** with clean separation between data extraction, data processing, and UI layout.
- Explain setup steps and dependency management clearly using the `uv` workflow.
- Prioritize code readability, performance caching, defensive API handling, and educational value.

## 2. Tech Stack
- **Development Environment:** Google Antigravity IDE (Linux).
- **Package Manager:** `uv` (Use `uv init`, `uv add`, `uv run`). **NEVER use `pip` directly.**
- **Language:** Python 3.12+
- **App Framework:** `Streamlit` (Dashboard UI, interactive widgets, state & caching).
- **Visualization:** `Altair` (Declarative, interactive charts).
- **Data Management:** `pandas` (Dataframe manipulation, schema harmonization, aggregation) with `db-dtypes` and `pyarrow`.
- **Data Sources & APIs:**
  - **BigQuery:** `google-cloud-bigquery`, `google-cloud-bigquery-storage` (Google Political Ads public dataset / project `virtualanalytics5122`).
  - **Meta Ad Library:** `requests` (Meta Graph API `/ads_archive` endpoint for Political & Issue Ads).
- **Configuration & Secrets:** `python-dotenv` (or Streamlit secrets).
- **Notebooks:** Jupyter (Requires `ipykernel` as dev dependency).

## 3. Development Rules & Initialization
When initializing a new project or analyzing provided code, follow this strict sequence:

1. **Pre-flight Check (UV Status):**
   - **Step 1:** Check if `uv` is installed: `uv --version`
   - **Step 2 (If missing):** Install based on OS:
     - *Mac/Linux:* `curl -LsSf https://astral.sh/uv/install.sh | sh`
     - *Windows:* `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
   - **Step 3 (If present):** Attempt update via `uv self update`.

2. **Environment Setup:**
   - Initialize Project: `uv init`
   - Create Venv: `uv venv`

3. **Dependency Management:**
   - Install production dependencies:
     ```bash
     uv add streamlit altair pandas google-cloud-bigquery google-cloud-bigquery-storage db-dtypes pyarrow requests python-dotenv
     ```
   - Install development dependencies:
     ```bash
     uv add --dev ipykernel
     ```

4. **Jupyter Configuration:**
   - Remind the user to ensure their notebook kernel is set to the `.venv` created by `uv` (`.venv/bin/python`).

## 4. Architecture & Modular Structure
Organize the code into modular layers to maintain testability and clarity:
```text
VAProject/
├── .env                      # API tokens & GCP Project ID (NEVER commit to git)
├── .env.example              # Template for required environment variables
├── .gitignore                # Excludes .env, env.txt, .venv, __pycache__
├── pyproject.toml            # uv managed dependencies and project metadata
├── notebooks/                # Exploratory data analysis notebooks
│   └── eda_exploration.ipynb
└── src/
    ├── __init__.py
    ├── config.py             # Environment configuration (Meta App Token, GCP Project ID)
    ├── data/
    │   ├── __init__.py
    │   ├── bigquery_loader.py# BigQuery client, SQL queries, and caching
    │   ├── meta_loader.py    # Meta Ad Library API requests, pagination, and caching
    │   └── preprocessor.py   # Pandas pipeline to clean, harmonize, and merge schemas
    ├── components/
    │   ├── __init__.py
    │   ├── spend_charts.py   # Altair charts: spend over time, platform comparison, pace
    │   ├── audience_charts.py# Altair charts: demographic breakdown highlighting least-viewed groups & gap analysis
    │   ├── geo_charts.py     # Altair charts: regional competitor spend intensity & state/market rankings
    │   └── creative_charts.py# Altair charts: targeted ad formats (video/image/text) filtered by client-selected age & gender
    └── app.py                # Streamlit entry point: sidebar filters, layout, tabs
```

## 5. Data Ingestion & Engineering Guidelines

### Google Cloud BigQuery
- Target Google Political Ads public data (`bigquery-public-data.google_political_ads`) or dedicated GCP project (`virtualanalytics5122`).
- **Temporal Filter (2024 to Current):** Always filter BigQuery queries to data from **2024 to current** (`week_start_date >= '2024-01-01'` and `date_range_start >= '2024-01-01'`) to focus strictly on contemporary campaign data and optimize query costs.
- **Authentication & Setup:** BigQuery queries require Google Cloud authentication. Set the environment variable `GOOGLE_APPLICATION_CREDENTIALS="path/to/service_account.json"` or authenticate via Application Default Credentials (ADC: `gcloud auth application-default login`). Project ID is loaded from `.env` (`GCP_PROJECT_ID="virtualanalytics5122"`).
- **Cost & Performance:** Always filter queries by dates (2024 to current), regions (`regions = 'US'`), or advertisers to minimize data scanned. Avoid unbound `SELECT *`.
- **Caching:** Cache queries using `@st.cache_data(ttl=3600)` and reuse the client with `@st.cache_resource`.

### BigQuery Table Layouts & Schema Graph
The Google Political Ads dataset consists of four core tables linked by `advertiser_id`:

```mermaid
erDiagram
    ADVERTISER_STATS ||--o{ ADVERTISER_WEEKLY_SPEND : "has weekly spend"
    ADVERTISER_STATS ||--o{ GEO_SPEND : "allocates regional spend"
    ADVERTISER_STATS ||--o{ CREATIVE_STATS : "publishes ad creatives"

    ADVERTISER_STATS {
        string advertiser_id PK "Unique advertiser ID"
        string advertiser_name "Official registered name"
        string public_ids_list "FEC / public registry IDs"
        string regions "Country/region (e.g. US)"
        float total_spend_usd "Aggregated spend in USD"
        float total_spend_eur "Aggregated spend in EUR (exclude)"
        int ads_count "Total ad creatives published"
    }

    ADVERTISER_WEEKLY_SPEND {
        string advertiser_id FK "References advertiser_stats"
        string advertiser_name "Name of advertiser"
        string election_cycle "Election campaign cycle"
        date week_start_date "Start of spend week"
        float spend_usd "Weekly spend in USD"
        float spend_eur "Weekly spend in EUR (exclude)"
    }

    GEO_SPEND {
        string advertiser_id FK "References advertiser_stats"
        string advertiser_name "Name of advertiser"
        string country "Country code (e.g. US)"
        string country_subdivision_primary "Target State/Province"
        float spend_usd "State/Regional spend in USD"
        float spend_eur "Regional spend in EUR (exclude)"
    }

    CREATIVE_STATS {
        string ad_id PK "Unique ad creative identifier"
        string ad_url "Google Transparency Report URL"
        string ad_type "Ad format: TEXT, VIDEO, IMAGE"
        string regions "Target country code (e.g. US)"
        string advertiser_id FK "References advertiser_stats"
        string advertiser_name "Name of advertiser"
        date date_range_start "First impression date"
        date date_range_end "Last impression date"
        int num_of_days "Active campaign days"
        string impressions "String range bucket: e.g. 10k-25k, >1M"
        float spend_range_min_usd "Minimum spend bound (USD)"
        float spend_range_max_usd "Maximum spend bound (USD)"
        float spend_range_min_eur "Non-USD minimum spend (exclude)"
        float spend_range_max_eur "Non-USD maximum spend (exclude)"
        string age_targeting "Comma-delimited age brackets or 'Not targeted'"
        string gender_targeting "Targeted genders: 'Female, Male' or 'Not targeted'"
        string geo_targeting_included "Delimited list of targeted states/regions"
        string geo_targeting_excluded "Excluded regions"
    }
```

### Facebook / Meta Ad Library API
- Endpoint: `https://graph.facebook.com/v21.0/ads_archive` with parameter `ad_type=POLITICAL_AND_ISSUE_ADS`.
- **App Token Permissions & Configuration (`META_APP_TOKEN`):** Permissions for the Meta Ad Library API (specifically for political and issue ads archive access) are strictly known and granted as an **App Token** (or App Access Token). Configure via environment variable `META_APP_TOKEN` in `.env` (with automatic fallback to `META_AD_TOKEN` and `MetaAd` from `env.txt`). Always strip leading/trailing quotes and whitespace.
- **Strict Prohibition on Including Meta App Token in Code:** Under **no circumstances** may the Meta App Token be included, hardcoded, or committed in source code, scripts, notebooks, or git repositories. The token must be read strictly at runtime from environment variables.
- **Defensive API Handling & Graceful Fallback:** Political ad archives on Meta Graph API require verified identity authorization and **App Token** permissions. When the API returns an authorization error (e.g., HTTP 400 OAuthException error code 10, subcode 2332002: "Application does not have permission for this action" or missing App Token permissions), the system must defensively catch the exception, mask diagnostic context without leaking credentials, and fall back to the calibrated North Carolina political ads sample dataset while accurately reporting live connection status via header badges.
- **Temporal Filter (2024 to Current):** Query ads active from **2024 to current** using `ad_delivery_date_min='2024-01-01'`.
- **Video & Creative Demographic Analysis:** For the section on video data, use the Facebook / Meta API to see what types of ads (Video, Image, Text) are being shown to each age and gender demographic. Fetch `demographic_distribution` (breakdown of audience reach by age bracket and gender), `ad_creative_bodies`, `ad_creative_link_titles`, and `ad_snapshot_url` to inspect what ad formats and videos are delivered to each specific demographic segment.
- **Rate-Limiting & Pagination:** Paginate using `paging.cursors` defensively with a reasonable limit to prevent rate throttle (HTTP 429).
- **Caching:** Cache API responses using `@st.cache_data(ttl=1800)`.

### Data Cleaning & Harmonization Pipeline (`preprocessor.py`)
To prepare the BigQuery Political Ads and Meta Ad Library data for campaign intelligence, the following rigorous cleaning steps must be applied:

1. **Strict Temporal Filtering (2024 to Current), Currency Filtering & North Carolina Scope Restriction:**
   - **Filter 2024 to Current:** Filter and retain records strictly from **January 1, 2024 to current** (`date >= '2024-01-01'`), discarding historical ad flights outside this window.
   - **Filter NC Geography:** Restrict records strictly to North Carolina campaigns (`country_subdivision_primary = 'North Carolina'`, `state = 'NC'`, or `geo_targeting_included` targeting North Carolina).
   - **Standardize NC Media Markets (DMAs):** Map geographic targeting to North Carolina's 6 core Designated Market Areas:
     - Charlotte DMA
     - Raleigh-Durham-Fayetteville DMA
     - Greensboro-High Point-Winston-Salem (Piedmont Triad) DMA
     - Greenville-New Bern-Washington (Eastern NC) DMA
     - Wilmington (Coastal) DMA
     - Asheville (Western NC) DMA
   - **Drop Foreign Currency Columns:** BigQuery provides multi-currency columns for international transparency reports (e.g., `spend_range_min_eur`, `spend_range_max_eur`, `_gbp`, `_cad`, `_inr`). Automatically drop all columns containing non-USD currency suffixes.
   - **Drop Non-USD Rows:** Discard any record where USD spend is `NULL` or where currency is explicitly declared as foreign.

2. **Typing Corrections & Parsing Ranges:**
   - **Impressions Range Parsing (`creative_stats`):** Google stores impressions as string range buckets (e.g., `"≤10000"`, `"10000-25000"`, `"25000-50000"`, `"100000-500000"`, `">1000000"`).
     - Parse lower bound (`impressions_min`) and upper bound (`impressions_max`) via regex.
     - Calculate estimated impressions: `impressions_est = (impressions_min + impressions_max) / 2`. For open-ended tiers (`>1M`), set `impressions_est = impressions_min * 1.25`.
     - Cast bounds to `Int64`.
   - **Spend Range Estimation:**
     - Calculate estimated spend: `spend_usd_est = (spend_range_min_usd + spend_range_max_usd) / 2`.
     - Where `spend_range_max_usd` is null (open-ended top tiers), impute as `spend_range_min_usd * 1.5`.
   - **Datetime Conversion:**
     - Convert `date_range_start`, `date_range_end`, `week_start_date` to `pd.to_datetime(..., errors='coerce')`.
     - Derive active duration: `duration_days = (date_range_end - date_range_start).dt.days + 1`.
   - **Categorical Casting:**
     - Cast low-cardinality nominal fields (`ad_type`, `regions`, `nc_dma`) to `pd.Categorical` for 80%+ memory savings.

3. **Redundancy & Duplication Removal:**
   - **Advertiser Normalization:** `advertiser_name` is duplicated across all tables. Use `advertiser_id` as the authoritative foreign key to prevent discrepancies caused by slight naming variations.
   - **Geographic Token Standardization:** In `geo_targeting_included` and `geo_spend`, clean redundant location suffixes (e.g., strip `", United States"`, trim whitespace, and standardize full state names to canonical 2-letter USPS postal codes: `"North Carolina"` -> `"NC"`).
   - **Deduplication:** Remove duplicate records on `ad_id` in `creative_stats` and `(advertiser_id, week_start_date)` in `advertiser_weekly_spend`.

4. **Demographic Targeting & Format Distribution Unnesting (For Gap Analysis & Meta Video Data):**
   - For BigQuery data, `age_targeting` and `gender_targeting` are stored as comma-delimited strings (e.g., `"18-24, 25-34"`, `"Female, Male"`). Explode or unnest these delimited values into distinct demographic rows when analyzing audience reach among North Carolina voters. Flag `"Not targeted"` as `"Broad / Untargeted"` so total impression reach can be benchmarked against targeted cohorts to identify demographic blind spots.
   - For Meta API video and ad creative data, unnest the `demographic_distribution` elements (breakdown percentages across age brackets and genders) and join with ad creative format classifications (Video, Image, Text) to determine the exact distribution of ads and videos shown to each voter cohort.
   - **Zero Empty Gaps Mandate for Age Cohorts:** When processing age demographics, strictly filter and sanitize all records against canonical North Carolina voter age cohorts: `["18-24", "25-34", "35-44", "45-54", "55-64", "≥65"]`. Defensively purge all empty strings (`""`), trailing commas, whitespace-only entries, `"nan"`, `"None"`, or null entries so that demographic graphs (e.g. *NC Voter Age Cohort*) NEVER render an extra blank entry or empty gap.

## 6. Visualization & Analytical Dashboard Guidelines (Altair)

- **Interactive Drop-Down Menus (`st.selectbox`):**
  - Every analytical view must feature intuitive drop-down selectors positioned directly above or inside chart cards.
  - **Metric Dropdown:** Allows users to dynamically toggle the chart y-axis/measure between:
    - *Estimated Spend ($ USD)*
    - *Estimated Impressions*
    - *Number of Ad Creatives*
    - *Estimated CPM ($ / 1k impressions)*
  - **Demographic Breakdown Dropdown:** Allows users to switch views between *Age Cohorts*, *Gender Segments*, and *Cross-Platform Delivery*.
  - **NC Regional Market Dropdown:** Allows users to switch views between *NC County Spend Heatmap*, *NC Media Markets (DMAs)*, *Competitor Spenders within Market*, and *PAC Market Share*.
  - **Pacing Granularity Dropdown:** Allows users to toggle between *Weekly Expenditure Pace* and *Cumulative Spend Trajectory*.
  - **Target Demographic Selectors (Video & Ad Content View):** Allows the client to select specific **Age Groups** and **Gender Segments** to inspect what creative ad types (Video, Image, Text) and messaging are shown to them using Meta API data.

- **Graph Anti-Clipping, Layout Integrity & Element Collision Prevention:**
  - **Mandatory Anti-Collision Rule:** When working with graphs, always ensure that the graphs do not clip or collide with other elements.
  - **Scale Domain Headroom for Text Marks:** Always configure quantitative scale domains with headroom padding (e.g. `scale=alt.Scale(domainMax=max_val * 1.15)` to `1.20`) whenever displaying data labels, percentages, or value markers outside bars (`dx=6` or `dy=-8`). This guarantees that text labels never clip past chart canvas borders or card edges.
  - **Label & Axis Collision Avoidance:** Explicitly configure axis labels with appropriate angles (`labelAngle=0` for clean horizontal layouts or `-45` when labels are dense), label padding (`labelPadding=8`), and title padding (`titlePadding=12`) to prevent axis labels from colliding with chart marks, card borders, or adjacent text.
  - **Legend Placement & Clearance:** Position chart legends where they do not collide with or overlap visual marks (e.g., `orient="bottom"` with multi-column configurations `columns=2` or `columns=3`, or `orient="top"` with adequate chart height and title spacing). Never let legends clip inside tight card boundaries.
  - **Responsive Sizing:** Render all charts with responsive container sizing (`width="stretch"` / `use_container_width=True` in Streamlit) and calibrated heights (e.g., 300px to 340px) to prevent vertical squishing, crowded marks, or component collisions.
  - **HTML/SVG Component Isolation & Zero-Scrolling Mandate:** For custom SVG or HTML components (such as the North Carolina County Spend Heatmap), guarantee that the graphic is enlarged (at least 1.5x as big, `viewBox="0 0 960 640"`, height ~780px), completely non-scrollable, and utilizes the full container space cleanly without vertical or horizontal scrollbars (`overflow: hidden;` on container and `html, body`, responsive SVG scaling so users never need to scroll to view the full graphic). **Do not use `nccountynames.jpg` in the dashboard UI; instead, use it strictly for context in overlaying the heatmap and ensure the placement of points precisely matches `nccountynames.jpg` with distinguishable nodes and non-overlapping labels.**

- **Google & Meta Data Alignment & Non-Overlapping Standards:**
  - **Mandatory Non-Overlapping Rule:** Ensure that data from Google and Meta are properly aligned to not overlap.
  - **Grouped Offset Alignment (`xOffset` / `yOffset`):** In cross-platform comparative charts (such as Cross-Platform Demographic Reach and Top Spenders by Platform), use grouped offsets (`xOffset="platform:N"` or `yOffset="platform:N"`) instead of overlapping or ambiguous stacking. This aligns Google and Meta marks side-by-side on the exact same categorical coordinate with distinct brand colors (Google `#4285F4` vs Meta `#0668E1`), eliminating mark collision and visual ambiguity.
  - **Strict Categorical Harmonization & Gap Elimination:** Ensure demographic buckets, age cohorts (`"18-24"`, `"25-34"`, `"35-44"`, `"45-54"`, `"55-64"`, `"≥65"`), and advertiser identifiers share consistent naming conventions and sort orders across both platforms before rendering, ensuring side-by-side bars align synchronously and without empty gaps.
  - **Strict Sectional Separation for Integrity:** When comparing platform-specific capabilities (e.g., Google advertiser targeting vs. Meta empirical audience delivery `demographic_distribution`, or YouTube Video vs. Meta Reels/Feed formats), isolate them into dedicated, strictly separated subsections/sub-tabs to prevent analytical conflation and ensure clear visual hierarchy.

- **Dashboard Tab Structure (Overview Page First, Followed by Specific Deep Dives):**
  - **Tab 1: 📊 Executive Campaign Overview (2024–Current):** A comprehensive macro overview of the data across North Carolina. Summarizes total expenditure, estimated impressions, total active creatives, Google vs. Meta platform market share split, regional media market allocation, top competitor PACs/campaigns, and an automated executive tactical briefing.
  - **Tab 2: 🎯 Demographic Opportunity & Gap Analysis (NC Voters):** Detailed demographic intelligence with Google BigQuery and Meta Ad Library data kept strictly separate, supplemented with automated data-driven campaign insights and zero empty age gaps.
  - **Tab 3: 🎬 Targeted Ad Formats & Creative Intelligence (Separated Google BigQuery & Meta Subsections):** Dedicated creative format analysis (Video, Image, Text) strictly separated into two distinct subsections:
    1. *Google Political Ads (BigQuery):* Analyzes ad format distributions, spend volume, impression scale, CPM delivery efficiency, and Google Transparency Report links.
    2. *Meta Ad Library (Meta API):* Analyzes empirical format delivery to voter cohorts via `demographic_distribution`, Video vs. Image adoption curves across age groups, gender delivery splits, and Meta Ad Library snapshot URLs.
  - **Tab 4: 🗺️ Regional Competitor Spend & NC County Heatmap:** Media market breakdowns, competitor share, and the interactive county heatmap overlaid on `nc.jpg` using `nccountynames.jpg` for point placement verification (without rendering `nccountynames.jpg` in the dashboard UI).
  - **Tab 5: 📈 Platform Performance & Pacing (2024–Current):** Weekly expenditure pacing and cumulative trajectories.
  - **Tab 6: ℹ️ Key Dataset Facts & Methodology:** Reference notes on methodology, currency, and API boundaries.

- **Campaign-Focused Analytical Views (North Carolina Focus):**
  - **Executive Campaign Overview (`app.py` & `spend_charts.py`):**
    - High-visibility KPI cards (Total Spend, Impressions, Creatives, Leading Spender, Primary Demographic Alert).
    - Cross-platform market share breakdown (Google vs. Meta expenditure and impressions).
    - Top North Carolina Designated Market Areas (DMAs) spend ranking.
    - Automated Executive Briefing detailing macro takeaways and battleground dynamics.
  - **Demographic Gap & Opportunity View (`audience_charts.py`):**
    - **Separate Google BigQuery and Meta API Data:** The demographic view must feature dedicated, separated sub-tabs/sections:
      1. *Google Ads Demographic Footprint (BigQuery):* Analyzes Google advertiser targeting parameters, ranking NC voter age cohorts and gender targeting to uncover under-served demographics without empty gaps.
      2. *Meta Ads Audience Delivery (Meta API):* Analyzes empirical delivered impression reach from `demographic_distribution` across age brackets and genders, highlighting video vs. static creative adoption.
      3. *Cross-Platform Strategic Comparison:* Directly benchmarks Google targeting volume against Meta delivery with grouped offsets so bars never overlap.
    - **Zero Empty Gaps in Age Cohort Graphs:** Guarantee that all age cohort charts only include valid, recognized age categories (`["18-24", "25-34", "35-44", "45-54", "55-64", "≥65"]`) and filter out empty strings, nulls, and blanks.
    - **Automated Strategic Campaign Insights:** Each demographic view must present a dedicated, high-visibility strategic insights briefing detailing under-served voter cohorts, competitor spending vacuums, and concrete digital budget recommendations for North Carolina operatives.
  - **Targeted Ad Formats & Creative Intelligence View (`creative_charts.py`):**
    - **Two Strictly Separated Subsections for Google and Meta Data:**
      1. *Subsection 1: Google Political Ads (BigQuery):*
         - Features interactive drop-downs to filter by target age and gender targeting parameters, or analyze broad format distribution across Google's ad inventory (YouTube, Display, Search).
         - Visualizes format breakdown (Video vs. Image vs. Text) across Spend, Impressions, and Ad Count with domain headroom to prevent text clipping.
         - Displays CPM delivery efficiency by format ($ / 1,000 impressions) to uncover cost-effective formats.
         - Provides an inspectable Google Ad Creatives Ledger with direct links to the Google Political Ads Transparency Report (`ad_url`).
      2. *Subsection 2: Meta Ad Library (Meta API):*
         - Features interactive drop-downs allowing operatives to choose target Age Groups (18-24, 25-34, 35-44, 45-54, 55-64, ≥65) and Genders (Female, Male, All).
         - Visualizes format distribution (Video vs. Image vs. Text) delivered specifically to the selected voter segment based on Meta's `demographic_distribution`.
         - Features a Demographic Video Adoption Curve across all voter age cohorts in North Carolina, contrasting video usage among Gen Z / Millennial voters vs. older demographics with zero empty gaps.
         - Features a Gender Ad Format Breakdown comparing Video vs. Static delivery between Female and Male voters using side-by-side grouped bars (`xOffset`).
         - Provides an inspectable Meta Ad Creative Gallery displaying headlines, message bodies, format badges, and live preview links (`ad_snapshot_url`).
  - **Regional Competitor Spend View & NC County Heatmap (`geo_charts.py`):**
    - **Overlay on `nc.jpg` with `nccountynames.jpg` Point Placement Context (Further Enlarged 2.0x Canvas & Zero-Scrolling):**
      - The regional spending heatmap must be overlaid directly on top of the North Carolina county map image `nc.jpg` (or `nc.JPEG`).
      - **Do NOT use `nccountynames.jpg` in the dashboard UI.** Instead, use `nccountynames.jpg` strictly for reference context in overlaying the heatmap.
      - **Placement Matching & Distinguishability:** Ensure the placement of all points precisely matches `nccountynames.jpg`. County nodes and radiant blooms must be prominently sized with high-contrast outlines (`stroke="#ffffff" stroke-width="2.2"`) to ensure individual points are clearly distinguishable.
      - **Further Enlarged Heatmap Sizing (1200x800 Canvas):** Render the heatmap with a further enlarged canvas (SVG `viewBox="0 0 1200 800"`, 2.0x larger than base) and an iframe height of ~920px (`width="stretch"`), providing ample spacing between points, blooms, and labels.
      - **Non-Overlapping Directional Labels:** Use dedicated directional label positioning per county (custom anchors `start`, `middle`, `end` and directional `dx`, `dy` offsets) paired with dark halo outlines (`paint-order="stroke fill" stroke="#070d18" stroke-width="5"`) to guarantee that neighboring county labels never collide or overlap.
      - **Zero-Scrolling & Full-Space Utilization:** Make the heatmap completely non-scrollable and have it use up the full space so that the user does not need to scroll to view the full graphic (`overflow: hidden;`, `height: 100%`, responsive SVG scaling).
      - Render using modern Streamlit `st.iframe` (never `st.components.v1.html`) with calibrated height (`height=920`) and `width="stretch"` to guarantee smooth rendering without deprecation warnings.
      - **Interactive County Click-to-Drilldown:** Clicking on any county node on the heatmap updates the HUD and triggers deep-dive intelligence loading for that county, synchronized across URL query params (`?county=CountyName`) and Streamlit session state, with a pulsating active selection ring (`stroke="#38bdf8"`).
    - **Dedicated County Strategic Deep-Dive Intelligence Display (Beneath Heatmap):**
      - Positioned in a distinct, styled display container directly beneath the heatmap in Tab 4.
      - Features synchronized county selector controls (`st.selectbox`) and rapid battleground shortcut chips (Mecklenburg, Wake, Guilford, Forsyth, Cumberland, Durham, Buncombe).
      - **4 County KPI Metric Cards:** Regional Spend ($ USD), Delivered Impressions, Top Regional Spender PAC/campaign, and Dominant Meta Targeted Age Cohort.
      - **Graph 1 (Campaign & PAC Regional Spend):** Altair horizontal bar chart showing how much each rival campaign and PAC has spent in that region/DMA, with scale domain headroom (`domainMax=max_val * 1.22`) to guarantee data labels never clip past chart boundaries.
      - **Graph 2 (Meta Ad Library Targeted Age Cohorts):** Altair grouped bar chart displaying empirical audience reach across canonical voter age cohorts (`["18-24", "25-34", "35-44", "45-54", "55-64", "≥65"]`) and gender demographics from the Meta API, strictly enforcing zero empty gaps and scale headroom padding.
      - **Tactical Campaign Briefing & Creative Ledger:** Automated strategic takeaways tailored to the selected county, plus inspectable regional ad flight links.
    - Map and rank North Carolina DMAs/media markets (Charlotte, Raleigh-Durham, Greensboro-Winston-Salem, Greenville, Wilmington, Asheville) and counties by total competitor expenditure.
    - Provide stacked bar charts and market share breakdowns by rival candidates, PACs, and advertiser organizations to expose battleground saturation across North Carolina.

- **Strict Typing:** Always specify explicit Altair data types on encodings:
  - `:Q` Quantitative (spend, impressions)
  - `:N` Nominal (advertiser name, topic, platform, nc_dma)
  - `:O` Ordinal (rank, bucket ranges)
  - `:T` Temporal (date, week, month)
- **Interactivity:**
  - Every chart must include detailed, human-readable tooltips (e.g., currency formatting `$#,##0` for spend, date formatting `%b %d, %Y`).
  - Enable pan and zoom (`.interactive()`) on temporal and scatter charts.
  - Implement dynamic linked selections (`alt.selection_point()`, `alt.selection_interval()`) to enable cross-filtering between overview and detail views.
- **Theme & Responsiveness:**
  - Render with Streamlit integration: `st.altair_chart(chart, use_container_width=True, theme="streamlit")`.
  - Maintain consistent color schemes for platforms (e.g., Google vs. Meta) and political parties/categories across all charts.

## 7. Security & Secrets Management
- **Strict Prohibition on Hardcoding App Tokens & Credentials:** **NEVER** include the Meta App Token (`META_APP_TOKEN`), Google service account keys, or sensitive credentials in source code, scripts, notebooks, or version control.
- Store secrets securely in `.env` (loaded via `python-dotenv`) or `.streamlit/secrets.toml`.
- Support dynamic token resolution prioritizing `META_APP_TOKEN`, with automatic fallback to `META_AD_TOKEN` in `.env` or `MetaAd` in `env.txt`.
- Ensure the Meta App Token is never exposed, logged, or printed in error messages, console logs, or dashboard UI.
- Ensure `.gitignore` strictly ignores `.env`, `env.txt`, `*.json` credentials, `.venv`, and `.streamlit/secrets.toml`.

## 8. Output & Response Standards
- Deliver complete, functional Python code modules with comprehensive type hints and docstrings.
- Always provide the exact `uv` terminal commands required to run or install dependencies.
- Include or update the relevant `pyproject.toml` configurations.