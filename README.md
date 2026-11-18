# NC Race Intelligence & War Room

A Streamlit + Altair dashboard for the **2026 North Carolina US Senate and US House races** from the Democratic
side: where political ad money is going, what Republicans are running and who it reaches, and, in the
**War Room**, where to spend a budget and what the model predicts it buys.

Every number comes from real public data, frozen in a local snapshot (`data/cache/`, committed):

| Source | Used for |
|---|---|
| NCSBE precinct results (2024, 2026), voter_stats (2022, 2024), history_stats (2022) | Starting margins, registration and turnout, audience sizes, 2026 results |
| Google Political Ads (BigQuery public dataset) | NC race ads, county-targeted spend, Google's district totals |
| Meta Ad Library API | Ad text, spend and impression ranges, NC delivery, age × gender reach |
| MEDSL 2022 US Senate (`data/senate_2022.csv`) | 2022 Senate results by county and district |
| CCES 2024 UNC module (`data/CCES24_UNC_OUTPUT.csv`) | News-source use and economic perceptions by age |

## Run it locally

You need [uv](https://docs.astral.sh/uv/) (it installs the right Python, 3.12 or newer, for you).

```bash
git clone <repo-url> && cd VAProject
uv sync                              # creates .venv and installs everything from uv.lock
cp .env.example .env                 # optional: add keys (see below)
uv run streamlit run app.py          # opens http://localhost:8501
```

No credentials are needed to run the app: the committed snapshot has all the data. The keys in `.env`
only switch on optional features. Use the sidebar to pick the race (US Senate or US House) and a page.

## The `.env` file

`.env` sits in the project root, is loaded automatically at start-up (python-dotenv), and is git-ignored.
Start from `.env.example`. Restart Streamlit after changing it.

| Variable | Needed for | Without it |
|---|---|---|
| `GEMINI_API` | War Room step 5 (Gemini analysis, questions, "Let Gemini change the plan"). A Google AI Studio API key. `GEMINI_KEY`, `GEMINI_API_KEY` or `GOOGLE_API_KEY` also work. | The Gemini buttons say Gemini is not configured. Everything else works. |
| `GEMINI_MODEL` | Optional. Comma-separated Gemini models to try in order. Default: `gemini-3.5-flash,gemini-3.5-flash-lite,gemini-3.8-flash`. | The default list is used. |
| `META_AD_TOKEN` | Checking Meta ad links before they are shown (War Room steps 2–3, Opponent Tracker), and rebuilding the Meta part of the snapshot. A Meta Ad Library API access token for an identity-verified account. | Meta ad cards still show, but without a link (it can't be confirmed). Google links are checked without a key. |
| `GCP_PROJECT_ID` | Rebuilding the Google part of the snapshot (BigQuery). Your Google Cloud project for query billing. | Only matters for a rebuild. |

BigQuery uses Google's Application Default Credentials: run `gcloud auth application-default login` once, or
set `GOOGLE_APPLICATION_CREDENTIALS` to a service-account key file. Keys are never logged; the Gemini key is sent
only in a request header.

Example:

```dotenv
GEMINI_API=your-ai-studio-key
META_AD_TOKEN=your-meta-ad-library-token
GCP_PROJECT_ID=your-gcp-project
# GEMINI_MODEL=gemini-3.5-flash-lite,gemini-3.5-flash
```

Gemini models can be busy (HTTP 503) or slow; the app retries and falls back to the next model, so an analysis
can take up to a minute or two.

## Pages

- **Overview**: race spend by side, share of voice, the map, weekly spend, top advertisers.
- **Region Analysis**: pick a county (Senate) or district (House) on the map to open its Audience Analysis:
  registration and turnout by age, race and gender, why it leans the way it does, and who advertises there.
- **Opponent Tracker**: Republican spend by week and platform, who pays for it, what they say and who sees it,
  and their latest ads. Only Republican-side ads are shown, each labeled with its campaign, party committee or
  PAC, and only links that were checked.
- **War Room**, six steps, planning "as of" a date before Election Day (nothing after that date is used):
  1. **Budget & spending**: budget, goal, and what both sides have spent by area. *Advanced:* set spending for
     any area as a % of the budget or in dollars.
  2. **Opponent messaging**: Republican themes, who they reach, their biggest ads, and how strongly their ads
     blunt ours in the model.
  3. **Our messaging**: pick up to three message themes; compare predicted votes by message; Democrats'
     most-seen ads.
  4. **Plan & prediction**: the model's plan (area × platform × goal), predicted win chance and net votes,
     returns by platform, win chance vs budget, and a plan editor.
  5. **Gemini**: analysis and questions; with your permission, Gemini can change spending by area, messages,
     and goals/platforms. Changes are checked, scored by the model, applied only if they score at least as
     well, and can be undone.
  6. **Recommended spending**: the final plan from all the settings above, compared with your edited plan and
     with the model's unconstrained choice, with a CSV download.

## Rebuilding the data snapshot

Only needed for fresh data. Needs the `.env` keys above (`META_AD_TOKEN`, `GCP_PROJECT_ID`) and BigQuery access.

```bash
uv run python -m campaign_intel.ingest.build_snapshot                       # everything (~30-60 min, mostly Meta)
uv run python -m campaign_intel.ingest.build_snapshot --skip-meta --skip-google   # NCSBE + re-derive, no API keys
uv run python -m campaign_intel.ingest.build_snapshot --refresh             # re-download raw NCSBE / Meta files
```

Raw downloads are cached in `data/raw/` (git-ignored). The build writes `data/cache/*.parquet` and
`manifest.json`. Which advertisers count as Democratic or Republican is set in `seeds/advertiser_sides.csv`;
change it and rebuild to re-classify ads.

## Project Layout

```
app.py                      sidebar: race picker, navigation, theme
app_pages/                  overview.py, regions.py, opponent.py, war_room.py
src/campaign_intel/
  config.py                 paths, .env loading, race definitions
  ingest/                   ncsbe.py, google_ads.py, meta_ads.py, build_snapshot.py
  data/                     snapshot.py (parquet reader), loaders.py (cached loaders), ad_links.py (link checks), bq.py
  processing/               ads.py (sides, themes, weekly), survey.py (CCES), themes.py, crosswalk.py
  model/                    engine.py (Monte Carlo), optimizer.py, warroom.py, assumptions.py, scenarios.py
  war_room_service.py       War Room: plan, predict, opponent and message inputs, Gemini client
  viz/                      charts.py, maps.py, themes.py (Altair)
  ui/                       components and styles
seeds/                      advertiser_sides.csv, theme_keywords.yaml, assumptions_default.yaml
tests/                      data reconciliation, model properties, War Room and Opponent Tracker pages
notebooks/                  EDA and sanity notebooks on the snapshot
```

## Tests

```bash
uv run pytest
```

The tests check that the snapshot reconciles to certified totals, that the model is monotone, concave and
reproducible, and they drive the War Room and Opponent Tracker pages headlessly (Streamlit AppTest). They
make no network calls: Gemini and the link checks are mocked.

## Known Limits

The War Room is a model, not a forecast: ad-effect sizes, costs and decay are set ranges, so use it to compare
plans. Message themes enter only through who their ads reach and how much Republicans spend on them; how
persuasive an ad is is not modeled. Meta does not report spend below state level, so only county-targeted
Google ads can be mapped to areas. Google ads carry no text, so themes come from Meta only. Ad-library spend and
impressions are reported as ranges (midpoints are used). The CCES sample is national. The 2026 results are
NCSBE's unofficial election-week file.
