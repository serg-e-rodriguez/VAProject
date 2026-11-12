"""
War Room — rewind, plan, reveal.

Rewind to a date before Election Day, plan the rest of the budget across regions with the help
of the optimizer, see what the plan does to our chances, then reveal how the race really ended.
Five steps, top to bottom:
  1 Where we stand   2 Where a dollar works hardest   3 Your plan   4 What it does
  5 Save, compare, reveal
All maths lives in campaign_intel.model; this file is layout and session state.
"""

from __future__ import annotations

import html
import io
import json
from dataclasses import replace

import numpy as np
import pandas as pd
import streamlit as st

from campaign_intel.data.loaders import (
    fmt_margin,
    fmt_money,
    fmt_num,
    load_regions,
    load_statewide,
    snapshot_date,
    spend_as_of,
    unit_type,
)
from campaign_intel.model import warroom as WR
from campaign_intel.model.assumptions import Assumptions, apply_preset, load_defaults
from campaign_intel.model.engine import sensitivity, simulate
from campaign_intel.model.optimizer import optimize
from campaign_intel.model.scenarios import delete_scenario, list_scenarios, save_scenario
from campaign_intel.state import race, theme
from campaign_intel.ui.components import (
    _md,
    bullets,
    callout,
    chart,
    kpi,
    page_header,
    section,
    source,
)
from campaign_intel.viz.charts import (
    net_votes_bars,
    outcome_dist,
    plan_weeks,
    reveal_board,
    win_chance_bar,
)
from campaign_intel.viz.maps import choropleth

R, T = race(), theme()
UT = unit_type(R)
ss = st.session_state
regions = load_regions(R)
labels = dict(zip(regions["unit_id"], regions["label"]))
ids_by_label = {v: k for k, v in labels.items()}
UNIT = "county" if R == "senate" else "district"
UNITS = "counties" if R == "senate" else "districts"

DEFAULT_ENV = 5.0
PRESETS = {"conservative": "Cautious", "default": "Expected", "optimistic": "Optimistic"}
SENS_LABELS = {
    "CPM (all channels)": "ad prices",
    "Persuasion effect p": "how well ads persuade",
    "Turnout lift t": "how well ads turn people out",
    "Saturation k": "how fast audiences tire of ads",
    "Weekly retention ρ": "how long an ad's effect lasts",
    "Environment ±3 pts": "the national mood (±3 pts)",
}


def k(name: str) -> str:
    """Session key scoped to the race, so Senate and House keep separate plans."""
    return f"wr_{R}_{name}"


ss.setdefault(k("mix"), WR.empty_mix())
ss.setdefault(k("timing"), "late")
ss.setdefault(k("revealed"), False)
ss.setdefault("wr_asof", WR.ELECTION_DAY - pd.Timedelta(weeks=8))
ss.setdefault("wr_budget", 2_000_000)
BUDGETS = [250_000, 500_000, 750_000, 1_000_000, 1_500_000, 2_000_000, 3_000_000, 4_000_000, 5_000_000,
           7_500_000, 10_000_000]
_a_def = load_defaults()
for _key, _v in [("wr_p", _a_def.persuasion_p[1] * 1000), ("wr_t", _a_def.turnout_t[1] * 1000),
                 ("wr_rho", _a_def.retention_rho[1]), ("wr_sig", _a_def.sigma_state)]:
    ss.setdefault(_key, float(round(_v, 2)))

page_header(f"War Room · {'US Senate' if R == 'senate' else 'US House'}",
            "Rewind to a date before Election Day, plan the rest of the budget, then reveal how it would have played out.")
callout("Model, not forecast",
        "Results come from an explicit model built on the 2024 presidential result, 2022 turnout and ad-cost data, "
        "with the assumptions under Model settings. Treat them as comparisons between plans, not predictions.")

