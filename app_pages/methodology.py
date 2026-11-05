"""
Methodology & Data Notes (UI_Design.md §6.6): sources, how each number is built, the War Room
model, its defaults, and limits. Defaults are read live from the same objects the model uses.
"""

import pandas as pd
import streamlit as st

from campaign_intel.config import CHANNEL_LABELS, CHANNELS
from campaign_intel.data.loaders import load_manifest
from campaign_intel.data.snapshot import has_table, read_table
from campaign_intel.model.assumptions import load_defaults
from campaign_intel.ui.topbar import render_topbar

render_topbar("Methodology & Data Notes")
_, center, _ = st.columns([1, 6, 1])
m = load_manifest()

with center:
    st.markdown("""
### 1. Data sources

| Source | What we use | Grain | Fidelity |
|---|---|---|---|
| **NCSBE precinct results** 2024 & 2026 (`results_pct_*`) | 2024 President (baseline), 2026 US Senate (backtest), district contests (precinct → district map) | Precinct × contest | **Aggregated** |
| **NCSBE voter_stats** 2022 & 2024, **history_stats** 2022 | Registration by party; who voted in 2022 | Precinct × party × demographics (already aggregated by NCSBE) | **Aggregated** |
| **Google Political Ads** (BigQuery public dataset) | Creatives targeting NC since Jul 2025, NC-focused advertisers' weekly spend, Google's own CD spend | Creative, advertiser-week, district | **Observed** (spend ranges) |
| **Meta Ad Library API** (`POLITICAL_AND_ISSUE_ADS`) | Ads delivered in NC since Jul 2026: text, spend/impression ranges, NC delivery share, age × gender delivery | Ad | **Observed** |
| **MEDSL 2022 US Senate** | County returns by vote method (cross-check) | County × mode | **Aggregated** |
| **CCES 2024 (UNC module)** | Past-24-hour news sources (social media / TV / newspaper / radio) and economic perceptions by age, weighted (`teamweight`), 95% CIs | Respondent (national, n = 1,000) | **Aggregated** |
| **TIGER 2024/2026 shapes** | CD (2026 map), SD & HD, counties — simplified GeoJSON | Polygon | — |
| **seeds/advertiser_sides.csv** | Team-curated advertiser → side (Dem / GOP / neutral) | Advertiser | — |

**Badges:** *Observed* = as published by the source. *Aggregated* = summed or weighted without extrapolation.
*Modeled* = depends on an allocation rule or the simulation.
""")
    st.markdown("""
### 2. How district numbers are built
- Every precinct's ballot lists its US House, NC Senate and NC House contests, so the **results files themselves** tell us
  which district each precinct (including absentee / early-vote pseudo-precincts) belongs to. Split precincts get
  fractional weights from their contest votes.
- **SD / HD** use the 2024 ballots (same lines in 2026). **CD** uses the 2026 ballots because Congress was redrawn in 2025
  and the CD shapes are the 2026 map. 2024 precincts renamed by 2026 and pseudo-precincts are spread by their county's
  district mix, which is exact for counties that sit inside one district.
- **Baseline margin** = 2024 presidential Dem margin (pts) × **expected midterm turnout** (the unit's 2024 vote × its county's
  2022/2024 ballots ratio). **Persuasion universe** = unaffiliated registrants. **Mobilization universe** = Dem registrants ×
  (1 − county 2022 Dem turnout rate).
- All four geographies (14 CD, 50 SD, 120 HD, 100 counties) sum to the same statewide totals (checked in `tests/`).
""")
    st.markdown("""
### 3. Ad spend in North Carolina
- Both libraries publish spend and impressions as **ranges**; we keep low / mid / high everywhere. Open-ended top tiers use
  mid = 1.5 × low and are shown as "≥ $low".
- **Google:** multi-state creatives count 1/*n* states toward NC (this matched Google's own NC totals far better than counting
  them in full); nationwide-only ads count 0. `advertiser_geo_spend` is lifetime, so it's only used to find NC-focused advertisers.
- **Meta:** NC spend = spend range × the ad's NC delivery share (`delivery_by_region`). Ads are pulled for
  **NC-focused pages** (≥ 50% of their spend delivered in NC), found by a capped newest-first scan of every political ad
  delivered in NC plus keyword scans; national pages' small NC slices are excluded from side totals.
- **Weekly series** spread each ad's NC spend evenly over its delivery days (Modeled). The trailing partial week is dropped.
- **Sides** come from the seed file; unmatched advertisers stay *Unclassified* (never guessed).
- **Themes** are a keyword classifier on Meta ad text (word-boundary matching); fundraising and GOTV ads are tagged and kept out
  of message analysis. Google creatives have no text in BigQuery.
""")
    st.markdown("### 4. War Room model — *a model, not a forecast*")
    st.markdown("For each unit *u* and audience *a* (persuasion / mobilization), dollars on channel *c* in week *w* build a decayed "
                "**adstock** of impressions, which feeds one **saturating reach** curve:")
    st.latex(r"S_{ua}=\sum_{c,w}\frac{\$_{ucaw}}{\text{CPM}_c}\cdot 1000\cdot\rho^{\,W-w}\qquad "
             r"R_{ua}=U_{ua}\left(1-e^{-k\,S_{ua}/U_{ua}}\right)")
    st.latex(r"\Delta V_{u}=\frac{1}{1+\lambda\,\text{opp}_u}\Big(R_{u,\text{pers}}\;p\;+\;R_{u,\text{mob}}\;t\,(2d-1)\Big)")
    st.markdown("""
- More money always helps, late money counts more (less decay), and each extra dollar in the same unit/audience buys less.
- **Monte Carlo (4,000 draws):** CPM per channel, *k*, *p*, *t*, ρ are drawn from triangular ranges; a shared statewide error
  N(0, σ) and independent unit errors N(0, σ_d) are applied in points of expected turnout. Baseline and plan share the same
  draws, so "baseline → plan" isn't noise. The win-probability whisker is the 10th–90th percentile of ad-effect size.
- **Scopes:** statewide = sum of all units > 0; single district = that unit > 0; chamber = seats won ≥ majority (26/50 SD, 61/120 HD, 8/14 CD).
- **Optimizer:** greedy, $10k steps, picks the line with the best expected gain **per dollar**; lines are capped at
  *N* impressions per person per week (default 5). For chamber scope each unit's votes are weighted by how close it is to
  flipping. It runs in well under 2 s even for 120 districts.
- **Opponent share of voice** is the observed statewide GOP share of partisan spend (no library reports spend by district),
  so with λ > 0 it scales every unit equally.
""")
    a = load_defaults()
    obs = read_table("cpm_observed").set_index("channel") if has_table("cpm_observed") else pd.DataFrame()
    rows = [{"Parameter": f"CPM — {CHANNEL_LABELS[c]}", "Low": a.cpm[c][0], "Mode": a.cpm[c][1], "High": a.cpm[c][2],
             "Basis": (f"Median NC CPM, {int(obs.loc[c, 'n_ads']):,} ads" if c in obs.index else "Assumption (no library data)")}
            for c in CHANNELS]
    rows += [
        {"Parameter": "Persuasion p (net votes / reached voter)", "Low": a.persuasion_p[0], "Mode": a.persuasion_p[1],
         "High": a.persuasion_p[2], "Basis": "Near-zero general-election persuasion (Kalla & Broockman 2018; Coppock, Hill & Vavreck 2020)"},
        {"Parameter": "Turnout lift t (per reached target)", "Low": a.turnout_t[0], "Mode": a.turnout_t[1],
         "High": a.turnout_t[2], "Basis": "Small digital turnout effects (Aggarwal et al. 2023)"},
        {"Parameter": "Weekly retention ρ", "Low": a.retention_rho[0], "Mode": a.retention_rho[1],
         "High": a.retention_rho[2], "Basis": "Ad effects decay within weeks (Hill, Lo, Vavreck & Zaller 2013)"},
        {"Parameter": "Saturation k", "Low": a.saturation_k[0], "Mode": a.saturation_k[1], "High": a.saturation_k[2], "Basis": "Assumption"},
        {"Parameter": "Statewide error σ (pts)", "Low": None, "Mode": a.sigma_state, "High": None, "Basis": "Assumption"},
        {"Parameter": "District error σ_d (pts)", "Low": None, "Mode": a.sigma_unit, "High": None, "Basis": "Assumption"},
        {"Parameter": "Dem share of mobilized Dems d", "Low": None, "Mode": a.dem_share_mobilized, "High": None, "Basis": "Assumption"},
    ]
    st.markdown("#### Default assumptions (live from `seeds/assumptions_default.yaml` + snapshot CPMs)")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.markdown("""
### 5. Backtest
The *2026 Backtest* page compares the baseline with the 2026 US Senate result from NCSBE's **unofficial** precinct file. It
shows how big the national environment was relative to anything paid digital can do, which is why the environment slider is
the first thing to set in the War Room.

### 6. Limits
- The War Room's effect sizes are assumptions informed by the literature, not estimates from NC data.
- CCES is a national sample; it describes voters like NC's, not NC voters.
- Ad libraries miss TV, mail and field; CTV costs are an assumption. Google creatives have no text, so themes are Meta-only.
- District ad spend isn't published (except Google's CD totals), so opponent pressure is statewide.

### 7. Privacy & ethics
- No individual voter records reach the app: NCSBE files are already aggregated by precinct × party × demographics.
- Tokens live in `.env` (git-ignored) and are used only by the snapshot builder; ad snapshot URLs are stored without tokens.
""")
    if m:
        st.caption(f"Snapshot built {m.get('built_at', '?')} UTC · Google report updated {m.get('google_report_updated', '?')}")
