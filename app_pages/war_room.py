"""
War Room (UI_Design.md §6.5, PROJECT_DESIGN.md §7): plan the remaining budget across
geography x channel x audience x week, see what it does to the race, and let the optimizer
recommend the next dollar. All maths is in campaign_intel.model; this file is layout.
"""

from __future__ import annotations

import hashlib
import io
import json

import numpy as np
import pandas as pd
import streamlit as st

from campaign_intel.config import (
    AUDIENCE_LABELS,
    AUDIENCES,
    CHANNEL_LABELS,
    CHANNELS,
    DEFAULT_BUDGET,
    DEFAULT_WEEKS,
)
from campaign_intel.data.loaders import esc, fmt_money, load_units
from campaign_intel.model.assumptions import Assumptions, apply_preset, load_defaults
from campaign_intel.model.engine import (
    CHAMBER_MAJORITY,
    RaceContext,
    clean_allocation,
    expected_deltas,
    response_curve,
    sensitivity,
    simulate,
)
from campaign_intel.model.optimizer import optimize
from campaign_intel.model.scenarios import delete_scenario, list_scenarios, save_scenario
from campaign_intel.state import set_state
from campaign_intel.ui.components import chart_card_header, insight, kpi_card, model_ribbon
from campaign_intel.ui.topbar import render_topbar
from campaign_intel.viz.charts import (
    outcome_histogram,
    ranked_bar,
    response_curves,
    stacked_weeks,
    tornado,
    win_prob_bar,
)
from campaign_intel.viz.maps import choropleth

render_topbar("War Room — Budget Allocator & Outcome Simulator")
model_ribbon()

ss = st.session_state
theme = ss.get("theme", "dark")
scope, geo_mode, unit_type = ss.get("scope", "statewide"), ss.get("geo_mode", "district"), ss.get("unit_type", "cd")
geo_key = "county" if geo_mode == "county" else unit_type
units = load_units(unit_type, geo_mode)
unit_ids = units["unit_id"].tolist()
names = dict(zip(units["unit_id"], units["name"]))
EMPTY = pd.DataFrame({"unit_id": pd.Series(dtype=str), "channel": pd.Series(dtype=str),
                      "audience": pd.Series(dtype=str), "week": pd.Series(dtype=int),
                      "dollars": pd.Series(dtype=float), "locked": pd.Series(dtype=bool)})

# ----------------------------------------------------------------------------- assumptions state
SLIDERS = {  # key: (label, min, max, step, fmt, getter)
    "wr_p": ("Persuasion: net votes per reached persuadable", 0.0, 0.01, 0.0005, "%.4f", lambda a: a.persuasion_p[1]),
    "wr_t": ("Mobilization: turnout lift per reached target", 0.0, 0.02, 0.0005, "%.4f", lambda a: a.turnout_t[1]),
    "wr_rho": ("Weekly retention of ad effects (ρ)", 0.2, 0.95, 0.05, "%.2f", lambda a: a.retention_rho[1]),
    "wr_k": ("Saturation: response per impression (k)", 0.01, 0.30, 0.005, "%.3f", lambda a: a.saturation_k[1]),
    "wr_env": ("National environment vs. 2024 baseline (pts, + = Dem)", -15.0, 25.0, 0.5, "%+.1f", lambda a: a.env_shift_pts),
    "wr_sig_s": ("Statewide error σ (pts)", 1.0, 8.0, 0.5, "%.1f", lambda a: a.sigma_state),
    "wr_sig_u": ("District extra error σ_d (pts)", 0.5, 6.0, 0.5, "%.1f", lambda a: a.sigma_unit),
    "wr_lambda": ("Opponent share-of-voice dampening (λ)", 0.0, 1.0, 0.1, "%.1f", lambda a: a.opp_lambda),
    "wr_d": ("Dem share among mobilized Dem registrants (d)", 0.5, 1.0, 0.01, "%.2f", lambda a: a.dem_share_mobilized),
}
for c in CHANNELS:
    SLIDERS[f"wr_cpm_{c}"] = (f"{CHANNEL_LABELS[c]} CPM ($)", 1.0, 80.0, 0.5, "$%.2f", lambda a, c=c: a.cpm[c][1])


def _set_widgets_from(a: Assumptions) -> None:
    for key, (_, lo, hi, _, _, get) in SLIDERS.items():
        ss[key] = float(min(hi, max(lo, get(a))))
    ss.wr_ref = a