# ============================================================================ setup bar
ELECTION = WR.ELECTION_DAY
ASOF_OPTS = [ELECTION - pd.Timedelta(weeks=n) for n in range(16, 0, -1)]
with st.container(border=True):
    c1, c2, c3, c4 = st.columns([3, 2.2, 3, 1.5], vertical_alignment="bottom")
    with c1:
        asof = st.select_slider(
            "Plan as of", ASOF_OPTS, key="wr_asof",
            format_func=lambda d: f"{d:%b %d} · {WR.weeks_left(d)} wk out")
    with c2:
        if ss["wr_budget"] not in BUDGETS:
            ss["wr_budget"] = min(BUDGETS, key=lambda b: abs(b - ss["wr_budget"]))
        budget = float(st.select_slider("Budget from this date", BUDGETS, key="wr_budget", format_func=fmt_money))
    with c3:
        house_mode, target = "seats", None
        if R == "house":
            hc1, hc2 = st.columns([1.4, 1])
            with hc1:
                house_mode = st.selectbox(
                    "Goal", ["seats", "focus"], key="wr_house_mode",
                    format_func=lambda m: "Win more seats" if m == "seats" else "Focus on one district")
            with hc2:
                close = regions.assign(a=(regions["dem_margin_pct"] + DEFAULT_ENV).abs()).sort_values("a")
                opts = close[close["dem_margin_pct"] < 0]["unit_id"].tolist()
                start = ss.get("region") if ss.get("region") in opts else opts[0]
                target = st.selectbox("District", opts, index=opts.index(start), format_func=labels.get,
                                      key="wr_target", disabled=house_mode != "focus")
        else:
            st.markdown("<div class='wr-goal'>Goal: <b>win the statewide race</b> — every county's votes count.</div>",
                        unsafe_allow_html=True)
    with c4:
        with st.popover("⚙ Model", width="stretch", help="Model settings: how well ads work, national mood"):
            preset = st.segmented_control("How well do ads work?", list(PRESETS), default="default", key="wr_preset",
                                          format_func=PRESETS.get) or "default"
            env = st.slider("National mood vs 2024 (points toward Democrats)", -10.0, 20.0, DEFAULT_ENV, 0.5,
                            key="wr_env", help="Midterms usually swing against the president's party. "
                                               "+5 is a typical midterm swing; 0 = same as the 2024 presidential vote.")
            adv = st.toggle("Advanced", key="wr_adv")
            if adv:
                st.caption("Middle values of the model's ranges (the ranges scale with them). These override the preset.")
                st.slider("Net votes per 1,000 persuadable voters reached", 0.0, 10.0, step=0.25, key="wr_p")
                st.slider("Extra voters per 1,000 low-turnout Democrats reached", 0.0, 20.0, step=0.5, key="wr_t")
                st.slider("Share of an ad's effect that lasts another week", 0.2, 0.95, step=0.05, key="wr_rho")
                st.slider("Polling-style error, statewide (pts)", 1.0, 8.0, step=0.5, key="wr_sig")


@st.cache_data(show_spinner=False)
def _assumptions(preset: str, env: float, pers: float | None, turn: float | None, keep: float | None,
                 err: float | None) -> dict:
    a = apply_preset(load_defaults(), preset)

    def scale(tri, new):
        if new is None or tri[1] == 0:
            return tri
        f = new / tri[1]
        return (tri[0] * f, new, tri[2] * f)

    a = replace(a, env_shift_pts=env,
                persuasion_p=scale(a.persuasion_p, None if pers is None else pers / 1000),
                turnout_t=scale(a.turnout_t, None if turn is None else turn / 1000),
                retention_rho=tuple(min(x, 0.98) for x in scale(a.retention_rho, keep)),
                sigma_state=err if err is not None else a.sigma_state)
    return a.to_dict()


A = Assumptions.from_dict(_assumptions(
    preset, float(env), ss.get("wr_p") if adv else None, ss.get("wr_t") if adv else None,
    ss.get("wr_rho") if adv else None, ss.get("wr_sig") if adv else None))
A_JSON = json.dumps(A.to_dict(), sort_keys=True)

W = WR.weeks_left(asof)
spend = spend_as_of(R, f"{asof:%Y-%m-%d}")
ctx = WR.build_context(regions, R, W, budget, house_mode, target, opp_share=spend["gop_share"], a=A)


# ============================================================================ cached model calls
def _mix_key(mix: pd.DataFrame) -> str:
    return mix.round(2).to_json(orient="split") if not mix.empty else ""


def _mix_from(mix_json: str) -> pd.DataFrame:
    if not mix_json:
        return WR.empty_mix()
    m = pd.read_json(io.StringIO(mix_json), orient="split", dtype={"unit_id": str})
    m["unit_id"] = m["unit_id"].astype(str)
    return m


def _ctx_for(asof_s: str, budget_: float, mode: str, target_: str | None, a_json: str):
    a = Assumptions.from_dict(json.loads(a_json))
    sp = spend_as_of(R, asof_s)
    return WR.build_context(regions, R, WR.weeks_left(pd.Timestamp(asof_s)), budget_, mode, target_,
                            opp_share=sp["gop_share"], a=a), a


@st.cache_data(show_spinner=False, max_entries=64)
def run_sim(race_: str, asof_s: str, budget_: float, mode: str, target_: str | None, a_json: str,
            mix_json: str, timing: str):
    c, a = _ctx_for(asof_s, budget_, mode, target_, a_json)
    mix = _mix_from(mix_json)
    return simulate(WR.spread(mix, timing, c.weeks), c, a)


