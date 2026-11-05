"""
2026 Backtest: the War Room's baseline (2024 presidential margins at midterm turnout) versus the
2026 US Senate result as posted by NCSBE (unofficial precinct file), by unit.
"""

from dataclasses import replace

import numpy as np
import streamlit as st

from campaign_intel.data.loaders import load_manifest, load_statewide, load_units
from campaign_intel.model.assumptions import load_defaults
from campaign_intel.model.engine import RaceContext, simulate
from campaign_intel.model.optimizer import optimize
from campaign_intel.ui.components import chart_card_header, insight, kpi_card
from campaign_intel.ui.topbar import render_topbar
from campaign_intel.viz.charts import backtest_scatter
from campaign_intel.viz.maps import choropleth

render_topbar("2026 Backtest — Baseline vs. Actual Result")
theme = st.session_state.get("theme", "dark")
unit_type, geo_mode = st.session_state.get("unit_type", "cd"), st.session_state.get("geo_mode", "district")
geo_key = "county" if geo_mode == "county" else unit_type
sw = load_statewide()
units = load_units(unit_type, geo_mode).dropna(subset=["actual26_margin_pct"]).copy()
units["swing"] = units["actual26_margin_pct"] - units["dem_margin_pct"]
units["flip"] = (units["dem_margin_pct"] < 0) & (units["actual26_margin_pct"] > 0)
units["una_share"] = units["reg_una"] / units["registered_voters"] * 100

base_pct = (sw["pres24_dem"] - sw["pres24_rep"]) / sw["pres24_total"] * 100
act_pct = (sw["sen26_dem"] - sw["sen26_rep"]) / sw["sen26_total"] * 100
swing = act_pct - base_pct
file_date = sw.get("sen26_file_date", "")

st.info(f"2026 results are **unofficial**: NCSBE precinct file `results_pct_20261103` as posted {file_date}. "
        "Numbers may change at canvass. The War Room's assumptions were not fitted to this result.", icon="🗳️")


@st.cache_data(show_spinner=False)
def model_check(geo: str, ut: str, gm: str) -> dict:
    u = load_units(ut, gm)
    a = load_defaults()
    ctx = RaceContext("statewide", geo, None, 8, 2_000_000, u)
    plan, _ = optimize(None, ctx, a)
    r0 = simulate(plan, ctx, a, n_draws=3000)
    r1 = simulate(plan, ctx, replace(a, env_shift_pts=swing), n_draws=3000)
    turnout = float(u["expected_turnout"].sum())
    return {"base_wp": r0.baseline_win_prob, "plan_wp": r0.win_prob, "plan_votes": r0.total_delta_votes,
            "plan_pts": r0.total_delta_votes / turnout * 100, "env_wp": r1.baseline_win_prob}


mc = model_check(geo_key, unit_type, geo_mode)

c1, c2, c3, c4 = st.columns(4, gap="medium")
with c1:
    kpi_card("Baseline (2024 President)", f"Dem {base_pct:+.1f}", fidelity="aggregated",
             band=f"Model's no-spend win probability: {mc['base_wp']:.0%}")
with c2:
    kpi_card("Actual 2026 US Senate", f"Dem {act_pct:+.1f}", fidelity="observed",
             band=f"{sw['sen26_dem_candidate']} {sw['sen26_dem']:,} – {sw['sen26_rep_candidate']} {sw['sen26_rep']:,}")
with c3:
    kpi_card("Implied environment shift", f"{swing:+.1f} pts", fidelity="modeled",
             band=f"With this shift the model gives {mc['env_wp']:.0%} — the environment slider is the lever that mattered")
with c4:
    kpi_card("Units that flipped to Dem", f"{int(units['flip'].sum())} of {len(units)}", fidelity="observed",
             band=f"Swing range {units['swing'].min():+.0f} to {units['swing'].max():+.0f} pts")

st.write("")
b1, b2 = st.columns([6, 6], gap="medium")
with b1, st.container(border=True):
    chart_card_header("Baseline vs actual, by unit", "Dashed diagonal = no change from 2024 · above it = Dem gained",
                      fidelity="observed")
    st.altair_chart(backtest_scatter(units, theme, label="Unit"), width="stretch")
with b2, st.container(border=True):
    chart_card_header("Where the swing happened", "2026 Senate Dem margin minus 2024 presidential Dem margin (pts)",
                      fidelity="observed")
    st.altair_chart(choropleth(geo_key, units, "swing", "Swing to Dem (pts)", scale="diverging", theme=theme, fmt="+.1f",
                               extra_tooltips=[("dem_margin_pct", "2024 baseline", "+.1f"),
                                               ("actual26_margin_pct", "2026 actual", "+.1f")],
                               swing_pts=None, selectable=False, domain_max=float(units["swing"].abs().max())),
                    width="stretch")

with st.container(border=True):
    chart_card_header("What this means for the War Room", "Computed from the snapshot", fidelity="modeled")
    corr_una = float(np.corrcoef(units["una_share"], units["swing"])[0, 1]) if len(units) > 2 else np.nan
    corr_base = float(np.corrcoef(units["dem_margin_pct"], units["swing"])[0, 1]) if len(units) > 2 else np.nan
    sd = units["swing"].std()
    insight(f"A $2M optimized digital plan is worth ≈ {mc['plan_pts']:.2f} pts in the model; the observed swing was {swing:+.1f} pts",
            f"Default assumptions: {mc['plan_votes']:,.0f} net votes, win probability {mc['base_wp']:.0%} → {mc['plan_wp']:.0%}. "
            "Paid digital can only decide races that the environment leaves close.", tone="dem")
    insight(f"The swing was {'fairly uniform' if sd < 6 else 'uneven'}: σ = {sd:.1f} pts across units",
            f"Correlation of swing with unaffiliated share: {corr_una:+.2f}; with the 2024 margin: {corr_base:+.2f}. "
            "A uniform swing supports the model's single statewide error term; the unit term (σ_d) covers the rest.")
    st.dataframe(units.sort_values("swing", ascending=False)[["name", "dem_margin_pct", "actual26_margin_pct", "swing",
                                                              "una_share", "flip"]],
                 hide_index=True, width="stretch", height=300,
                 column_config={"name": "Unit", "dem_margin_pct": st.column_config.NumberColumn("2024 baseline", format="%+.1f"),
                                "actual26_margin_pct": st.column_config.NumberColumn("2026 actual", format="%+.1f"),
                                "swing": st.column_config.NumberColumn("Swing", format="%+.1f"),
                                "una_share": st.column_config.NumberColumn("Unaffiliated %", format="%.1f"),
                                "flip": "Flipped"})
    st.caption("Caveats: CD results use the 2026 congressional map (2025 redraw); SD/HD lines were unchanged; counties are exact. "
               "2024 precincts renamed by 2026 and early-vote pseudo-precincts are spread by county mix. "
               f"Snapshot built {load_manifest().get('built_at', '')[:16]} UTC.")