def _on_preset() -> None:
    name = {"Default": "default", "Conservative": "conservative", "Optimistic": "optimistic"}[ss.get("wr_preset") or "Default"]
    keep = current_assumptions() if "wr_p" in ss else load_defaults()
    _set_widgets_from(apply_preset(keep, name))


def current_assumptions() -> Assumptions:
    """Slider modes, with low/high scaled from the active preset's triangle shape."""
    ref: Assumptions = ss.wr_ref

    def tri(mode, t):
        if t[1] <= 0:
            return (0.0, mode, mode * 2.5)
        return (mode * t[0] / t[1], mode, mode * t[2] / t[1])

    return Assumptions(
        cpm={c: tri(ss[f"wr_cpm_{c}"], ref.cpm[c]) for c in CHANNELS},
        saturation_k=tri(ss.wr_k, ref.saturation_k), persuasion_p=tri(ss.wr_p, ref.persuasion_p),
        turnout_t=tri(ss.wr_t, ref.turnout_t), retention_rho=tuple(min(0.99, x) for x in tri(ss.wr_rho, ref.retention_rho)),
        opp_lambda=ss.wr_lambda, sigma_state=ss.wr_sig_s, sigma_unit=ss.wr_sig_u, env_shift_pts=ss.wr_env,
        dem_share_mobilized=ss.wr_d,
    )


# Streamlit drops widget keys when you leave the page: keep shadow copies and restore them.
PERSIST = list(SLIDERS) + ["wr_budget", "wr_weeks", "wr_preset", "wr_opt_channels", "wr_freq"]
if "wr_ref" not in ss:
    _set_widgets_from(load_defaults())
for _k in PERSIST:
    if _k not in ss and f"_{_k}" in ss:
        ss[_k] = ss[f"_{_k}"]
ss.setdefault("wr_budget", DEFAULT_BUDGET)
ss.setdefault("wr_weeks", DEFAULT_WEEKS)
ss.setdefault("wr_freq", 5.0)
ss.setdefault("wr_opt_channels", list(CHANNELS))


# ----------------------------------------------------------------------------- plan state
def get_plan() -> pd.DataFrame:
    return ss.setdefault("wr_plans", {}).get(geo_key, EMPTY.copy())


def set_plan(df: pd.DataFrame | None) -> None:
    df = EMPTY.copy() if df is None or len(df) == 0 else df
    if "locked" not in df.columns:
        df = df.assign(locked=False)
    df = df[list(EMPTY.columns)].reset_index(drop=True)
    df["locked"] = df["locked"].fillna(False).astype(bool)
    ss.setdefault("wr_plans", {})[geo_key] = df
    ss["wr_ver"] = ss.get("wr_ver", 0) + 1
    ss.pop("wr_diff", None)
    ss.pop("wr_sens", None)


def starter_plan(budget: float, weeks: int) -> pd.DataFrame:
    """Editable starting point: 40% of budget, closest 3 units, Meta + YouTube, last 3 weeks."""
    close = units.assign(a=units["dem_margin_pct"].abs()).nsmallest(3, "a")["unit_id"].tolist()
    if scope == "district" and ss.get("target_unit"):
        close = [ss.target_unit]
    rows = []
    per = 0.4 * budget / (len(close) * 2 * 2 * 3)
    for u in close:
        for ch in ["meta", "youtube"]:
            for aud in AUDIENCES:
                for w in range(max(1, weeks - 2), weeks + 1):
                    rows.append({"unit_id": u, "channel": ch, "audience": aud, "week": w,
                                 "dollars": round(per, -3), "locked": False})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- race setup