@st.cache_data(show_spinner=False, max_entries=32)
def run_sens(race_: str, asof_s: str, budget_: float, mode: str, target_: str | None, a_json: str,
             mix_json: str, timing: str) -> pd.DataFrame:
    c, a = _ctx_for(asof_s, budget_, mode, target_, a_json)
    mix = _mix_from(mix_json)
    return sensitivity(WR.spread(mix, timing, c.weeks), c, a, n_draws=1200)


@st.cache_data(show_spinner=False, max_entries=32)
def run_value(race_: str, asof_s: str, budget_: float, mode: str, target_: str | None, a_json: str,
              mix_json: str, timing: str) -> pd.DataFrame:
    c, a = _ctx_for(asof_s, budget_, mode, target_, a_json)
    mix = _mix_from(mix_json)
    return WR.region_value(mix, c, a, timing)


mix = ss[k("mix")]
timing = ss[k("timing")]
args = (R, f"{asof:%Y-%m-%d}", budget, house_mode, target, A_JSON)
with st.spinner("Running 4,000 simulations…"):
    res = run_sim(*args, _mix_key(mix), timing)
value = run_value(*args, _mix_key(mix), timing).merge(regions[["unit_id", "label", "dem_margin_pct"]], on="unit_id")

is_seats = ctx.scope == "chamber"
is_focus = ctx.scope == "district"
win_word = (f"Chance of {ctx.majority}+ seats" if is_seats else
            (f"Chance to win {labels[target]}" if is_focus else "Chance to win the Senate race"))
proj0 = WR.projection(ctx, A)
state_turn = proj0["turnout"].sum()

# ============================================================================ 1 · where we stand
st.markdown(f"<div class='step'><span>1</span>Where we stand on {asof:%b %d}</div>", unsafe_allow_html=True)
k1, k2, k3, k4 = st.columns(4, gap="small")
with k1:
    kpi("Time left", f"{W} weeks", f"Election Day {ELECTION:%b %d} · budget {fmt_money(budget)}")
with k2:
    kpi("Ad spend so far", f"{fmt_money(spend['dem'])} vs {fmt_money(spend['gop'])}",
        "Democrats vs Republicans in this race, since Jul 1", tone="good" if spend["dem"] >= spend["gop"] else "bad")
with k3:
    pace = spend["gop_4w"] / 4
    kpi("Republican pace", f"{fmt_money(pace)}/wk",
        f"Last 4 weeks · ours {fmt_money(spend['dem_4w'] / 4)}/wk", tone="bad" if pace > spend["dem_4w"] / 4 else "good")
with k4:
    if is_seats:
        start_seats = WR.seats_at_start(ctx, A)
        kpi(win_word, f"{res.baseline_win_prob:.0%}",
            f"Without new spend · we start favoured in {start_seats} of 14", tone="good" if res.baseline_win_prob >= .5 else "bad")
    else:
        rel = proj0 if not is_focus else proj0[proj0["unit_id"] == target]
        m_pct = rel["base_votes"].sum() / rel["turnout"].sum() * 100
        kpi(win_word, f"{res.baseline_win_prob:.0%}",
            f"Without new spend · projected {fmt_margin(m_pct)} ({fmt_num(abs(rel['base_votes'].sum()))} votes)",
            tone="good" if res.baseline_win_prob >= .5 else "bad")

if is_seats:
    lean_r = regions.assign(m=regions["dem_margin_pct"] + env).query("m < 0 and m > -8")["label"].tolist()
    msg = (f"With a {env:+.0f}-point national mood we start favoured in {start_seats} districts. "
           f"The next seats are {', '.join(lean_r[:3]) or 'out of reach'}: they decide whether we reach {ctx.majority}.")
else:
    gap = -proj0["base_votes"].sum() if not is_focus else -proj0.loc[proj0["unit_id"] == target, "base_votes"].sum()
    msg = (f"We start about {fmt_num(gap)} votes behind" if gap > 0 else f"We start about {fmt_num(-gap)} votes ahead") + \
        f" (2024 presidential result, midterm turnout, {env:+.0f}-pt national mood)."
if spend["gop_4w"] > spend["dem_4w"]:
    msg += f" Republicans out-spent us {fmt_money(spend['gop_4w'])} to {fmt_money(spend['dem_4w'])} over the last 4 weeks."
_md(f"<div class='wr-lead'>{html.escape(msg)}</div>")

# ============================================================================ 2 · where a dollar works
st.markdown("<div class='step'><span>2</span>Where a dollar works hardest</div>", unsafe_allow_html=True)


def _add_regions(uids: list[str], dollars: float = 100_000.0) -> None:
    cur = ss[k("mix")]
    have = set(cur["unit_id"]) if not cur.empty else set()
    v = value.set_index("unit_id")
    new = [WR.region_lines(u, dollars, v.loc[u, "best_goal"], [v.loc[u, "best_channel"]]) for u in uids if u not in have]
    if new:
        ss[k("mix")] = pd.concat([cur] + new, ignore_index=True)
        ss.pop(k("editor"), None)
    skipped = [labels[u] for u in uids if u in have]
    if skipped:
        st.toast(f"Already in the plan: {', '.join(skipped)}. Change the budget in step 3.")


