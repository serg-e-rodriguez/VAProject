# NC Campaign Ad Intelligence & War Room

A Streamlit + Altair dashboard for the **2026 North Carolina US Senate race** from the Democratic side:
where political ad money is going, who sees which messages, what the opponent is doing, who the
persuadable and mobilizable voters are, and, in the **War Room**, how to allocate a remaining budget
across districts, channels, audiences and weeks, with honest uncertainty.

Every number in the app comes from real public data, frozen in a local snapshot:

| Source | Used for |
|---|---|
| NCSBE precinct results (2024, 2026), voter_stats (2022, 2024), history_stats (2022) | Baselines, district roll-ups, registration universes, 2022 turnout, 2026 backtest |
| Google Political Ads (BigQuery public dataset) | NC-targeted creatives, NC-focused weekly spend, Google's district spend |
| Meta Ad Library API | Ad text, spend/impression ranges, NC delivery share, age × gender delivery |
| MEDSL 2022 US Senate (`data/senate_2022.csv`) | County cross-check, vote-method chart |
| CCES 2024 UNC module (`data/CCES24_UNC_OUTPUT.csv`) | News-source use and economic perceptions by age (weighted, 95% CIs) |

## Quickstart

```bash
uv sync
uv run streamlit run app.py
```

The committed snapshot in `data/cache/` is enough to run the app. No credentials are needed.

## Rebuilding the data snapshot

Needs `.env` (see `.env.example`) with `GCP_PROJECT_ID` (BigQuery access via
`gcloud auth application-default login`) and a Meta Ad Library `META_AD_TOKEN`.

```bash
uv run python -m campaign_intel.ingest.build_snapshot                 # everything (~30-60 min, mostly Meta)
uv run python -m campaign_intel.ingest.build_snapshot --skip-meta     # NCSBE + Google only
uv run python -m campaign_intel.ingest.build_snapshot --skip-ncsbe --skip-google --skip-meta   # re-derive
```

Raw downloads are cached in `data/raw/` (git-ignored). The build writes `data/cache/*.parquet` and
`manifest.json`; the app's freshness chip reads the manifest.

## Pages

- **Overview**: NC spend, share of voice, the electoral map (2024 margins), weekly spend by side, top advertisers.
- **Audience Intelligence**: theme × age delivery (Us / Opponent / Gap), CCES news sources by age, computed message-gap callouts.
- **Opponent Tracker**: GOP-side spend and share of voice, a filterable library of real GOP-side creatives, committee ledger, alerts.
- **Electorate & Turnout**: registration, persuasion and mobilization universes, and 2022 turnout by district or county.
- **War Room** (main feature): allocation builder, a 4,000-draw Monte Carlo, an optimizer, where-the-votes-come-from map,
  pacing, channel efficiency, diminishing-returns curves, sensitivity analysis and saved scenarios.
  Scopes: statewide, a single district, or chamber majority (CD/SD/HD).
- **2026 Backtest**: the baseline against NCSBE's (unofficial) 2026 Senate results, by unit.
- **Methodology**: every source, rule and default assumption (read live from the code).

## Project layout

```
app.py                      navigation + theme
app_pages/                  one file per page (layout only)
src/campaign_intel/
  ingest/                   ncsbe.py, google_ads.py, meta_ads.py, build_snapshot.py
  data/                     snapshot.py (parquet reader), loaders.py (cached page loaders)
  processing/               ads.py (sides, themes, weekly), survey.py (CCES), themes.py, crosswalk.py (MEDSL)
  model/                    engine.py (Monte Carlo), optimizer.py, assumptions.py, scenarios.py (SQLite)
  viz/                      charts.py, maps.py, themes.py (Altair)
  ui/                       topbar, KPI cards, styles
seeds/                      advertiser_sides.csv, theme_keywords.yaml, assumptions_default.yaml
tests/                      data reconciliation, model properties, chart specs
notebooks/                  EDA / sanity notebooks on the snapshot
```

## Tests

```bash
uv run pytest
```

The tests check that the snapshot reproduces the certified 2024 presidential totals, that all four geographies
reconcile to the same statewide totals, and that the model is monotone, concave, reproducible, scope-correct
and fast (under 5 s for 120 districts).

## Known limits

The War Room is a model, not a forecast. Its effect sizes are literature-informed assumptions. Ad libraries
don't publish spend by district, so opponent pressure is statewide. Google creatives have no text, so themes come
from Meta only. CCES is a national sample. The 2026 results are NCSBE's unofficial election-week file.