with st.container(border=True):
    s1, s2, s3, s4 = st.columns([1.3, 1.2, 1.6, 1.6], vertical_alignment="bottom")
    budget = s1.number_input("Budget to allocate ($)", min_value=50_000.0, max_value=50_000_000.0,
                             step=100_000.0, format="%.0f", key="wr_budget")
    weeks = s2.slider("Weeks to Election Day", 2, 16, key="wr_weeks")
    target = None
    if scope == "district":
        default_t = ss.get("target_unit") or units.assign(a=units["dem_margin_pct"].abs()).nsmallest(1, "a")["unit_id"].iloc[0]
        target = s3.selectbox("Target district", unit_ids, index=unit_ids.index(default_t) if default_t in unit_ids else 0,
                              format_func=lambda u: f"{names[u]} ({units.set_index('unit_id').loc[u, 'dem_margin_pct']:+.1f})")
        if target != ss.get("target_unit"):
            set_state(target_unit=target)
    elif scope == "chamber":
        s3.markdown(f"**Goal:** majority of {len(units)} seats — **{CHAMBER_MAJORITY.get(unit_type, len(units)//2+1)}** needed")
    else:
        s3.markdown(f"**Goal:** win the statewide US Senate race (sum of all {len(units)} units)")
    s4.pills("Assumption preset", ["Default", "Conservative", "Optimistic"], default="Default", key="wr_preset",
             on_change=_on_preset, help="Conservative = smaller effects, higher CPMs. Optimistic = the reverse.")

    with st.expander("⚙️ Model assumptions (all editable — every one is uncertain)", expanded=False):
        cols = st.columns(3)
        groups = [["wr_p", "wr_t", "wr_rho", "wr_k"], ["wr_env", "wr_sig_s", "wr_sig_u", "wr_lambda", "wr_d"],
                  [f"wr_cpm_{c}" for c in CHANNELS]]
        heads = ["**Ad effects**", "**Race environment & error**", "**Costs (CPM)**"]
        for col, keys, head in zip(cols, groups, heads):
            with col:
                st.markdown(head)
                for k in keys:
                    lab, lo, hi, step, fmt, _ = SLIDERS[k]
                    st.slider(lab, lo, hi, step=step, format=fmt, key=k)
        st.caption("Sliders set each parameter's most-likely value; the Monte Carlo draws around it using the preset's "
                   "low–high range. CPM defaults are the median observed NC CPM per channel from the ad libraries "
                   "(CTV has no library data, so it is an assumption).")

a = current_assumptions()
ctx = RaceContext(scope=scope if not (scope == "chamber" and geo_mode == "county") else "statewide",
                  unit_type=geo_key, target_unit=target, weeks=int(weeks), budget=float(budget), units=units)

if geo_key not in ss.setdefault("wr_plans", {}):
    set_plan(starter_plan(budget, weeks))


@st.cache_data(show_spinner=False, max_entries=64)
def run_sim(alloc_json: str, ctx_key: str, a_json: str, _ctx: RaceContext, _a: Assumptions):
    return simulate(pd.read_json(io.StringIO(alloc_json), orient="split"), _ctx, _a, n_draws=4000)


def keys_for(plan: pd.DataFrame) -> tuple[str, str, str]:
    aj = clean_allocation(plan, ctx.weeks)[["unit_id", "channel", "audience", "week", "dollars"]].to_json(orient="split")
    ck = f"{ctx.scope}|{ctx.unit_type}|{ctx.target_unit}|{ctx.weeks}|{ctx.budget}"
    return aj, ck, json.dumps(a.to_dict(), sort_keys=True)


# ----------------------------------------------------------------------------- layout skeleton
kpi_row = st.container()
col_builder, col_outcome = st.columns([6, 6], gap="medium")