with st.container(border=True):
    vm = value.copy()
    vm["gain_pts"] = vm["win_gain"] * 100
    vm["best"] = vm["best_channel"].map(WR.PLATFORM_LABELS) + " · " + vm["best_goal"].map(WR.GOAL_LABELS)
    vm["best_short"] = vm["best_channel"].map(WR.PLATFORM_SHORT) + " · " + vm["best_goal"].map(WR.GOAL_SHORT)
    vm["name"] = vm["label"]
    left, right = st.columns([6, 5], gap="medium")
    with left:
        what = "the statewide win chance" if R == "senate" else "that district's win chance"
        section("Win-chance gain per $100K",
                f"How much the next $100K here (spent the best way) raises {what}, given the plan so far. "
                f"Darker = better. Click a {UNIT} to add it to the plan.")
        mp = choropleth(UT, vm, "gain_pts", "Win-chance gain per $100K (pts)", scale="sequential", theme=T, fmt=".2f",
                        extra_tooltips=[("votes_per_step", "Net votes per $100K", ",.0f"), ("best", "Best use", ""),
                                        ("dem_margin_pct", "2024 president (D−R)", "+.1f")],
                        swing_pts=None, height=380 if UT == "county" else 410)
        ev = chart(mp, on_select="rerun", selection_mode="unit_pick", key=k("map"))
        sel = (ev or {}).get("selection", {}).get("unit_pick") if ev else None
        picked = str(sel[0].get("unit_id") or sel[0].get("properties.unit_id") or "") if sel else None
        if picked and picked != ss.get(k("last_pick")):
            ss[k("last_pick")] = picked
            _add_regions([picked])
            st.rerun()
    with right:
        section("Best next $100K", "Ranked by win-chance gain. Tick rows to add them.")
        top = vm.sort_values("win_gain", ascending=False).head(10)
        if is_focus:
            top = vm[vm["unit_id"] == target]
        tbl = st.dataframe(
            top[["label", "gain_pts", "votes_per_step", "best_short"]], hide_index=True, width="stretch",
            height=36 + 35 * len(top), on_select="rerun", selection_mode="multi-row", key=k("rank"),
            column_config={"label": UNIT.title(),
                           "gain_pts": st.column_config.NumberColumn("Win chance", format="+%.2f pts"),
                           "votes_per_step": st.column_config.NumberColumn("Net votes", format="%d"),
                           "best_short": "Best use"})
        rows = tbl.selection.rows if tbl else []
        b1, b2 = st.columns(2)
        add_lbl = f"Add {len(rows)} selected" if rows else ("Add to plan" if is_focus else "Add top 5")
        if b1.button(add_lbl, width="stretch", key=k("add")):
            _add_regions(top.iloc[rows]["unit_id"].tolist() if rows else top.head(5)["unit_id"].tolist())
            st.rerun()

    st.divider()
    s1, s2, s3 = st.columns([3, 1.3, 1.3], vertical_alignment="bottom")
    with s1:
        plat = st.multiselect("Platforms the suggestion may use", WR.WR_CHANNELS, default=WR.WR_CHANNELS,
                              format_func=WR.PLATFORM_LABELS.get, key="wr_plats")
    spent_now = float(mix["dollars"].sum()) if not mix.empty else 0.0

    def _suggest(rebuild: bool) -> None:
        cur = ss[k("mix")]
        start = WR.spread(cur, timing, W) if not rebuild else None
        rec, _ = optimize(start, ctx, A, step=20_000 if UT == "county" else 10_000, channels=plat or WR.WR_CHANNELS)
        ss[k("pending")] = {"mix": WR.to_mix(rec), "old": cur.copy(),
                            "what": "A fresh plan for the whole budget" if rebuild else "How to spend what's left"}

    with s2:
        if st.button("✨ Suggest a plan", type="primary", width="stretch", key=k("suggest")):
            _suggest(True)
    with s3:
        if st.button("Spend what's left", width="stretch", key=k("topup"), disabled=spent_now >= budget - 1000):
            _suggest(False)

    pend = ss.get(k("pending"))
    if pend:
        changes = WR.diff_sentences(pend["old"], pend["mix"], labels)
        st.markdown(f"<div class='sec-title'>{html.escape(pend['what'])}</div>", unsafe_allow_html=True)
        if not changes:
            st.caption("The optimizer has nothing to change: the budget is spent or more money adds no votes.")
        lines = []
        for c in changes[:12]:
            sign = "+" if c["change"] > 0 else "−"
            lines.append(f"{sign}{fmt_money(abs(c['change']))} → {c['label']} · {c['platforms']} · {c['goal']}"
                         + (f"  (total {fmt_money(c['after'])})" if c["after"] != abs(c["change"]) else ""))
        if len(changes) > 12:
            rest = sum(c["change"] for c in changes[12:])
            lines.append(f"… and {len(changes) - 12} smaller changes ({fmt_money(rest)} in total)")
        bullets(lines)
        a1, a2, _ = st.columns([1, 1, 4])
        if a1.button("Accept", type="primary", width="stretch", key=k("accept")):
            ss[k("mix")] = pend["mix"]
            ss[k("timing")] = "late"
            ss.pop(k("timing_pick"), None)
            ss.pop(k("pending"))
            ss.pop(k("editor"), None)
            st.rerun()
        if a2.button("Discard", width="stretch", key=k("discard")):
            ss.pop(k("pending"))
            st.rerun()

