# NC Race Intelligence & War Room

A Streamlit + Altair visual analytics app for the **2026 North Carolina US Senate and US House races**, built
for a Democratic campaign's media team. It shows where political ad money is going, what the opponent is
saying and to whom, which voters each district or county holds, and, in the **War Room**, how to spend a
remaining budget across regions, platforms and audiences, with honest uncertainty.

*Visual Analytics course project. Use case: "The Midterms: Political & Issue Advertising".*

## App Deployment URL

**➡️ <https://vaproject-team2.streamlit.app/>** (hosted on Streamlit Community Cloud)

## Local Setup Instructions

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) installed. uv installs the right Python
(3.12+) and all dependencies for you.

```bash
git clone https://github.com/serg-e-rodriguez/VAProject.git
cd VAProject
uv sync
uv run streamlit run app.py
```

The app opens at <http://localhost:8501>.

- **No credentials are needed.** All the data the app uses is committed in `data/` (see [Data](#data)).
- **Optional: Gemini in the War Room.** Step 5 of the War Room can ask Google Gemini to explain or adjust a
  plan. To turn it on, copy `.env.example` to `.env` and set `GEMINI_API=<your key>`. Everything else works
  without a key.

## Project Description

### The problem

A campaign has a fixed budget left and a few weeks to go. It needs to answer:

1. Where is the race close, and where are we out-spent?
2. What is the other side spending, on which platforms, with which messages, aimed at whom?
3. Who lives in each region, who votes there, and what would it take to win it?
4. If we spend $X here, on this platform, for this audience, how much does it move the race?

### How to use the app

In the sidebar, **first pick the race**: *US Senate* (statewide, mapped by the 100 counties) or *US House*
(the 14 congressional districts). Then open one of the pages:

| Page | What it shows |
|---|---|
| **Overview** | Headline KPIs, spend and share of voice by side, week-by-week spend (Dem vs GOP), top committees and PACs, platform mix, registered voters vs. 2022 midterm turnout, and the path to win (statewide or per target district). |
| **Region Analysis** | A choropleth map of NC for the chosen race. **Click a county or district** to open its *Audience Analysis*: party registration and turnout by age, race and gender, why it leans the way it does, our path to win there, and who is advertising there. |
| **Opponent Tracker** | Republican spend per week by platform, platform mix (them vs us), who is paying, new advertisers in the last 7 days, the topics their ads mention vs ours, the ages their ads reach, and a library of their latest real ads. |
| **War Room** *(main feature)* | A six-step planner: **1** set the budget against what both sides have spent · **2** read the opponent's messaging and set how hard it pushes back · **3** choose our message mix · **4** see the optimized plan, its map, win chance and net votes from a Monte Carlo simulation, and what each platform × goal buys per $100K · **5** ask Gemini to explain or adjust the plan (optional) · **6** the final recommended spending. |

A light/dark mode toggle is at the bottom of the sidebar, next to the data snapshot date.

### How the War Room model works

- **Baseline:** 2024 presidential precinct results, rolled up to counties and districts, plus voter
  registration and 2022 turnout from NCSBE.
- **Response:** ad dollars in a region turn into persuaded unaffiliated voters or mobilized low-turnout
  Democrats. Returns diminish (concave curves), and costs come from observed ad prices (CPMs).
- **Opponent pressure:** each region's Republican share of voice reduces our ads' effect there.
- **Uncertainty:** a 4,000-draw Monte Carlo simulation samples the model's assumptions and reports win chance
  and net votes with ranges.
- **Optimizer:** a greedy allocator puts each next $100K wherever it raises win chance the most.
- **Planning date:** you plan "as of" a date before Election Day, so the model never sees later ads or the
  2026 results.

The War Room is **a model, not a forecast**. Its effect sizes are assumptions informed by the research
literature, and you can switch between ad-effect presets in the app.

## Data

Every number in the app comes from real public data, frozen in a snapshot in `data/cache/` (Parquet files plus
`manifest.json`, built 2026-11-05).

| Source | Used for |
|---|---|
| NC State Board of Elections: precinct results (2024, 2026), voter_stats (2022, 2024), history_stats (2022) | Baselines, county/district roll-ups, registration by party and demographics, 2022 turnout, 2026 results |
| Google Political Ads Transparency (BigQuery public dataset) | NC-targeted ads, weekly spend, spend by congressional district |
| Meta Ad Library API | Ad text, spend and impression ranges, NC delivery share, delivery by age and gender |
| MEDSL 2022 US Senate results (`data/senate_2022.csv`) | County cross-check |
| CCES 2024, UNC module (`data/CCES24_UNC_OUTPUT.csv`) | News sources and economic views by age |
| US Census TIGERweb boundaries and ZCTA→county file (`data/geo/`) | County and district maps, ZIP-to-county lookup |

Seeds in `seeds/` hold hand-curated inputs: which advertisers are on which side, keyword lists for ad topics,
and the model's default assumptions.

### Rebuilding the snapshot (optional)

You don't need this to run the app. To refresh the data, copy `.env.example` to `.env` and set `GCP_PROJECT_ID`
(BigQuery access through `gcloud auth application-default login`) and a Meta Ad Library `META_AD_TOKEN`. Then:

```bash
uv run python -m campaign_intel.ingest.build_snapshot                 # everything (~30-60 min, mostly Meta)
uv run python -m campaign_intel.ingest.build_snapshot --skip-meta     # NCSBE + Google only
uv run python -m campaign_intel.ingest.build_snapshot --skip-ncsbe --skip-google --skip-meta   # re-derive from cached raw files
```

Raw downloads are cached in `data/raw/` (git-ignored).

## Project Layout

```
app.py                      entry point: race picker, sidebar navigation, theme
app_pages/                  one file per page: overview, regions, opponent, war_room
src/campaign_intel/
  ingest/                   download and build the snapshot (NCSBE, Google BigQuery, Meta API)
  data/                     snapshot reader and cached loaders used by the pages
  processing/               ad sides and topics, survey weighting, crosswalks
  model/                    Monte Carlo engine, optimizer, assumptions, War Room glue
  war_room_service.py       plan -> predict -> explain (incl. the optional Gemini calls)
  viz/                      Altair charts, maps and themes
  ui/                       KPI cards, page components, CSS
data/                       committed data snapshot (cache/, geo/, CSVs)
seeds/                      advertiser sides, topic keywords, default model assumptions
notebooks/                  exploration and sanity checks (BigQuery EDA, Meta fields, crosswalk, CCES, model)
tests/                      data, model, chart and War Room tests
PROJECT_DESIGN(1).md        design doc: goals, data pipeline, model
UI_Design(1).md             UI design doc: layout, components, colors
```

## Tests

```bash
uv run pytest
```

115 tests check that the snapshot reproduces the certified 2024 presidential totals, that all geographies
add up to the same statewide totals, and that the model is monotone, has diminishing returns, is
reproducible and runs fast.

## Known Limits

- The War Room is a model, not a forecast. Its effect sizes are assumptions.
- Ad libraries don't report spend by county, so most opponent pressure is estimated from statewide and
  district-level data.
- Google ads have no text in the public dataset, so ad topics come from Meta only.
- CCES is a national survey, so the age patterns are national.
- The 2026 results are NCSBE's unofficial election-week file.
- Connected TV and broadcast TV are not covered, because neither ad library reports them.