with col_builder, st.container(border=True):
    chart_card_header("Allocation builder", "One row per line item: unit · channel · audience · week · dollars. "
                      "Tick 🔒 to protect a row from the optimizer.", fidelity="modeled")
    plan_src = get_plan()
    edited = st.data_editor(
        plan_src, key=f"wr_editor_{geo_key}_{ss.get('wr_ver', 0)}", num_rows="dynamic", width="stretch", height=300,
        column_config={
            "unit_id": st.column_config.SelectboxColumn("Unit", options=unit_ids, required=True),
            "channel": st.column_config.SelectboxColumn("Channel", options=CHANNELS, required=True),
            "audience": st.column_config.SelectboxColumn("Audience", options=AUDIENCES, required=True),
            "week": st.column_config.NumberColumn("Week", min_value=1, max_value=int(weeks), step=1, required=True),
            "dollars": st.column_config.NumberColumn("Dollars", min_value=0, step=5_000, format="dollar", required=True),
            "locked": st.column_config.CheckboxColumn("🔒", default=False),
        },
    )
    plan = edited.copy()
    plan["locked"] = plan["locked"].fillna(False).astype(bool)

    def _norm(d):
        return d.reset_index(drop=True).astype(str).to_json()
    if _norm(plan) != _norm(plan_src):  # commit edits so they survive reruns and page changes
        set_plan(plan)
        st.rerun()

    spent = float(clean_allocation(plan, ctx.weeks)["dollars"].sum())
    bad_units = sorted(set(plan["unit_id"].dropna()) - set(unit_ids))
    if bad_units:
        st.warning(f"{len(bad_units)} row(s) reference units not in this geography and are ignored: {', '.join(bad_units[:5])}")
    if spent > budget + 1:
        st.error(esc(f"Plan is over budget by {fmt_money(spent - budget)}."))
    st.progress(min(1.0, spent / budget), text=esc(f"Allocated {fmt_money(spent)} of {fmt_money(budget)}"))

    o1, o2 = st.columns([1.4, 1])
    allowed = o1.multiselect("Channels the optimizer may use", CHANNELS, format_func=CHANNEL_LABELS.get,
                             key="wr_opt_channels")
    freq = o2.number_input("Max impressions / person / week / channel", 1.0, 20.0, step=1.0, key="wr_freq",
                           help="Caps each line item so money isn't poured past sensible frequency.")
    b1, b2 = st.columns(2)
    b3, b4 = st.columns(2)
    if b1.button("⚡ Optimize remaining", type="primary", width="stretch",
                 help="Greedy: add the remaining budget $10k at a time where the next dollar buys the most."):
        rec, diff = optimize(plan, ctx, a, step=10_000, channels=allowed or CHANNELS, cap_mult=freq)
        ss.wr_diff, ss.wr_rec = diff, rec
    if b2.button("♻️ Rebuild from scratch", width="stretch", help="Re-plan the whole budget, keeping only 🔒 rows."):
        rec, diff = optimize(plan, ctx, a, step=10_000, channels=allowed or CHANNELS, cap_mult=freq,
                             locks=plan[plan["locked"]], rebuild=True)
        ss.wr_diff, ss.wr_rec = diff, rec
    if b3.button("Starter plan", width="stretch"):
        set_plan(starter_plan(budget, weeks)); st.rerun()
    if b4.button("Clear", width="stretch"):
        set_plan(None); st.rerun()

    if "wr_diff" in ss:
        diff = ss.wr_diff
        if diff.empty:
            st.info("Nothing to add: either the budget is used up or every line is at its frequency cap.")
        else:
            add = diff["delta_dollars"].sum()
            st.markdown(esc(f"##### 💡 Recommended additions — {fmt_money(add)} for ≈ **{diff['marginal_votes'].sum():,.0f}** "
                        "expected net votes"))
            show = diff.assign(unit=diff["unit_id"].map(names), channel=diff["channel"].map(CHANNEL_LABELS),
                               per_vote=diff["delta_dollars"] / diff["marginal_votes"].replace(0, np.nan))
            st.dataframe(show[["unit", "channel", "audience", "week", "delta_dollars", "marginal_votes", "per_vote"]],
                         hide_index=True, width="stretch", height=220,
                         column_config={"unit": "Unit", "delta_dollars": st.column_config.NumberColumn("+ Dollars", format="dollar"),
                                        "marginal_votes": st.column_config.NumberColumn("+ Net votes", format="%.0f"),
                                        "per_vote": st.column_config.NumberColumn("$ / vote", format="dollar")})
            left = budget - (spent + add)
            if left >= 10_000:
                st.caption(esc(f"{fmt_money(left)} left unspent: every remaining line hit its frequency cap. "
                           "Raise the cap, allow more channels/units, or switch scope."))
            c1, c2 = st.columns(2)
            if c1.button("✅ Accept recommendation", type="primary", width="stretch"):
                rec = ss.wr_rec.merge(plan[plan["locked"]][["unit_id", "channel", "audience", "week", "locked"]],
                                      on=["unit_id", "channel", "audience", "week"], how="left")
                set_plan(rec); st.rerun()
            if c2.button("Dismiss", width="stretch"):
                ss.pop("wr_diff", None); st.rerun()

# ----------------------------------------------------------------------------- simulate
aj, ck, ajs = keys_for(plan)
with st.spinner("Simulating 4,000 elections…"):
    res = run_sim(aj, ck, ajs, ctx, a)
lines = expected_deltas(plan, ctx, a)