# ============================================================================ 3 · your plan
st.markdown("<div class='step'><span>3</span>Your plan</div>", unsafe_allow_html=True)
with st.container(border=True):
    rows_df = WR.plan_rows(mix)
    view = pd.DataFrame({
        "Region": rows_df["unit_id"].map(labels) if len(rows_df) else pd.Series(dtype=str),
        "Budget": rows_df["budget"].round(-3) if len(rows_df) else pd.Series(dtype=float),
        "Goal": rows_df["goal"].map(WR.GOAL_LABELS) if len(rows_df) else pd.Series(dtype=str),
        "Platforms": rows_df["channels"].map(lambda cs: [WR.PLATFORM_LABELS[c] for c in cs]) if len(rows_df)
        else pd.Series(dtype=object),
    })
    pc1, pc2 = st.columns([7, 3], gap="medium")
    with pc1:
        if view.empty:
            st.info(f"The plan is empty. Click {UNITS} on the map, tick rows in the ranking, or press "
                    "**✨ Suggest a plan**. You can also add rows here.")
        edited = st.data_editor(
            view, key=k("editor"), num_rows="dynamic", hide_index=True, width="stretch",
            column_config={
                "Region": st.column_config.SelectboxColumn(UNIT.title(), options=sorted(labels.values()), required=True),
                "Budget": st.column_config.NumberColumn("Budget", min_value=0, step=10_000, format="dollar"),
                "Goal": st.column_config.SelectboxColumn("Goal", options=list(WR.GOAL_LABELS.values())),
                "Platforms": st.column_config.MultiselectColumn("Platforms", options=list(WR.PLATFORM_LABELS.values())),
            })
    with pc2:
        timing_new = st.segmented_control("When to spend it", list(WR.TIMINGS), default=timing, key=k("timing_pick"),
                                          format_func=WR.TIMINGS.get) or timing
        if timing_new != timing:
            ss[k("timing")] = timing_new
            st.rerun()
        spent = float(mix["dollars"].sum()) if not mix.empty else 0.0
        st.progress(min(spent / budget, 1.0))
        over = spent - budget
        _md(f"<div class='wr-meter'><b>{fmt_money(spent)}</b> of {fmt_money(budget)} planned · "
            + (f"<span class='rep'>{fmt_money(over)} over budget</span>" if over > 1000 else f"{fmt_money(max(budget - spent, 0))} left")
            + "</div>")
        if not mix.empty and st.button("Clear plan", width="stretch", key=k("clear")):
            ss[k("mix")] = WR.empty_mix()
            ss.pop(k("editor"), None)
            st.rerun()

    # editor -> plan (only when the table really changed)
    def _norm(df: pd.DataFrame) -> list:
        return [(r["Region"], 0.0 if pd.isna(r["Budget"]) else round(float(r["Budget"]), 0),
                 r["Goal"] if isinstance(r["Goal"], str) else None,
                 tuple(sorted(r["Platforms"])) if isinstance(r["Platforms"], (list, tuple)) else ())
                for _, r in df.iterrows()]

    complete = edited[edited["Region"].notna()] if len(edited) else edited
    if _norm(complete) != _norm(view):
        v = value.set_index("unit_id")
        goal_ids = {lbl: g for g, lbl in WR.GOAL_LABELS.items()}
        plat_ids = {lbl: c for c, lbl in WR.PLATFORM_LABELS.items()}
        new_rows = []
        for _, r in complete.iterrows():
            uid = ids_by_label.get(r["Region"])
            if not uid:
                continue
            goal = goal_ids.get(r["Goal"]) if isinstance(r["Goal"], str) else None
            goal = goal or v.loc[uid, "best_goal"]
            plats = r["Platforms"] if isinstance(r["Platforms"], (list, tuple)) else []
            chans = [plat_ids[p] for p in plats if p in plat_ids] or [v.loc[uid, "best_channel"]]
            bud = float(r["Budget"]) if pd.notna(r["Budget"]) and r["Budget"] else 100_000.0
            new_rows.append({"unit_id": uid, "budget": bud, "goal": goal, "channels": chans})
        nr = pd.DataFrame(new_rows, columns=["unit_id", "budget", "goal", "channels"])
        nr = nr.groupby("unit_id", as_index=False, sort=False).agg(
            budget=("budget", "sum"), goal=("goal", "first"), channels=("channels", "first"))
        ss[k("mix")] = WR.apply_rows(mix, nr)
        ss.pop(k("editor"), None)
        st.rerun()

    if not mix.empty:
        alloc = WR.spread(mix, timing, W)
        starts = WR.week_starts(asof, W)
        wk = alloc.assign(week=alloc["week"].map(lambda i: f"{starts[i - 1]:%b %d}"),
                          channel=alloc["channel"].map(WR.PLATFORM_LABELS))
        wk = wk.groupby(["week", "channel"], as_index=False, sort=False)["dollars"].sum()
        chart(plan_weeks(wk, [f"{d:%b %d}" for d in starts], T))
        source("Each region's money is spread over the weeks left with the timing above. "
               "Late money counts more because an ad's effect fades week by week.")