with kpi_row:
    k1, k2, k3, k4, k5 = st.columns(5, gap="small")
    with k1:
        kpi_card("Win probability", f"{res.win_prob:.1%}", delta=f"{(res.win_prob - res.baseline_win_prob) * 100:+.1f} pts",
                 good_direction="up", fidelity="modeled",
                 band=f"No-spend baseline {res.baseline_win_prob:.1%} · effect range {res.win_prob_interval[0]:.0%}–{res.win_prob_interval[1]:.0%}")
    with k2:
        if ctx.scope == "chamber":
            kpi_card("Expected seats", f"{res.expected_outcome:.1f}", delta=f"{res.expected_outcome - res.baseline_expected_outcome:+.2f}",
                     good_direction="up", fidelity="modeled", band=f"Majority = {ctx.majority} · baseline {res.baseline_expected_outcome:.1f}")
        else:
            kpi_card("Expected margin", f"{res.expected_outcome:+,.0f}", delta=f"{res.expected_outcome - res.baseline_expected_outcome:+,.0f} votes",
                     good_direction="up", fidelity="modeled", band=f"Baseline {res.baseline_expected_outcome:+,.0f} (2024 pres → midterm turnout)")
    with k3:
        lo, hi = res.total_delta_interval
        kpi_card("Net votes from plan", f"{res.total_delta_votes:,.0f}", delta=None, fidelity="modeled",
                 band=f"80% range {lo:,.0f} – {hi:,.0f} (effect-size uncertainty)")
    with k4:
        cpv = res.cost_per_net_vote
        kpi_card("Cost per net vote", fmt_money(cpv) if np.isfinite(cpv) else "—", fidelity="modeled",
                 band="Counted votes only (target district in district scope)")
    with k5:
        kpi_card("Budget remaining", fmt_money(max(0.0, budget - spent)), delta=f"{spent / budget:.0%} planned",
                 good_direction="neutral", fidelity="modeled", band=f"{fmt_money(spent)} of {fmt_money(budget)} allocated")

with col_outcome, st.container(border=True):
    chart_card_header("Outcome & uncertainty", f"{res.n_draws:,} simulated elections · shared statewide error + district error "
                      "· every effect, cost and decay parameter drawn from its range", fidelity="modeled")
    st.altair_chart(win_prob_bar(res.win_prob, res.baseline_win_prob, res.win_prob_interval, theme), width="stretch")
    st.caption("Green bar = with plan · black tick = no-spend baseline · whisker = 10th–90th percentile of ad-effect size")
    st.altair_chart(outcome_histogram(res.outcome_hist, theme, x_title=res.outcome_label,
                                      threshold=(ctx.majority - 0.5) if ctx.scope == "chamber" else 0.0,
                                      discrete=ctx.scope == "chamber"), width="stretch")
    st.caption("Bars = with plan (blue = win) · dashed step line = baseline · dashed rule = win threshold")
    turnout = float(units["expected_turnout"].sum() if ctx.scope != "district" else
                    units.set_index("unit_id").loc[ctx.target_unit, "expected_turnout"])
    equiv = res.total_delta_votes / max(1.0, turnout) * 100
    if res.total_delta_votes > 0:
        insight(f"This plan is worth ≈ {equiv:.2f} pts of margin",
                f"For scale: a 1-pt national environment shift moves {turnout / 100:,.0f} votes here. Ads matter most "
                "when the race is within the error band — see the sensitivity panel below.", tone="dem")

# ----------------------------------------------------------------------------- where the votes come from
m1, m2 = st.columns([7, 5], gap="medium")
by_unit = res.delta_votes_by_unit.merge(units[["unit_id", "dem_margin_pct", "expected_turnout"]], on="unit_id")
by_unit["plan_dollars"] = by_unit["unit_id"].map(clean_allocation(plan, ctx.weeks).groupby("unit_id")["dollars"].sum()).fillna(0)
with m1, st.container(border=True):
    chart_card_header("Where the plan adds votes", "Expected net votes by unit (click a unit to inspect its response curve)",
                      fidelity="modeled")
    if by_unit["delta_votes"].sum() > 0:
        mp = choropleth(geo_key, by_unit, "delta_votes", "Net votes from plan", scale="sequential", theme=theme,
                        extra_tooltips=[("plan_dollars", "Plan $", "$,.0f"), ("dem_margin_pct", "Baseline margin", "+.1f")],
                        highlight=ctx.target_unit, swing_pts=None, height=380)
        ev = st.altair_chart(mp, width="stretch", on_select="rerun", key="wr_map", selection_mode="unit_pick")
        pick = (ev or {}).get("selection", {}).get("unit_pick") or []
        if pick and pick[0].get("unit_id"):
            ss.selected_unit = pick[0]["unit_id"]
    else:
        st.info("Add dollars to the plan to see where votes come from.")
with m2, st.container(border=True):
    chart_card_header("Top units by net votes", "Mean of the simulation, with 10th–90th percentile whiskers", fidelity="modeled")
    top = by_unit[by_unit["delta_votes"] > 0].assign(label=lambda d: d["unit_id"].astype(str) + " · " + d["dem_margin_pct"].map("{:+.1f}".format).astype(str))
    if not top.empty:
        st.altair_chart(ranked_bar(top, "unit_id", "delta_votes", theme, title="Net votes", fmt=",.0f",
                                   low_col="delta_low", high_col="delta_high", label_col="label", top=12), width="stretch")
        st.caption("Label = unit · 2024 presidential Dem margin (pts)")

p1, p2 = st.columns([7, 5], gap="medium")
with p1, st.container(border=True):
    chart_card_header("Flight pacing", "Planned dollars by week and channel — late weeks decay less, so they buy more",
                      fidelity="modeled")
    cp = clean_allocation(plan, ctx.weeks)
    if not cp.empty:
        st.altair_chart(stacked_weeks(cp, theme, weeks=ctx.weeks), width="stretch")
with p2, st.container(border=True):
    chart_card_header("Channel efficiency", "Expected net votes and $ per vote by channel (mode parameters)", fidelity="modeled")
    if not lines.empty:
        ch = lines.groupby("channel", as_index=False)[["dollars", "delta_votes"]].sum()
        ch["per_vote"] = ch["dollars"] / ch["delta_votes"].replace(0, np.nan)
        ch["Channel"] = ch["channel"].map(CHANNEL_LABELS)
        st.dataframe(ch[["Channel", "dollars", "delta_votes", "per_vote"]].sort_values("per_vote"), hide_index=True,
                     width="stretch", column_config={"dollars": st.column_config.NumberColumn("Dollars", format="dollar"),
                                                     "delta_votes": st.column_config.NumberColumn("Net votes", format="%.0f"),
                                                     "per_vote": st.column_config.NumberColumn("$ / vote", format="dollar")})
        aud = lines.groupby("audience")[["dollars", "delta_votes"]].sum()
        for aud_k, r in aud.iterrows():
            st.caption(esc(f"{AUDIENCE_LABELS[aud_k]}: {fmt_money(r.dollars)} → {r.delta_votes:,.0f} votes "
                           f"({fmt_money(r.dollars / max(r.delta_votes, 1e-9))}/vote)"))

r1, r2 = st.columns(2, gap="medium")
with r1, st.container(border=True):
    chart_card_header("Diminishing returns", "What the next dollar buys in one unit, per channel, holding the rest of the plan fixed",
                      fidelity="modeled")
    default_u = ss.get("selected_unit") if ss.get("selected_unit") in unit_ids else (
        ctx.target_unit or (by_unit.sort_values("delta_votes").iloc[-1]["unit_id"] if len(by_unit) else unit_ids[0]))
    q1, q2 = st.columns(2)
    ru = q1.selectbox("Unit", unit_ids, index=unit_ids.index(default_u), format_func=lambda u: names[u], key="wr_curve_unit")
    ra = q2.selectbox("Audience", AUDIENCES, format_func=AUDIENCE_LABELS.get, key="wr_curve_aud")
    curve = response_curve(plan, ctx, a, ru, ra, week=ctx.weeks, max_dollars=300_000, n=21)
    st.altair_chart(response_curves(curve, theme), width="stretch")
    st.caption(f"Extra dollars added in the final week. Universe: "
               f"{int(units.set_index('unit_id').loc[ru, 'persuasion_universe' if ra == 'persuasion' else 'mobilization_universe']):,} people. "
               "Click a legend entry to isolate a channel.")