# ============================================================================ 4 · what it does
st.markdown("<div class='step'><span>4</span>What it does</div>", unsafe_allow_html=True)
if mix.empty:
    st.info("Add money to the plan to see what it does to our chances.")
else:
    lo, hi = res.win_prob_interval
    d_win = res.win_prob - res.baseline_win_prob
    q1, q2, q3, q4 = st.columns(4, gap="small")
    with q1:
        kpi(win_word, f"{res.baseline_win_prob:.0%} → {res.win_prob:.0%}",
            f"Range {lo:.0%}–{hi:.0%} depending on how well ads work", tone="good" if d_win > 0 else "neutral")
    with q2:
        dlo, dhi = res.total_delta_interval
        kpi("Net votes gained", f"+{fmt_num(res.total_delta_votes)}", f"Range {fmt_num(dlo)}–{fmt_num(dhi)}"
            + (" · only the focus district counts" if is_focus else ""), tone="good")
    with q3:
        kpi("Cost per net vote", fmt_money(res.cost_per_net_vote) if np.isfinite(res.cost_per_net_vote) else "—",
            f"{fmt_money(res.total_spent)} spent")
    with q4:
        if is_seats:
            kpi("Expected seats", f"{res.baseline_expected_outcome:.1f} → {res.expected_outcome:.1f}", "Out of 14")
        else:
            pm = res.expected_outcome / (state_turn if not is_focus else
                                         proj0.loc[proj0["unit_id"] == target, "turnout"].sum()) * 100
            kpi("Projected margin", fmt_margin(pm), f"{'+' if res.expected_outcome >= 0 else '−'}"
                f"{fmt_num(abs(res.expected_outcome))} votes with the plan", tone="good" if pm > 0 else "bad")

    with st.container(border=True):
        section(win_word, "◇ without new spend · ● with this plan · shaded = range depending on how well ads work")
        chart(win_chance_bar(res.baseline_win_prob, res.win_prob, lo, hi, T, win_word))
        sens = run_sens(*args, _mix_key(mix), timing)
        top2 = sens.head(3)
        risk = []
        for r in top2.itertuples():
            nm = SENS_LABELS.get(r.parameter, r.parameter)
            risk.append(f"{nm[0].upper() + nm[1:]}: the win chance ranges from {min(r.low, r.high):.0%} to "
                        f"{max(r.low, r.high):.0%} between the low and high assumption.")
        st.markdown("<div class='sec-title' style='margin-top:.4rem'>What could change the answer most</div>",
                    unsafe_allow_html=True)
        bullets(risk)

    o1, o2 = st.columns([1, 1], gap="medium")
    with o1, st.container(border=True):
        section("Range of outcomes", "4,000 simulations of the race. Dashed line = without new spend.")
        thr = ctx.majority - 0.5 if is_seats else 0.0
        chart(outcome_dist(res.outcome_hist, T, thr, "Seats won" if is_seats else "Margin (votes, + = we win)",
                           seats=is_seats))
    with o2, st.container(border=True):
        section("Where the votes come from", "Expected net votes gained per region, with the likely range.")
        bu = res.delta_votes_by_unit.merge(WR.plan_rows(mix)[["unit_id", "budget"]], on="unit_id")
        bu["label"] = bu["unit_id"].map(labels)
        chart(net_votes_bars(bu.nlargest(12, "delta_votes"), T, height=250))
        if is_focus and len(bu) > 1:
            source(f"In focus mode only {labels[target]} counts toward the win chance.")

# ============================================================================ 5 · save, compare, reveal
st.markdown("<div class='step'><span>5</span>Save, compare, reveal</div>", unsafe_allow_html=True)
saved = [s for s in list_scenarios() if s["scope"] == R]
with st.container(border=True):
    v1, v2 = st.columns([3, 2], gap="medium")
    with v1:
        section("Saved plans", "Save a plan, then compare up to three side by side.")
        n1, n2 = st.columns([3, 1], vertical_alignment="bottom")
        name = n1.text_input("Plan name", value=f"Plan {len(saved) + 1} · {asof:%b %d}", key=k("name"))
        if n2.button("Save", width="stretch", disabled=mix.empty, key=k("save")):
            save_scenario(name, R, UT, mix, json.loads(A_JSON) | {"_preset": preset}, {
                "asof": f"{asof:%Y-%m-%d}", "budget": budget, "timing": timing, "house_mode": house_mode,
                "target": target, "win": res.win_prob, "base": res.baseline_win_prob,
                "lo": res.win_prob_interval[0], "hi": res.win_prob_interval[1], "votes": res.total_delta_votes,
                "spent": res.total_spent, "cpv": res.cost_per_net_vote, "goal": win_word})
            st.toast(f"Saved “{name}”")
            st.rerun()
    with v2:
        if saved:
            section("Open or delete", "Opening a plan restores its date, budget and timing.")
            pick = st.selectbox("Plan", [s["id"] for s in saved], key=k("pick"),
                                format_func=lambda i: next(s["name"] for s in saved if s["id"] == i))
            o1, o2 = st.columns(2)
            if o1.button("Open", width="stretch", key=k("open")):
                s = next(s for s in saved if s["id"] == pick)
                ss[k("mix")] = s["allocation"][WR.MIX_COLS] if not s["allocation"].empty else WR.empty_mix()
                ss[k("timing")] = s["results"].get("timing", "late")
                ss.pop(k("timing_pick"), None)
                ss["wr_asof"] = pd.Timestamp(s["results"]["asof"])
                ss["wr_budget"] = int(s["results"]["budget"])
                ss.pop(k("editor"), None)
                st.rerun()
            if o2.button("Delete", width="stretch", key=k("del")):
                delete_scenario(pick)
                st.rerun()
    if saved:
        cmp_ids = st.multiselect("Compare", [s["id"] for s in saved], default=[s["id"] for s in saved[:3]],
                                 max_selections=3, key=k("cmp"),
                                 format_func=lambda i: next(s["name"] for s in saved if s["id"] == i))
        rows = []
        for s in saved:
            if s["id"] not in cmp_ids:
                continue
            r = s["results"]
            top3 = (s["allocation"].groupby("unit_id")["dollars"].sum().nlargest(3).index.map(labels).tolist()
                    if not s["allocation"].empty else [])
            rows.append({"Plan": s["name"], "As of": pd.Timestamp(r["asof"]).strftime("%b %d"),
                         "Spent": r["spent"], "Win chance": f"{r['base']:.0%} → {r['win']:.0%}",
                         "Range": f"{r['lo']:.0%}–{r['hi']:.0%}", "Net votes": r["votes"],
                         "$ per vote": r["cpv"], "Top regions": ", ".join(top3)})
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", column_config={
                "Spent": st.column_config.NumberColumn(format="dollar"),
                "Net votes": st.column_config.NumberColumn(format="%d"),
                "$ per vote": st.column_config.NumberColumn(format="dollar")})

    st.divider()
    rv = ss[k("revealed")]
    if st.button("🙈 Hide the 2026 result" if rv else "🗳️ Reveal the 2026 result", type="secondary" if rv else "primary",
                 key=k("reveal")):
        ss[k("revealed")] = not rv
        st.rerun()
    if not rv:
        st.caption("Everything above uses only what was known on the plan date. Reveal shows how the race actually ended.")