with r2, st.container(border=True):
    chart_card_header("Which assumptions matter?", "Win probability with each parameter pinned to its pessimistic (red) "
                      "and optimistic (blue) end", fidelity="modeled")
    sens_key = hashlib.md5((aj + ck + ajs).encode()).hexdigest()
    if ss.get("wr_sens", (None,))[0] != sens_key:
        if st.button("Run sensitivity analysis", width="stretch"):
            with st.spinner("Re-simulating with each assumption at its extremes…"):
                ss.wr_sens = (sens_key, sensitivity(plan, ctx, a, n_draws=1500))
            st.rerun()
        st.caption("Runs 13 extra simulations of this plan.")
    else:
        sdf = ss.wr_sens[1]
        st.altair_chart(tornado(sdf, theme), width="stretch")
        top_p = sdf.iloc[0]
        st.caption(f"Biggest lever: **{top_p.parameter}** ({top_p.low:.0%} → {top_p.high:.0%}). "
                   "When the environment dominates, no ad plan can be judged without a view on the national mood.")

# ----------------------------------------------------------------------------- scenarios
with st.container(border=True):
    chart_card_header("Saved scenarios", "Save the current plan with its assumptions and results; compare up to three",
                      fidelity="modeled")
    n1, n2 = st.columns([3, 1], vertical_alignment="bottom")
    sname = n1.text_input("Scenario name", placeholder="e.g. Late mobilization push", key="wr_sname")
    if n2.button("💾 Save scenario", width="stretch", disabled=not sname.strip()):
        save_scenario(
            name=sname.strip(), scope=ctx.scope, unit_type=ctx.unit_type,
            allocation=clean_allocation(plan, ctx.weeks),
            assumptions_dict={**a.to_dict(), "budget": budget, "weeks": weeks, "target_unit": ctx.target_unit},
            results_dict={"win_prob": res.win_prob, "baseline_win_prob": res.baseline_win_prob,
                          "win_prob_interval": list(res.win_prob_interval), "net_votes": res.total_delta_votes,
                          "cost_per_net_vote": res.cost_per_net_vote if np.isfinite(res.cost_per_net_vote) else None,
                          "spent": spent, "expected_outcome": res.expected_outcome,
                          "by_channel": lines.groupby("channel")["dollars"].sum().to_dict() if not lines.empty else {}},
        )
        st.toast(f"Saved '{sname.strip()}'")
    scen = [s for s in list_scenarios() if s["unit_type"] == ctx.unit_type]
    if not scen:
        st.caption("No saved scenarios for this geography yet.")
    else:
        labels = {s["id"]: f"{s['name']} · {s['created_at'][:16].replace('T', ' ')}" for s in scen}
        pick = st.multiselect("Compare (max 3)", list(labels), default=[scen[0]["id"]], format_func=labels.get,
                              max_selections=3, key="wr_cmp")
        if pick:
            rows = []
            for s in (x for x in scen if x["id"] in pick):
                r = s["results"]
                rows.append({"Scenario": s["name"], "Scope": s["scope"], "Win prob": r.get("win_prob"),
                             "Baseline": r.get("baseline_win_prob"), "Net votes": r.get("net_votes"),
                             "$ / vote": r.get("cost_per_net_vote"), "Spent": r.get("spent"),
                             "Env shift": s["assumptions"].get("env_shift_pts"),
                             **{CHANNEL_LABELS[c]: (r.get("by_channel") or {}).get(c, 0.0) for c in CHANNELS}})
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", column_config={
                "Win prob": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
                "Baseline": st.column_config.NumberColumn(format="percent"),
                "Net votes": st.column_config.NumberColumn(format="%.0f"),
                "$ / vote": st.column_config.NumberColumn(format="dollar"),
                "Spent": st.column_config.NumberColumn(format="dollar"),
                **{CHANNEL_LABELS[c]: st.column_config.NumberColumn(format="dollar") for c in CHANNELS}})
            st.caption("Results are as saved (with that scenario's assumptions). Load one to re-simulate it under today's settings.")
            bc = st.columns(len(pick))
            for col, s in zip(bc, (x for x in scen if x["id"] in pick)):
                with col:
                    c1, c2 = st.columns(2)
                    if c1.button(f"Load '{s['name']}'", key=f"wr_load_{s['id']}", width="stretch"):
                        set_plan(s["allocation"]); st.rerun()
                    if c2.button("Delete", key=f"wr_del_{s['id']}", width="stretch"):
                        delete_scenario(s["id"]); st.rerun()

for _k in PERSIST:
    if _k in ss:
        ss[f"_{_k}"] = ss[_k]