if ss[k("revealed")]:
    st.markdown("<div class='step reveal'><span>★</span>How it actually played out</div>", unsafe_allow_html=True)
    dv = res.delta_votes_by_unit.set_index("unit_id")["delta_votes"] if not mix.empty else None
    pj = WR.projection(ctx, A, dv).merge(
        regions[["unit_id", "label", "dem_margin_pct", "result26_margin_pct"]], on="unit_id")
    pj = pj.rename(columns={"dem_margin_pct": "start_pct", "result26_margin_pct": "actual_pct"})
    money = WR.plan_rows(mix).set_index("unit_id")["budget"] if not mix.empty else pd.Series(dtype=float)
    pj["budget"] = pj["unit_id"].map(money).fillna(0.0)
    sw = load_statewide()
    after = spend

    r1, r2, r3, r4 = st.columns(4, gap="small")
    if R == "senate":
        proj_pct = pj["proj_votes"].sum() / pj["turnout"].sum() * 100
        act_pct = (sw["sen26_dem"] - sw["sen26_rep"]) / sw["sen26_total"] * 100
        base24 = (sw["pres24_dem"] - sw["pres24_rep"]) / sw["pres24_total"] * 100
        with r1:
            kpi("Projected with your plan", fmt_margin(proj_pct), f"Win chance {res.win_prob:.0%}",
                tone="good" if proj_pct > 0 else "bad")
        with r2:
            kpi("Actual result", fmt_margin(act_pct), f"{sw['sen26_dem_candidate']} beat {sw['sen26_rep_candidate']}",
                tone="good" if act_pct > 0 else "bad")
        with r3:
            plan_pts = float(pj["plan_votes"].sum() / pj["turnout"].sum() * 100)
            kpi("Your plan was worth", f"{plan_pts:+.2f} pts", f"≈{fmt_num(pj['plan_votes'].sum())} net votes")
        with r4:
            kpi("Turnout", fmt_num(sw["sen26_total"]), f"vs {fmt_num(pj['turnout'].sum())} the model expected")
        swing = act_pct - base24
        pj["swing"] = pj["actual_pct"] - pj["start_pct"]
        big_swing = pj["swing"] >= pj["swing"].median()
        share_big = pj.loc[big_swing, "budget"].sum() / max(pj["budget"].sum(), 1)
        lessons = [
            (f"The national mood decided it. The race moved {swing:+.1f} points from 2024; the plan assumed {env:+.0f}. "
             "No ad plan in the model is worth more than a point or two statewide."),
            f"Money after {asof:%b %d}: Democrats {fmt_money(after['dem_after'])}, Republicans {fmt_money(after['gop_after'])}.",
        ]
        if not mix.empty:
            lessons.append(f"{share_big:.0%} of your plan went to counties that swung toward us more than the typical county.")
        shown = pj[pj["budget"] > 0].nlargest(15, "budget") if not mix.empty else pj.nlargest(15, "turnout")
    else:
        hr = regions.set_index("unit_id")
        actual_seats = int((regions["result26_margin_pct"] > 0).sum())
        with r1:
            kpi("Projected with your plan", f"{res.expected_outcome:.1f} seats" if is_seats else
                fmt_margin(pj.loc[pj["unit_id"] == target, "proj_pct"].iloc[0]),
                f"{win_word}: {res.win_prob:.0%}", tone="good" if res.win_prob >= .5 else "bad")
        with r2:
            if is_seats:
                kpi("Actual result", f"{actual_seats} seats", "Democrats won, of 14 (unofficial)",
                    tone="good" if actual_seats >= ctx.majority else "bad")
            else:
                m = hr.loc[target, "result26_margin_pct"]
                kpi("Actual result", fmt_margin(m), f"{hr.loc[target, 'dem_candidate']} (D) vs {hr.loc[target, 'rep_candidate']} (R)",
                    tone="good" if m > 0 else "bad")
        with r3:
            kpi("Your plan was worth", f"+{fmt_num(res.total_delta_votes)} votes",
                f"{res.win_prob - res.baseline_win_prob:+.0%} win chance in the model")
        with r4:
            flipped = regions[(regions["dem_margin_pct"] < 0) & (regions["result26_margin_pct"] > 0)]["label"].tolist()
            kpi("Districts flipped vs 2024", str(len(flipped)), ", ".join(flipped[:5]) or "None",
                tone="good" if flipped else "neutral")
        close = pj[pj["actual_pct"].abs() < 5]
        share_close = close["budget"].sum() / max(pj["budget"].sum(), 1)
        swing = float((pj["actual_pct"] - pj["start_pct"]).median())
        lessons = [f"The typical district moved {swing:+.1f} points from 2024; the plan assumed {env:+.0f}."]
        if len(close):
            lessons.append(f"Districts that finished within 5 points: {', '.join(close['label'])}. "
                           + (f"They got {share_close:.0%} of your plan money." if not mix.empty else ""))
        missed = pj[(pj["actual_pct"] > 0) & (pj["start_pct"] < 0) & (pj["budget"] == 0)]["label"].tolist()
        if missed and not mix.empty:
            lessons.append(f"Flipped without any plan money: {', '.join(missed)}. In hindsight those seats were in play.")
        lessons.append(f"Money after {asof:%b %d}: Democrats {fmt_money(after['dem_after'])}, "
                       f"Republicans {fmt_money(after['gop_after'])}.")
        shown = pj

    with st.container(border=True):
        section("Projection vs result", ("| 2024 start · ○ projected with your plan · ● actual 2026 result. "
                                         + ("Counties with the most plan money." if R == "senate" else "All 14 districts.")))
        chart(reveal_board(shown, T))
        section("What to take from it")
        bullets(lessons)
        source(f"2026 results are the NCSBE unofficial results file ({sw.get('sen26_file_date', '')}). "
               f"Snapshot {snapshot_date():%b %d, %Y}.")
