"""
War Room — where the money should go, what it is predicted to buy, and why.

Two interface states on one page (no new route):
  Plan      Settings · Where to put the money (headline, KPIs, map, ranked plan) ·
            What the money buys (net votes per $100K by platform x goal, budget curve) ·
            Adjust the plan (collapsed) · Ask Gemini
  Analysis  Gemini's analysis of the plan and the model's predictions only, with a clear way back.

The plan comes from the existing optimizer and the predictions from the existing Monte Carlo
engine (campaign_intel.model); campaign_intel.war_room_service wires them up and talks to Gemini.
Region detail lives on Region Analysis and opponent messaging on Opponent Tracker.
"""

from __future__ import annotations

import html
from dataclasses import replace

import altair as alt
import pandas as pd
import streamlit as st

from campaign_intel import war_room_service as S
from campaign_intel.config import RACES
from campaign_intel.data.loaders import fmt_money, fmt_num, load_regions, unit_type
from campaign_intel.model import warroom as WR
from campaign_intel.processing.themes import theme_labels
from campaign_intel.state import race, theme
from campaign_intel.ui.components import (
    _md,
    ad_card,
    bullets,
    chart,
    kpi,
    page_header,
    pill,
    section,
    source,
)
from campaign_intel.ui.styles import get_tokens
from campaign_intel.viz.charts import net_votes_bars, side_pair_bars, win_chance_bar
from campaign_intel.viz.maps import choropleth

R, T = race(), theme()
UT = unit_type(R)
W = RACES[R]
tok = get_tokens(T)
ss = st.session_state
regions = load_regions(R)
labels = dict(zip(regions["unit_id"], regions["label"]))
ids_by_label = {v: k for k, v in labels.items()}
BUDGETS = [250_000, 500_000, 750_000, 1_000_000, 1_500_000, 2_000_000, 3_000_000, 4_000_000, 5_000_000,
           7_500_000, 10_000_000]
ASOF = [f"{d:%Y-%m-%d}" for d in S.asof_options()]
# Blue and red are reserved for Democrats and Republicans; audience goals use non-party colours.
GOAL_COLORS = {"Persuade unaffiliated": tok["swing"], "Turn out Democrats": "#14b8c4", "Persuade + turn out": tok["accent"]}
SENS_LABELS = {"CPM (all channels)": "Ad prices", "Persuasion effect p": "How well ads persuade",
               "Turnout lift t": "How well ads turn people out", "Saturation k": "How fast audiences tire of ads",
               "Weekly retention ρ": "How long an ad's effect lasts", "Environment ±3 pts": "National mood ±3 pts"}
PARTY_METRICS = {"dem_spend_so_far": "dem", "gop_spend_so_far": "rep", "gop_pace": "rep"}
SRC_SHORT = {"war_room_model": "War Room model", "ncsbe_2024": "NCSBE 2024", "ncsbe_voters": "NCSBE voter file",
             "bq_google": "Google Ads · BigQuery", "meta_library": "Meta Ad Library",
             "ad_libraries": "Google + Meta ad libraries", "war_room_plan": "War Room settings"}


def k(name: str) -> str:
    """Race-scoped session key (Senate and House keep separate plans)."""
    return f"wr_{R}_{name}"


def wk(name: str) -> str:
    """Race-scoped widget key; 'wrw_' keys are re-assigned every run so they survive the analysis view."""
    return f"wrw_{R}_{name}"


def _persist(name: str) -> None:
    """on_change: save a setting the moment it changes ('wrp_' copies are the source of truth across pages)."""
    ss[f"wrp_{R}_{name}"] = ss.get(wk(name))


def setw(name: str, value) -> None:
    """Set a setting from code (callbacks only, or before its widget is created) and save it."""
    ss[wk(name)] = value
    ss[f"wrp_{R}_{name}"] = value


# Other pages drop or reset these widgets' state; the saved copies always hold the latest value (every setting
# widget saves on change), so restore any that differ. Then keep the rest alive across steps.
for _key in [x for x in ss if str(x).startswith(f"wrp_{R}_")]:
    _w = f"wrw_{_key[4:]}"
    if _w not in ss or ss[_w] != ss[_key]:
        ss[_w] = ss[_key]
for _key in [x for x in ss if str(x).startswith("wrw_")]:
    ss[_key] = ss[_key]

_md("""<style>
.wr-kicker { font-size: 11px; font-weight: 800; letter-spacing: .7px; text-transform: uppercase; color: var(--text-muted); }
.wr-card-title { font-size: 15px; font-weight: 800; color: var(--text-primary); margin: 2px 0 4px; }
.wr-headline { font-size: 15px; line-height: 1.55; color: var(--text-primary); margin: 2px 0 12px; }
.wr-label { font-size: 12px; font-weight: 800; letter-spacing: .5px; text-transform: uppercase; color: var(--text-muted);
  margin: 8px 0 2px; }
.wr-interp li { color: var(--text-secondary) !important; font-style: italic; }
</style>""")

_MD_ENT = {"[": "&#91;", "]": "&#93;", "*": "&#42;", "_": "&#95;", "`": "&#96;", "!": "&#33;", "#": "&#35;",
           "|": "&#124;", "~": "&#126;"}


_HTML_ENT = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}


def esc(text: str) -> str:
    """Escape model text for an HTML block in ONE pass: HTML entities plus markdown control characters (no
    links/images). Escaping in two passes would escape the '#' inside '&#39;' and show it literally."""
    return "".join(_HTML_ENT.get(c) or _MD_ENT.get(c, c) for c in " ".join(str(text).split()))


def kpi_vs(label: str, dem: str, gop: str, sub: str = "") -> None:
    """KPI tile with the Democratic number in blue and the Republican number in red."""
    sub_html = f"<div class='kpi-sub'>{html.escape(sub)}</div>" if sub else ""
    _md(f"<div class='kpi'><div class='kpi-label'>{html.escape(label)}</div><div class='kpi-value'>"
        f"<span style='color:var(--dem)'>{html.escape(dem)}</span> <span style='font-size:16px;"
        f"color:var(--text-muted)'>vs</span> <span style='color:var(--rep)'>{html.escape(gop)}</span></div>{sub_html}</div>")


def md_list(items: list[str], cls: str = "why") -> None:
    if items:
        _md(f"<ul class='{cls}'>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>")


# ============================================================================ defaults
_lean_r = regions.assign(_a=(regions["dem_margin_pct"] + S.DEFAULT_ENV).abs()).sort_values("_a")
FOCUS_OPTS = _lean_r[_lean_r["dem_margin_pct"] < 0]["unit_id"].tolist() if UT == "cd" else []
ss.setdefault(wk("asof"), f"{WR.ELECTION_DAY - pd.Timedelta(weeks=8):%Y-%m-%d}")
ss.setdefault(wk("budget"), 2_000_000)
ss.setdefault(wk("house_mode"), "seats")
ss.setdefault(wk("target"), FOCUS_OPTS[0] if FOCUS_OPTS else None)
ss.setdefault(wk("preset"), "default")
ss.setdefault(wk("env"), S.DEFAULT_ENV)
ss.setdefault(wk("platforms"), list(WR.WR_CHANNELS))
ss.setdefault(wk("timing"), "late")
ss.setdefault(wk("focus"), "")
ss.setdefault(wk("step"), 1)
ss.setdefault(wk("opp_on"), True)
ss.setdefault(wk("opp_lambda"), 0.5)
ss.setdefault(wk("msg_themes"), [])
for _p in ("areas", "messages", "tactics"):
    ss.setdefault(wk(f"perm_{_p}"), False)
ss.setdefault(wk("agent_note"), "")
ss.setdefault(k("agent"), None)
ss.setdefault(k("undo"), None)
ss.setdefault(wk("ask"), "")
ss.setdefault(k("mix"), None)       # None = use the recommended plan; else the user's edited plan (json)
ss.setdefault(k("ed_nonce"), 0)
ss.setdefault(k("result"), None)
ss.setdefault(k("qa"), [])
ss.setdefault("wr_view", "plan")


def current_settings() -> S.PlanSettings:
    return S.PlanSettings(
        race=R, asof=ss[wk("asof")], budget=float(ss[wk("budget")]),
        house_mode=ss[wk("house_mode")] if UT == "cd" else "seats",
        target=ss[wk("target")] if UT == "cd" and ss[wk("house_mode")] == "focus" else None,
        preset=ss[wk("preset")] or "default", env=float(ss[wk("env")]),
        platforms=tuple(c for c in WR.WR_CHANNELS if c in (ss[wk("platforms")] or WR.WR_CHANNELS)),
        timing=ss[wk("timing")] or "late", opp_on=bool(ss[wk("opp_on")]), opp_lambda=float(ss[wk("opp_lambda")]),
        messages=current_messages())


def usable_themes(asof: str) -> set[str]:
    return set(S.theme_stats(R, asof).query("enough_data")["theme"])


def current_messages() -> tuple[tuple[str, float], ...]:
    """The chosen message mix, limited to themes with enough data at the planning date (same for every step)."""
    ok = usable_themes(ss[wk("asof")])
    chosen = [t for t in ss.get(wk("msg_themes"), []) if t in ok][:3]
    if len(chosen) == 1:
        return ((chosen[0], 1.0),)
    w = {t: float(ss.get(wk(f"msg_w_{t}"), 100 / max(len(chosen), 1)) or 0) for t in chosen}
    tot = sum(w.values())
    return tuple((t, round(v / tot, 3)) for t, v in w.items() if v > 0) if tot > 0 else ()


def set_messages(messages) -> None:
    setw("msg_themes", [t for t, _ in messages])
    for t, w in messages:
        setw(f"msg_w_{t}", round(w * 100))  # shares are already in 5% steps (S.five_pct_shares)


def message_state() -> dict:
    return {"themes": list(ss.get(wk("msg_themes"), [])),
            "weights": {t: ss.get(wk(f"msg_w_{t}")) for t in ss.get(wk("msg_themes"), [])}}


def undo_available() -> bool:
    """Undo only while the plan and messages are still exactly what Gemini applied (later edits win)."""
    u = ss.get(k("undo"))
    return bool(u) and ss[k("mix")] == u["applied_mix"] and message_state() == u["applied_msgs"]


def undo_agent() -> None:
    u = ss.get(k("undo"))
    if not u or not undo_available():
        return
    if "mix" in u["scopes"]:
        ss[k("mix")] = u["mix"]
        ss[k("ed_nonce")] += 1
    if "messages" in u["scopes"]:
        setw("msg_themes", u["msgs"]["themes"])
        for t, w in u["msgs"]["weights"].items():
            if w is not None:
                setw(f"msg_w_{t}", w)
    ss[k("undo")] = None
    ss[k("agent")] = None


themes_avail = S.available_themes(R)
labels_th = theme_labels()


def msg_text(messages) -> str:
    return ", ".join(f"{themes_avail.get(t, t)} {w:.0%}" for t, w in messages) or "No specific theme"


def change_chart(diff: pd.DataFrame) -> alt.Chart:
    d = diff.copy()
    d["dir"] = d["change"].map(lambda v: "More money" if v > 0 else "Less money")
    d["lbl"] = d.apply(lambda r: f"{'+' if r.change > 0 else '−'}{fmt_money(abs(r.change))} → {fmt_money(r.after)}", axis=1)
    y = alt.Y("area:N", sort=d["area"].tolist(), title=None, axis=alt.Axis(labelLimit=140))
    bars = alt.Chart(d).mark_bar(cornerRadiusEnd=3, height={"band": 0.6}).encode(
        y=y, x=alt.X("change:Q", title="Change in planned dollars", axis=alt.Axis(format="$~s")),
        color=alt.Color("dir:N", scale=alt.Scale(domain=["More money", "Less money"], range=[tok["accent"], tok["swing"]]),
                        title=None, legend=alt.Legend(orient="top")),
        tooltip=[alt.Tooltip("area:N", title="Area"), alt.Tooltip("before:Q", title="Before", format="$,.0f"),
                 alt.Tooltip("after:Q", title="After", format="$,.0f"), alt.Tooltip("use_before:N", title="Use before"),
                 alt.Tooltip("use_after:N", title="Use after")])
    text = alt.Chart(d).mark_text(align="left", dx=4, fontSize=10.5, color=tok["text_secondary"]).encode(
        y=y, x=alt.value(4), text="lbl:N")
    zero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=tok["border"]).encode(x="x:Q")
    return (zero + bars + text).properties(height=56 + 28 * len(d))


def render_agent_result(out: dict) -> None:
    best, b = out["best"], out["before"]
    a = best["after"]
    diff = S.plan_diff(R, out["before_mix"], best["mix"])
    msg_before, msg_after = msg_text(out["before_messages"]), msg_text(best["messages"])
    st.write("")
    if ss.get(k("undo")):
        u1, u2 = st.columns([1.6, 5], vertical_alignment="center")
        if undo_available():
            u1.button("Undo Gemini's last change", key="wrb_undo", on_click=undo_agent, width="stretch")
        else:
            u2.caption("Undo is off: the plan or messages changed after Gemini's edit.")
    title = "What Gemini changed" if out["applied"] else "What Gemini proposed (not applied: the model scored it lower)"
    section(title, f"{out['model']} · {len(out['rounds'])} round(s) · allowed: "
            + ", ".join(S.PERMISSIONS[p_].split(" (")[0].lower() for p_ in out["permissions"]))
    with st.container(border=True):
        t1, t2, t3 = st.columns(3, gap="small")
        with t1:
            kpi("Win chance", f"{b['win_prob']:.1%} → {a['win_prob']:.1%}", "before → after (model)")
        with t2:
            kpi("Net votes", f"{fmt_num(b['net_votes'])} → {fmt_num(a['net_votes'])}", "before → after (model)")
        with t3:
            moved = diff.loc[diff["change"] > 0, "change"].sum() if len(diff) else 0.0
            kpi("Money moved", fmt_money(moved), f"{int((diff['change'].abs() >= 1000).sum())} areas changed")
        c1, c2 = st.columns([6, 5], gap="medium")
        with c1:
            _md("<div class='wr-card-title'>Spending changes by area</div>")
            moves = diff[diff["change"].abs() >= 1000].head(12)
            if len(moves):
                chart(change_chart(moves))
                if (diff["change"].abs() >= 1000).sum() > 12:
                    source(f"Showing the 12 largest of {int((diff['change'].abs() >= 1000).sum())} changes.")
            else:
                st.caption("No spending moved between areas.")
        with c2:
            _md("<div class='wr-card-title'>Messages</div>")
            bullets([f"Before: {msg_before}", f"After: {msg_after}" + ("" if msg_before != msg_after else " (unchanged)")])
            tac = diff[diff["use_changed"]]
            _md("<div class='wr-card-title'>Goal and platform changes</div>")
            if len(tac):
                bullets([f"{r.area}: {r.use_before} → {r.use_after}" for r in tac.head(8).itertuples()]
                        + ([f"… and {len(tac) - 8} more"] if len(tac) > 8 else []))
            else:
                st.caption("No goal or platform changes.")
            for n_ in best["notes"]:
                source("Checked and adjusted: " + n_)
        if len(diff):
            with st.expander(f"All {len(diff)} area changes"):
                st.dataframe(diff[["area", "before", "after", "change", "use_before", "use_after"]], hide_index=True,
                             width="stretch", column_config={
                                 "area": "Area", "use_before": "Use before", "use_after": "Use after",
                                 "before": st.column_config.NumberColumn("Before", format="dollar"),
                                 "after": st.column_config.NumberColumn("After", format="dollar"),
                                 "change": st.column_config.NumberColumn("Change", format="dollar")})
    with st.container(border=True):
        _md("<div class='wr-card-title'>Why: Gemini's reasoning</div>")
        r1, r2 = st.columns(2, gap="large")
        with r1:
            _md("<div class='wr-label'>What it relied on (from the data)</div>")
            md_list([o["text"] + (f" ({SRC_SHORT.get(o['source'], o['source'])})" if o["source"] else "")
                     for o in best.get("observations", [])] or ["—"])
        with r2:
            _md("<div class='wr-label'>Its reasoning (interpretation)</div>")
            md_list(best.get("reasoning", []) or ["—"], "why wr-interp")
        if best["expected"]:
            _md(f"<div class='source'>Gemini expected: {esc(best['expected'])} The model scored it: "
                f"{a['win_prob']:.1%} win chance, ≈{fmt_num(a['net_votes'])} net votes.</div>")
        source("See step 4 for the full plan. Gemini can't change the budget, the planning date or the model's assumptions.")


def render_ads(ads: pd.DataFrame, how: str) -> None:
    """Ad cards; a link is shown only after it is checked (Google: HTTP 200; Meta: confirmed via the Ad Library API)."""
    with st.spinner("Checking ad links…"):
        links = S.checked_links(ads)
    for col, r in zip(st.columns(len(ads), gap="medium"), ads.itertuples()):
        with col:
            ths = [labels_th.get(t, t) for t in (r.message_themes if r.message_themes is not None else [])]
            url, note = links.get(str(r.ad_id), ("", "not checked"))
            reach = S.top_reach(r.ad_id) if r.platform == "Meta" else None
            ad_card(r.advertiser, f"{r.start:%b %d}", str(r.body), fmt_money(r.p_spend), r.platform, url, audience=reach,
                    themes=ths)
            cpm = f" · {fmt_money(r.p_spend / r.p_impr * 1000)} per 1K" if r.p_impr > 0 else ""
            source(f"≈{fmt_num(r.p_impr)} NC impressions{cpm} {how}. Link: {note}.")


# ============================================================================ charts
def spend_map(rs: pd.DataFrame, height: int) -> alt.Chart:
    d = rs.assign(name=rs["label"], gop_sov_pct=rs["gop_sov"] * 100)
    return choropleth(UT, d, "net_dem_pts", "Dem − GOP share of race ad spend (pts)", scale="diverging", theme=T,
                      fmt="+.0f", extra_tooltips=[("dem", "Democratic spend ($)", "$,.0f"), ("gop", "Republican spend ($)",
                                                                                          "$,.0f"),
                                                  ("gop_sov_pct", "Republican share of voice (%)", ".0f")],
                      swing_pts=None, height=height, selectable=False, domain_max=100.0)


def message_chart(mc: pd.DataFrame, chosen: set[str]) -> alt.Chart:
    d = mc.copy()
    d["what"] = d["theme"].map(lambda t: "Your message" if t in chosen else ("No specific theme" if not t else "Other"))
    d["lbl"] = d["net_votes"].map(lambda v: f"≈{v:,.0f}")
    y = alt.Y("label:N", sort=d["label"].tolist(), title=None, axis=alt.Axis(labelLimit=200))
    bars = alt.Chart(d).mark_bar(cornerRadiusEnd=3, height={"band": 0.65}).encode(
        y=y, x=alt.X("net_votes:Q", title="Net votes gained (expected)", axis=alt.Axis(format="~s")),
        color=alt.Color("what:N", scale=alt.Scale(domain=["Your message", "Other", "No specific theme"],
                                                  range=[tok["accent"], tok["swing"], tok["text_muted"]]), title=None,
                        legend=alt.Legend(orient="top")),
        tooltip=[alt.Tooltip("label:N", title="Message"), alt.Tooltip("net_votes:Q", title="Net votes", format=",.0f"),
                 alt.Tooltip("win_prob:Q", title="Win chance", format=".1%"),
                 alt.Tooltip("mult_persuasion:Q", title="Effect on persuasion", format=".2f"),
                 alt.Tooltip("mult_mobilization:Q", title="Effect on turnout", format=".2f")])
    text = alt.Chart(d).mark_text(align="left", dx=4, fontSize=11, color=tok["text_secondary"]).encode(
        y=y, x="net_votes:Q", text="lbl:N")
    return (bars + text).properties(height=56 + 30 * len(d))


def issue_spend_chart(ts: pd.DataFrame) -> alt.Chart:
    long = ts.melt(id_vars=["label"], value_vars=["dem_spend", "gop_spend"], var_name="side", value_name="spend")
    long["side_group"] = long["side"].map({"dem_spend": "Dem side", "gop_spend": "GOP side"})
    order = ts.assign(t=ts["dem_spend"] + ts["gop_spend"]).sort_values("t", ascending=False)["label"].tolist()
    return side_pair_bars(long, "label", "spend", T, fmt="$,.0f", axis_fmt="$~s", order=order)


def spend_bars(top: pd.DataFrame) -> alt.Chart:
    long = top.melt(id_vars=["label"], value_vars=["dem", "gop"], var_name="side", value_name="spend")
    long["side_group"] = long["side"].map({"dem": "Dem side", "gop": "GOP side"})
    return side_pair_bars(long, "label", "spend", T, fmt="$,.0f", axis_fmt="$~s", order=top["label"].tolist())



def plan_map(plan: pd.DataFrame, height: int) -> alt.Chart:
    d = regions[["unit_id", "label", "dem_margin_pct"]].merge(plan[["unit_id", "budget", "delta_votes"]], on="unit_id",
                                                              how="left").fillna({"budget": 0.0, "delta_votes": 0.0})
    d = d.assign(name=d["label"])
    return choropleth(UT, d, "budget", "Planned dollars", scale="sequential", theme=T, fmt="$,.0f",
                      extra_tooltips=[("delta_votes", "Net votes (expected)", ",.0f"),
                                      ("dem_margin_pct", "2024 President (D−R)", "+.1f")],
                      swing_pts=None, height=height, selectable=False)


def plan_bars(plan: pd.DataFrame, top: int = 10) -> alt.Chart:
    d = plan.head(top).copy()
    d["goal_lbl"] = d["goal"].map(WR.GOAL_LABELS)
    d["plats"] = d["channels"].map(lambda cs: " + ".join(WR.PLATFORM_SHORT[c] for c in cs))
    d["lbl"] = d.apply(lambda r: f"{fmt_money(r.budget)} · ≈{r.delta_votes:,.0f} votes", axis=1)
    order = d["label"].tolist()
    dom = list(GOAL_COLORS)
    y = alt.Y("label:N", sort=order, title=None, axis=alt.Axis(labelLimit=140))
    bars = alt.Chart(d).mark_bar(cornerRadiusEnd=3, height={"band": 0.65}).encode(
        y=y, x=alt.X("budget:Q", title="Planned dollars", axis=alt.Axis(format="$~s")),
        color=alt.Color("goal_lbl:N", scale=alt.Scale(domain=dom, range=[GOAL_COLORS[g] for g in dom]), title=None,
                        legend=alt.Legend(orient="top")),
        tooltip=[alt.Tooltip("label:N", title=W["unit_word"].title()), alt.Tooltip("budget:Q", title="Dollars", format="$,.0f"),
                 alt.Tooltip("goal_lbl:N", title="Goal"), alt.Tooltip("plats:N", title="Platforms"),
                 alt.Tooltip("delta_votes:Q", title="Net votes (expected)", format=",.0f"),
                 alt.Tooltip("delta_low:Q", title="Low end", format=",.0f"),
                 alt.Tooltip("delta_high:Q", title="High end", format=",.0f"),
                 alt.Tooltip("start_pct:Q", title="Model start margin (pts)", format="+.1f")])
    text = alt.Chart(d).mark_text(align="left", dx=4, fontSize=11, color=tok["text_secondary"]).encode(
        y=y, x="budget:Q", text="lbl:N")
    return (bars + text).properties(height=56 + 30 * len(d))


def mix_chart(mm: pd.DataFrame) -> alt.Chart:
    d = mm.copy()
    order = d.groupby("platform")["votes_per_100k"].max().sort_values(ascending=False).index.tolist()
    dom = [g for g in GOAL_COLORS if g in set(d["goal"])]
    d["lbl"] = d["dollars"].map(lambda x: f"{fmt_money(x)} planned")
    y = alt.Y("platform:N", sort=order, title=None, axis=alt.Axis(labelLimit=160))
    bars = alt.Chart(d).mark_bar(cornerRadiusEnd=3).encode(
        y=y, yOffset=alt.YOffset("goal:N", sort=dom),
        x=alt.X("votes_per_100k:Q", title="Net votes per $100K (expected)"),
        color=alt.Color("goal:N", scale=alt.Scale(domain=dom, range=[GOAL_COLORS[g] for g in dom]), title=None,
                        legend=alt.Legend(orient="top")),
        tooltip=[alt.Tooltip("platform:N", title="Platform"), alt.Tooltip("goal:N", title="Goal"),
                 alt.Tooltip("votes_per_100k:Q", title="Net votes per $100K", format=",.0f"),
                 alt.Tooltip("dollars:Q", title="Planned dollars", format="$,.0f"),
                 alt.Tooltip("net_votes:Q", title="Net votes (expected)", format=",.0f")])
    text = alt.Chart(d).mark_text(align="left", dx=4, fontSize=10.5, color=tok["text_secondary"]).encode(
        y=y, yOffset=alt.YOffset("goal:N", sort=dom), x="votes_per_100k:Q", text="lbl:N")
    return (bars + text).properties(height=56 + 44 * len(order))


def curve_chart(curve: pd.DataFrame, budget: float, ww: str, mine: tuple[float, float] | None = None) -> alt.Chart:
    d = curve.copy()
    base = alt.Chart(d).encode(
        x=alt.X("budget:Q", title="Budget (optimizer's best plan at each level)", axis=alt.Axis(format="$~s")),
        y=alt.Y("win_prob:Q", title=ww, axis=alt.Axis(format=".0%"), scale=alt.Scale(zero=False, padding=12)),
        tooltip=[alt.Tooltip("budget:Q", title="Budget", format="$,.0f"),
                 alt.Tooltip("win_prob:Q", title=ww, format=".1%"),
                 alt.Tooltip("net_votes:Q", title="Net votes (expected)", format=",.0f")])
    line = base.mark_line(color=tok["dem"], strokeWidth=2.5) + base.mark_circle(size=70, color=tok["dem"], opacity=1)
    now = alt.Chart(pd.DataFrame({"x": [budget]})).mark_rule(color=tok["text_muted"], strokeDash=[4, 3]).encode(x="x:Q")
    layers = now + line
    if mine is not None:
        pt = pd.DataFrame({"budget": [mine[0]], "win_prob": [mine[1]], "what": ["Your edited plan"]})
        layers += alt.Chart(pt).mark_point(shape="diamond", size=160, filled=True, color=tok["swing"]).encode(
            x="budget:Q", y="win_prob:Q", tooltip=[alt.Tooltip("what:N", title=" "),
                                                   alt.Tooltip("budget:Q", title="Planned", format="$,.0f"),
                                                   alt.Tooltip("win_prob:Q", title=ww, format=".1%")])
    return layers.properties(height=250)


def next_chart(nd: pd.DataFrame, plan: pd.DataFrame, top: int = 10, seats: bool = False) -> alt.Chart:
    d = nd.sort_values("win_gain", ascending=False).head(top).copy()
    d["gain_pts"] = d["win_gain"] * 100
    d["status"] = d["unit_id"].isin(set(plan["unit_id"])).map({True: "Already in plan", False: "Not in plan"})
    d["best"] = d["best_channel"].map(WR.PLATFORM_LABELS) + " · " + d["best_goal"].map(WR.GOAL_LABELS)
    return alt.Chart(d).mark_bar(cornerRadiusEnd=3).encode(
        y=alt.Y("label:N", sort=d["label"].tolist(), title=None),
        x=alt.X("gain_pts:Q", title=("Gain in that district's own win chance" if seats else "Win-chance gain")
                + " from the next $100K (pts)"),
        color=alt.Color("status:N", scale=alt.Scale(domain=["Already in plan", "Not in plan"],
                                                    range=[tok["accent"], tok["swing"]]), title=None,
                        legend=alt.Legend(orient="top")),
        tooltip=[alt.Tooltip("label:N", title="Region"), alt.Tooltip("gain_pts:Q", title="Win-chance gain (pts)", format=".2f"),
                 alt.Tooltip("votes_per_step:Q", title="Net votes", format=",.0f"), alt.Tooltip("best:N", title="Best use")],
    ).properties(height=56 + 28 * len(d))


def tornado(se: pd.DataFrame, ww: str) -> alt.Chart:
    d = se.copy()
    d["what"] = d["parameter"].map(SENS_LABELS).fillna(d["parameter"])
    d["lo"], d["hi"] = d[["low", "high"]].min(axis=1), d[["low", "high"]].max(axis=1)
    y = alt.Y("what:N", sort=d["what"].tolist(), title=None, axis=alt.Axis(labelLimit=200))
    bars = alt.Chart(d).mark_bar(color=tok["swing"], opacity=0.75, height={"band": 0.6}).encode(
        y=y, x=alt.X("lo:Q", title=f"{ww}: assumption unfavourable vs favourable", axis=alt.Axis(format=".0%")), x2="hi:Q",
        tooltip=[alt.Tooltip("what:N", title="Assumption"), alt.Tooltip("lo:Q", title="Unfavourable", format=".1%"),
                 alt.Tooltip("hi:Q", title="Favourable", format=".1%")])
    rule = alt.Chart(pd.DataFrame({"x": [float(d["base"].iloc[0])]})).mark_rule(color=tok["text_primary"]).encode(x="x:Q")
    return (bars + rule).properties(height=56 + 30 * len(d))


# ============================================================================ model for the current settings
def model_state(ps: S.PlanSettings, mix_json: str | None) -> dict:
    ctx, _a, sp = S.race_context(ps)
    mix = S.recommend(ps) if mix_json is None else S.mix_from(mix_json)
    mj = S.mix_key(mix)
    res = S.predict(ps, mj)
    mm = S.messaging_mix(ps, mix)
    plan = S.plan_table(ps, mix, res)
    return {"ctx": ctx, "sp": sp, "mix": mix, "mj": mj, "res": res, "mm": mm, "plan": plan,
            "ww": S.win_word(ps, ctx), "head": S.headline(ps, ctx, res, mm, plan)}


# ============================================================================ ANALYSIS VIEW
def back() -> None:
    ss["wr_view"] = "plan"


def render_analysis(result: dict) -> None:
    ps = S.PlanSettings(**result["settings"])
    m = model_state(ps, result["plan"])
    rep, ctxj = result["report"], result["context"]
    metrics, secs = ctxj["metrics"], rep["sections"]

    c1, c2 = st.columns([2, 7], vertical_alignment="center")
    c1.button("← Back to War Room", key="wrb_back_top", on_click=back, type="primary", width="stretch")
    c2.caption("Gemini's analysis of the plan below. Going back restores your settings and plan.")
    page_header(f"War Room · Plan analysis · {W['label']}",
                "Predictions are from the War Room model; the explanation and suggestions are Gemini's, grounded in "
                "the model's numbers.")
    heads = [pill(f"Plan {fmt_money(m['res'].total_spent)} of {fmt_money(ps.budget)}"),
             pill(f"As of {pd.Timestamp(ps.asof):%b %d} · {ps.weeks} wk out"), pill(S.PRESETS[ps.preset] + " ad effects"),
             pill(f"{result['model']} · {result['created']}")]
    _md(f"<div class='region-head'><h2>{esc(rep['headline'] or 'Plan analysis')}</h2>{''.join(heads)}</div>")

    def tiles(ids: list[str], n: int = 4) -> None:
        ids = [i for i in ids if i in metrics][:n]
        if ids:
            for col, mid in zip(st.columns(len(ids), gap="small"), ids):
                with col:
                    kpi(metrics[mid]["label"], str(metrics[mid]["value"]), SRC_SHORT.get(metrics[mid]["source"], ""),
                        tone=PARTY_METRICS.get(mid, "neutral"))

    def text(sec: dict, interp_label: str = "Interpretation (Gemini)") -> None:
        if sec.get("missing"):
            st.caption("Gemini did not return this section.")
            return
        if sec["summary"]:
            _md(f"<div class='wr-headline'>{esc(sec['summary'])}</div>")
        if sec["observations"]:
            _md("<div class='wr-label'>Observations (from the model and data)</div>")
            md_list([o["text"] + (f" ({SRC_SHORT.get(o['source'], o['source'])})" if o["source"] else " (source not given)")
                     for o in sec["observations"]])
        if sec["interpretations"]:
            _md(f"<div class='wr-label'>{html.escape(interp_label)}</div>")
            md_list(sec["interpretations"], "why wr-interp")

    tiles(secs["summary"]["metric_ids"] or ["win_now", "win_plan", "net_votes", "cost_per_vote"])
    with st.container(border=True):
        section(S.SECTION_KEYS["summary"])
        g, t = st.columns([5, 6], gap="medium")
        with g:
            lo, hi = m["res"].win_prob_interval
            chart(win_chance_bar(m["res"].baseline_win_prob, m["res"].win_prob, lo, hi, T, m["ww"]))
            source(f"{m['ww']}: hollow = no new spend, dot = with the plan, band = ad-effect uncertainty.")
        with t:
            text(secs["summary"])

    plan, mm = m["plan"], m["mm"]
    blocks = [
        ("why", (lambda: net_votes_bars(plan.head(12), T)) if len(plan) else None,
         "Expected net votes per funded region, with the 10–90% range.", "Interpretation (Gemini)"),
        ("improve", lambda: next_chart(S.next_dollar(ps, m["mj"]), plan, seats=m["ctx"].scope == "chamber"),
         "Where the next $100K would do the most, on top of this plan (net votes at typical assumptions).",
         "Suggestions (Gemini)"),
        ("messaging", (lambda: mix_chart(mm)) if len(mm) else None,
         ("Net votes per $100K by platform and goal (model). Messages count through fit and contest (step 3); "
         "ad content is not modeled."), "Interpretation (Gemini)"),
        ("risks", (lambda: tornado(S.risks(ps, m["mj"]), m["ww"])) if m["res"].total_spent > 0 else None,
         "Win chance with each assumption at its unfavourable vs favourable value; line = this plan.",
         "Interpretation (Gemini)"),
    ]
    for key, make, cap, lab in blocks:
        st.write("")
        with st.container(border=True):
            section(S.SECTION_KEYS[key])
            tiles(secs[key]["metric_ids"], 3)
            g, t = st.columns([6, 5], gap="medium")
            with g:
                if make is not None:
                    chart(make())
                    source(cap)
                else:
                    st.caption("Nothing to chart for this plan.")
                if key == "messaging":
                    ts = S.theme_shares(S.ads_between(R, pd.Timestamp("2026-07-01"), pd.Timestamp(ps.asof)))
                    if len(ts):
                        top = ts.groupby("theme")["spend"].sum().nlargest(6).index
                        _md("<div class='wr-card-title'>What each side's Meta ads said (up to the planning date)</div>")
                        chart(side_pair_bars(ts[ts["theme"].isin(top)].rename(columns={"side": "side_group"}), "theme",
                                             "share", T, order=list(top)))
                        source("Share of each side's Meta spend by detected theme (from ad text; ads can carry several).")
            with t:
                text(secs[key], lab)

    st.write("")
    with st.container(border=True):
        section(S.SECTION_KEYS["limits"])
        l1, l2 = st.columns([5, 6], gap="medium")
        with l1:
            text(secs["limits"])
            _md("<div class='wr-label'>Built-in limitations</div>")
            bullets(ctxj["known_limitations"])
        with l2:
            _md("<div class='wr-label'>Datasets and periods used</div>")
            bullets([f"{v['label']} — {v['period']}" for v in ctxj["sources"].values()])
            with st.expander("Settings sent to Gemini"):
                st.json(ctxj["settings"])
    st.divider()
    st.button("← Back to War Room", key="wrb_back_bottom", on_click=back, type="primary", width="stretch")


if ss["wr_view"] == "analysis" and ss.get(k("result")):
    render_analysis(ss[k("result")])
    st.stop()
ss["wr_view"] = "plan"


# ============================================================================ PLAN VIEW (four steps)
STEPS = {1: "Budget & spending", 2: "Opponent messaging", 3: "Our messaging", 4: "Plan & prediction",
         5: "Gemini"}


def go_step(i: int) -> None:
    setw("step", i)


def step_nav(i: int) -> None:
    st.write("")
    b1, _sp, b2 = st.columns([1.4, 5, 1.6])
    if i > 1:
        b1.button(f"← {STEPS[i - 1]}", key=f"wrb_prev_{i}", on_click=go_step, args=(i - 1,), width="stretch")
    if i < len(STEPS):
        b2.button(f"Next: {STEPS[i + 1]} →", key=f"wrb_next_{i}", on_click=go_step, args=(i + 1,), type="primary",
                  width="stretch")


page_header(f"War Room · {W['label']}",
            "Four steps: set the budget against what both sides have spent, read the opponent's messaging, see the "
            "model's plan and prediction, then ask Gemini why it works.")
if ss.get(wk("step")) not in STEPS:
    setw("step", 1)
STEP = ss[wk("step")]


def _step_changed() -> None:
    if ss.get(wk("step")) not in STEPS:  # deselected: stay on the current step
        ss[wk("step")] = STEP
    _persist("step")


st.segmented_control("Step", list(STEPS), key=wk("step"), on_change=_step_changed,
                     format_func=lambda i: f"{i} · {STEPS[i]}", label_visibility="collapsed", width="stretch")
ps = current_settings()
edited = ss[k("mix")] is not None
SIDE_NAMES = {"Dem side": "Democrats", "GOP side": "Republicans"}

# ---------------------------------------------------------------------------- step 1 · budget & spending
if STEP == 1:
    with st.container(border=True):
        c1, c2, c3 = st.columns([3, 2.6, 3], vertical_alignment="bottom")
        with c1:
            st.select_slider("Plan as of", ASOF, key=wk("asof"), on_change=_persist, args=("asof",),
                             format_func=lambda d: f"{pd.Timestamp(d):%b %d} · {WR.weeks_left(pd.Timestamp(d))} wk out",
                             help="Planning date before Election Day. Only spend and ads before this date are used.")
        with c2:
            if ss[wk("budget")] not in BUDGETS:
                setw("budget", min(BUDGETS, key=lambda b: abs(b - ss[wk("budget")])))
            st.select_slider("How much to spend", BUDGETS, key=wk("budget"), on_change=_persist, args=("budget",), format_func=fmt_money)
        with c3:
            if UT == "cd":
                h1, h2 = st.columns([1.3, 1])
                h1.selectbox("Goal", ["seats", "focus"], key=wk("house_mode"), on_change=_persist, args=("house_mode",),
                             format_func=lambda x: "Win one more seat" if x == "seats" else "Win one district")
                h2.selectbox("District", FOCUS_OPTS, key=wk("target"), on_change=_persist, args=("target",), format_func=labels.get,
                             disabled=ss[wk("house_mode")] != "focus")
            else:
                _md("<div class='wr-headline' style='margin:0 0 10px'>Goal: <b>win the statewide race</b> — every "
                    "county's votes count.</div>")
    ps = current_settings()
    sp = S.spend_before(R, ps.asof)
    rs = S.region_spend_before(R, ps.asof)
    st.write("")
    section("What both sides have spent so far",
            f"Race ads from Jul 1 to {pd.Timestamp(ps.asof):%b %d}, by {W['unit_word']}. Republican share of voice in each "
            f"{W['unit_word']} is an input to the model in step 2.")
    with st.container(border=True):
        k1, k2, k3, k4 = st.columns(4, gap="small")
        with k1:
            kpi("Your budget", fmt_money(ps.budget), f"{ps.weeks} weeks to Election Day")
        with k2:
            kpi_vs("Spent so far", fmt_money(sp["dem"]), fmt_money(sp["gop"]), "Democrats vs Republicans")
        with k3:
            kpi_vs("Last 4 weeks", fmt_money(sp["dem_4w"]), fmt_money(sp["gop_4w"]), "Democrats vs Republicans")
        with k4:
            kpi("Republican share of voice", f"{sp['gop_share']:.0%}", "of Dem + GOP race ad spend so far", tone="rep")
        m1, m2 = st.columns([6, 5], gap="medium")
        with m1:
            _md(f"<div class='wr-card-title'>Who out-spends whom, by {W['unit_word']}</div>")
            chart(spend_map(rs, 360 if UT == "county" else 400))
        with m2:
            top = rs.assign(t=rs["dem"] + rs["gop"]).nlargest(12, "gop")
            _md(f"<div class='wr-card-title'>Most Republican spending: top {len(top)} {W['units_word']}</div>")
            chart(spend_bars(top))
        source("Sources: Google Political Ads (BigQuery) and Meta Ad Library, race-attributed ads, NC spend pro-rated by "
               "flight days. Google ads targeted to counties are assigned there (districts via the county crosswalk); "
               "all other spend (all Meta, statewide Google) is split by registered voters.")
    step_nav(1)

# ---------------------------------------------------------------------------- step 2 · opponent messaging
elif STEP == 2:
    asof = ps.asof
    ot = S.opponent_themes(R, asof)
    section("What Republicans are saying, and who it reaches",
            f"Meta ads before {pd.Timestamp(asof):%b %d}, compared with ours. Themes are detected from ad text; Google "
            "ads carry no text.")
    with st.container(border=True):
        t1, t2 = st.columns(2, gap="medium")
        with t1:
            _md("<div class='wr-card-title'>Message themes: share of each side's Meta spend</div>")
            if len(ot):
                topt = ot.groupby("theme")["spend"].sum().nlargest(8).index.tolist()
                chart(side_pair_bars(ot[ot["theme"].isin(topt)].rename(columns={"side": "side_group"}), "theme", "share",
                                     T, order=topt))
                g = ot[ot["side"] == "GOP side"].head(1)
                d_ = ot[ot["side"] == "Dem side"].head(1)
                if len(g) and len(d_):
                    source(f"Republicans lead with {g['theme'].iloc[0].lower()} ({g['share'].iloc[0]:.0%} of their Meta "
                           f"spend); Democrats with {d_['theme'].iloc[0].lower()} ({d_['share'].iloc[0]:.0%}). Ads can "
                           "carry several themes.")
            else:
                st.caption("No themed Meta ads before the planning date.")
        with t2:
            _md("<div class='wr-card-title'>Who each side's messages reach, by age</div>")
            reach = S.opponent_reach_by_age_gender(R, asof)
            if len(reach):
                ag = reach.groupby(["side_group", "age"], as_index=False)["share"].sum()
                chart(side_pair_bars(ag, "age", "share", T, order=list(S.META_TO_VOTER_AGE)))
                gw = reach[reach["side_group"] == "GOP side"].groupby("gender")["share"].sum()
                if len(gw):
                    source(f"Share of each side's Meta impressions by age. Republican impressions: "
                           f"{gw.get('Women', 0):.0%} women, {gw.get('Men', 0):.0%} men.")
            else:
                st.caption("No Meta delivery data before the planning date.")

    with st.container(border=True):
        _md("<div class='wr-card-title'>Their biggest ads so far</div>")
        gads = S.ads_between(R, pd.Timestamp("2026-07-01"), pd.Timestamp(asof) - pd.Timedelta(days=1))
        gads = gads[(gads["side"] == "GOP side") & (gads["body"].fillna("").str.len() > 20)]
        gads = gads.sort_values("p_spend", ascending=False).drop_duplicates("body").head(3)
        if len(gads):
            render_ads(gads, "before the planning date")
        else:
            st.caption("No Republican ads with text before the planning date.")

    section("Use it in the model", "These settings change the prediction and the recommended plan in step 3.")
    with st.container(border=True):
        i1, i2 = st.columns([5, 4], gap="large")
        with i1:
            st.toggle("Account for opponent ads", key=wk("opp_on"), on_change=_persist, args=("opp_on",),
                      help="Our ads' effect in each area is divided by (1 + strength × Republican share of voice there).")
            st.slider("How much their ads blunt ours (strength)", 0.0, 1.5, step=0.1, key=wk("opp_lambda"), on_change=_persist, args=("opp_lambda",),
                      disabled=not ss[wk("opp_on")],
                      help="0 = no effect. 0.5 is the model's cautious preset. An assumption, not a measurement.")
            source("All Republican messaging counts: their spend in each area, who their Meta ads reach, and what they "
                   "spend on each issue (used in step 3).")
        ps = current_settings()
        with i2:
            ap = S.audience_pressure(R, ps.asof)
            with st.spinner("Running the model…"):
                eff = S.opponent_effect(ps, S.recommend(ps) if ss[k("mix")] is None else S.mix_from(ss[k("mix")]))
            cA, cB = st.columns(2, gap="small")
            with cA:
                kpi("Pressure on persuasion", f"{ap['idx']['persuasion']:.2f}×", "unaffiliated voters vs all voters")
            with cB:
                kpi("Pressure on turnout", f"{ap['idx']['mobilization']:.2f}×", "low-turnout Democrats vs all voters")
            if ps.opp_on and ps.opp_lambda > 0:
                lost = eff["votes_without"] - eff["votes_with"]
                kpi("What opponent ads cost the plan", f"−{fmt_num(lost)} net votes",
                    f"win chance {eff['win_without']:.1%} → {eff['win_with']:.1%} with opponent pressure")
            else:
                kpi("What opponent ads cost the plan", "not counted", "turn on 'Account for opponent ads'")
        source("How it enters the model: each area's Republican share of voice (step 1) scales our ads' effect there; the "
               "pressure indices compare Republican share of Meta impressions in each audience's age profile with all "
               "voters (above 1× = more contested) and scale that audience's effect. Meta age bands are mapped to "
               "voter-file age groups approximately; message content itself is not modeled.")
    step_nav(2)

# ---------------------------------------------------------------------------- step 3 · our messaging
elif STEP == 3:
    ts = S.theme_stats(R, ps.asof)
    usable = ts[ts["enough_data"]]
    ok = set(usable["theme"])
    opts = ts["theme"].tolist() + [t for t in ss[wk("msg_themes")] if t not in set(ts["theme"])]
    section("What we say",
            "Pick up to three message themes for our ads and their mix. The model scores each by who ads on that theme "
            "reach and how much Republicans spend on it; the plan in the next step re-optimizes for your choice.")
    with st.container(border=True):
        c1, c2 = st.columns([5, 4], gap="large")
        with c1:
            st.multiselect("Messages we run", opts, key=wk("msg_themes"), on_change=_persist, args=("msg_themes",), max_selections=3,
                           format_func=lambda t: themes_avail.get(t, t) + ("" if t in ok else " (no data at this date)"),
                           placeholder="No specific theme")
            dropped = [themes_avail.get(t, t) for t in ss[wk("msg_themes")] if t not in ok]
            if dropped:
                st.caption("Not modeled at this planning date (too little ad data): " + ", ".join(dropped) + ".")
            chosen = [t for t in ss[wk("msg_themes")] if t in ok]
            if len(chosen) > 1:
                for t in chosen:
                    if not ss.get(wk(f"msg_w_{t}")):
                        setw(f"msg_w_{t}", max(5, int(round(100 / len(chosen) / 5) * 5)))
                    st.slider(f"Share of messaging: {themes_avail.get(t, t)}", 5, 100, step=5, key=wk(f"msg_w_{t}"),
                              on_change=_persist, args=(f"msg_w_{t}",), help="Relative weight; shares are normalized.")
            thin = ts[~ts["enough_data"]]["label"].tolist()
            if thin:
                source("Not enough Meta delivery data before the planning date to score: " + ", ".join(thin) + ".")
        ps = current_settings()
        with c2:
            with st.spinner("Running the model…"):
                base_ps = replace(ps, messages=())
                if ss[k("mix")] is None:  # recommended plan: re-optimized for each message choice
                    r_mine = S.predict(ps, S.mix_key(S.recommend(ps)))
                    r_none = S.predict(base_ps, S.mix_key(S.recommend(base_ps)))
                else:  # edited plan: same dollars, different messages
                    r_mine = S.predict(ps, ss[k("mix")])
                    r_none = S.predict(base_ps, ss[k("mix")])
            mult = S.message_multipliers(R, ps.asof, ps.messages, ps.opp_lambda if ps.opp_on else 0.0)
            kA, kB = st.columns(2, gap="small")
            with kA:
                kpi("Net votes with this messaging", f"≈{fmt_num(r_mine.total_delta_votes)}",
                    f"vs ≈{fmt_num(r_none.total_delta_votes)} with no specific theme")
            with kB:
                kpi(S.win_word(ps, S.race_context(ps)[0]), f"{r_mine.win_prob:.1%}",
                    f"vs {r_none.win_prob:.1%} with no specific theme")
            kC, kD = st.columns(2, gap="small")
            with kC:
                kpi("Effect on persuasion", f"{mult['persuasion']:.2f}×", "fit × contest, unaffiliated voters")
            with kD:
                kpi("Effect on turnout", f"{mult['mobilization']:.2f}×", "fit × contest, low-turnout Democrats")
    with st.container(border=True):
        e1, e2 = st.columns(2, gap="medium")
        with e1:
            _md("<div class='wr-card-title'>Predicted net votes if all our messaging were one theme</div>")
            with st.spinner("Comparing messages…"):
                mc = S.message_comparison(ps)
            chart(message_chart(mc, set(ss[wk("msg_themes")]) if len(ss[wk("msg_themes")]) == 1 else set()))
            source("Each bar re-optimizes the plan for that single message (1,500 simulations each). Hover for the fit "
                   "and contest behind it.")
        with e2:
            _md("<div class='wr-card-title'>Who is spending on each issue</div>")
            if len(usable):
                chart(issue_spend_chart(usable))
            source("Meta race-ad spend on each theme before the planning date (themes from ad text). A theme Republicans "
                   "flood dilutes our voice on it in the model; one they leave alone does not.")
    with st.container(border=True):
        sel = [t for t, _ in ps.messages]
        dads = S.ads_between(R, pd.Timestamp("2026-07-01"), pd.Timestamp(ps.asof) - pd.Timedelta(days=1))
        dads = dads[(dads["side"] == "Dem side") & (dads["body"].fillna("").str.len() > 20) & (dads["p_impr"] > 0)]
        if sel:
            hit = dads[dads["message_themes"].map(lambda ts: bool(set(sel) & set(ts if ts is not None else [])))]
            note = "on your chosen messages" if len(hit) else "(none ran on your chosen messages yet, so all Democratic ads)"
            dads = hit if len(hit) else dads
        else:
            note = "on any message"
        dads = dads.sort_values("p_impr", ascending=False).drop_duplicates("body").head(3)
        _md(f"<div class='wr-card-title'>Democrats' most-seen ads {html.escape(note)}</div>")
        if len(dads):
            render_ads(dads, "before the planning date")
            source("Ranked by NC impressions (reach). The ad libraries report spend and impressions only, not clicks or "
                   "persuasion, so 'top performing' here means most seen.")
        else:
            st.caption("No Democratic ads with text before the planning date.")
    source("What the model can and can't say: it captures who a message's ads tend to reach and how contested the "
           "issue is. It does not know how persuasive a given ad is; those differences are real but unmeasured here. "
           f"Theme scores rest on few ads ({', '.join(f'{r.label} {r.ads}' for r in usable.itertuples())}).")
    step_nav(3)



# ---------------------------------------------------------------------------- step 4 · plan & prediction
elif STEP == 4:
    with st.spinner("Running the model…"):
        M = model_state(ps, ss[k("mix")])
    res, plan, mm = M["res"], M["plan"], M["mm"]
    hc, mc = st.columns([8, 1.4], vertical_alignment="bottom")
    with hc:
        section("Where to put the money",
                ("Your edited plan" if edited else "The model's recommended plan") + f" for {fmt_money(ps.budget)}, "
                f"{ps.weeks} weeks out, " + ("with" if ps.opp_on and ps.opp_lambda > 0 else "without")
                + " opponent pressure. Model, not forecast: compare plans, don't read it as a prediction of the result.")
    with mc, st.popover("Model", width="stretch", icon=":material/tune:"):
        st.segmented_control("How well do ads work?", list(S.PRESETS), key=wk("preset"), on_change=_persist, args=("preset",), format_func=S.PRESETS.get)
        st.slider("National mood vs 2024 (pts toward Democrats)", -10.0, 20.0, step=0.5, key=wk("env"), on_change=_persist, args=("env",),
                  help="+5 is a typical midterm swing against the president's party; 0 = same as 2024.")
        st.multiselect("Platforms the plan may use", list(WR.WR_CHANNELS), key=wk("platforms"), on_change=_persist, args=("platforms",),
                       format_func=WR.PLATFORM_LABELS.get)
        st.segmented_control("When to spend", list(WR.TIMINGS), key=wk("timing"), on_change=_persist, args=("timing",), format_func=WR.TIMINGS.get)
    with st.container(border=True):
        _md(f"<div class='wr-headline'>{html.escape(M['head'])}</div>")
        k1, k2, k3, k4 = st.columns(4, gap="small")
        lo, hi = res.win_prob_interval
        with k1:
            kpi(M["ww"], f"{res.baseline_win_prob:.0%} → {res.win_prob:.0%}", f"range {lo:.0%}–{hi:.0%} with this plan")
        with k2:
            a_, b_ = res.total_delta_interval
            kpi("Net votes gained", f"≈{fmt_num(res.total_delta_votes)}", f"10–90%: {fmt_num(a_)}–{fmt_num(b_)}")
        with k3:
            kpi("Cost per net vote", fmt_money(res.cost_per_net_vote) if res.total_delta_votes > 0 else "—",
                f"{fmt_money(res.total_spent)} planned of {fmt_money(ps.budget)}")
        with k4:
            if ps.opp_on and ps.opp_lambda > 0:
                eff = S.opponent_effect(ps, M["mix"])
                kpi("Opponent pressure", f"−{fmt_num(eff['votes_without'] - eff['votes_with'])} votes",
                    f"strength {ps.opp_lambda:.1f} · set in step 2")
            else:
                kpi("Opponent pressure", "off", "set in step 2")
        m1, m2 = st.columns([6, 5], gap="medium")
        with m1:
            _md(f"<div class='wr-card-title'>Planned dollars by {W['unit_word']}</div>")
            chart(plan_map(plan, 360 if UT == "county" else 400))
        with m2:
            _md(f"<div class='wr-card-title'>Top {min(10, len(plan))} {W['units_word']} in the plan</div>")
            if len(plan):
                chart(plan_bars(plan))
                if len(plan) > 10:
                    source(f"Plus {len(plan) - 10} more {W['units_word']} with {fmt_money(plan['budget'].iloc[10:].sum())}.")
            else:
                st.info("No money is planned. Reset to the recommended plan or add rows under 'Adjust the plan'.")
        source("Sources: War Room model (2024 NCSBE starting margins shifted by the national mood, NCSBE voter-file "
               "audience sizes, ad prices and opponent spend/reach from the Google and Meta ad libraries).")

    st.write("")
    section("What the money buys", "Which messaging investment (platform × audience goal) returns the most, and what more "
                                   "or less budget would do. Inputs: region, platform, audience goal, timing, dollars, opponent pressure "
                                   "and our message mix (fit and contest); what an ad says is not modeled.")
    with st.container(border=True):
        w1, w2 = st.columns(2, gap="medium")
        with w1:
            _md("<div class='wr-card-title'>Net votes per $100K, by platform and goal</div>")
            if len(mm):
                chart(mix_chart(mm))
                source("Expected net votes for this plan's dollars on each platform and goal. Diminishing returns: the "
                       "first dollars in a region buy more than the last.")
            else:
                st.caption("No money is planned.")
        with w2:
            _md("<div class='wr-card-title'>Win chance vs budget</div>")
            chart(curve_chart(S.budget_curve(ps), ps.budget, M["ww"], (res.total_spent, res.win_prob) if edited else None))
            source("The recommended plan at ¼×, ½×, 1×, 1½× and 2× the budget (dashed line = current budget"
                   + ("; violet diamond = your edited plan" if edited else "") + "). A flat curve means extra money buys "
                   "little.")

    with st.expander(("Adjust the plan · edited" if edited else "Adjust the plan") + f" · {len(plan)} {W['units_word']}"):
        rows = WR.plan_rows(M["mix"])
        view = pd.DataFrame({
            "Region": rows["unit_id"].map(labels) if len(rows) else pd.Series(dtype=str),
            "Budget": rows["budget"].round(-2) if len(rows) else pd.Series(dtype=float),
            "Goal": rows["goal"].map(WR.GOAL_LABELS) if len(rows) else pd.Series(dtype=str),
            "Platforms": rows["channels"].map(lambda cs: [WR.PLATFORM_LABELS[c] for c in cs]) if len(rows)
            else pd.Series(dtype=object)})
        new = st.data_editor(
            view, key=f"wre_{R}_{ss[k('ed_nonce')]}", num_rows="dynamic", hide_index=True, width="stretch",
            column_config={
                "Region": st.column_config.SelectboxColumn(W["unit_word"].title(), options=sorted(labels.values()),
                                                           required=True),
                "Budget": st.column_config.NumberColumn("Budget", min_value=0, step=10_000, format="dollar"),
                "Goal": st.column_config.SelectboxColumn("Goal", options=list(WR.GOAL_LABELS.values())),
                "Platforms": st.column_config.MultiselectColumn("Platforms", options=list(WR.PLATFORM_LABELS.values()))})
        goal_ids = {v: kk for kk, v in WR.GOAL_LABELS.items()}
        plat_ids = {v: kk for kk, v in WR.PLATFORM_LABELS.items()}

        def _rows(df: pd.DataFrame) -> pd.DataFrame:
            out = []
            for r in df.itertuples(index=False):
                uid = ids_by_label.get(r.Region)
                budget = float(r.Budget) if pd.notna(r.Budget) else 0.0
                plats = [plat_ids[p] for p in (r.Platforms if isinstance(r.Platforms, list) else []) if p in plat_ids]
                if uid and budget > 0:
                    out.append({"unit_id": uid, "budget": round(budget, -2), "goal": goal_ids.get(r.Goal, "both"),
                                "channels": plats or ["meta"]})
            return pd.DataFrame(out, columns=["unit_id", "budget", "goal", "channels"])

        before, after = _rows(view), _rows(new)
        if not before.astype(str).equals(after.astype(str)):
            ss[k("mix")] = S.mix_key(WR.apply_rows(M["mix"], after))
            ss[k("ed_nonce")] += 1
            st.rerun()

        def _reset() -> None:
            ss[k("mix")] = None
            ss[k("ed_nonce")] += 1

        e1, e2 = st.columns([1.6, 5], vertical_alignment="center")
        e1.button("Reset to recommended", key="wrb_reset", on_click=_reset, disabled=not edited, width="stretch")
        e2.caption("Edit amounts, goals or platforms, or add rows; every number above updates. An edited plan is kept "
                   "when settings change; reset to re-optimize.")
    step_nav(4)

# ---------------------------------------------------------------------------- step 5 · Gemini
else:
    with st.spinner("Running the model…"):
        M = model_state(ps, ss[k("mix")])
    res, plan = M["res"], M["plan"]
    section("Why it works, and what could improve",
            "Gemini reads the model's predictions, the plan, both sides' spending and the opponent's messaging and reach "
            "(all before the planning date) and explains them. It changes the plan only with your permission "
            "(below).")
    _md(f"<div class='wr-headline'>{html.escape(M['head'])}</div>")
    with st.container(border=True):
        g1, g2 = st.columns([1, 1], gap="large")
        with g1:
            _md("<div class='wr-card-title'>Analyze this plan</div>")
            st.text_input("Anything to focus on? (optional)", key=wk("focus"), on_change=_persist, args=("focus",),
                          placeholder="e.g. How should we respond to their economy messaging?")
            go = st.button("Analyze with Gemini", key="wrb_analyze", type="primary", width="stretch",
                           icon=":material/auto_awesome:", disabled=res.total_spent <= 0)
            if not S.gemini_api_key():
                source("Gemini is not configured: add GEMINI_API=<key> to .env.")
            if go:
                with st.status("Analyzing the plan…", expanded=True) as status:
                    st.write("1 · Model outputs: win chance, net votes, next-$100K values, budget curve, sensitivity.")
                    st.write("2 · Plan, settings, both sides' spend, opponent themes and reach before the planning date.")
                    st.write("3 · Asking Gemini (structured output)… this can take a minute.")
                    try:
                        result = S.analyze_plan(ps, M["mix"], str(ss[wk("focus")]))
                    except S.GeminiError as exc:
                        status.update(label="Analysis failed", state="error")
                        st.error(str(exc))
                    else:
                        status.update(label=f"Analysis ready ({result['model']})", state="complete")
                        ss[k("result")] = result
                        ss["wr_view"] = "analysis"
                        st.rerun()
            if ss.get(k("result")):
                st.button("Open the last analysis", key="wrb_open_last", width="stretch",
                          on_click=lambda: ss.update(wr_view="analysis"))
        with g2:
            _md("<div class='wr-card-title'>Ask a quick question</div>")
            with st.form("wr_ask_form", border=False):
                st.text_input("Question", key=wk("ask"), label_visibility="collapsed",
                              placeholder=f"e.g. Why does {plan['label'].iloc[0] if len(plan) else 'this area'} get the "
                                          "most?")
                asked = st.form_submit_button("Ask Gemini", width="stretch", icon=":material/chat:")
            if asked and str(ss[wk("ask")]).strip():
                with st.spinner("Asking Gemini…"):
                    try:
                        ss[k("qa")].insert(0, S.ask(ps, M["mix"], str(ss[wk("ask")])))
                    except S.GeminiError as exc:
                        st.error(str(exc))
            for item in ss[k("qa")][:2]:
                _md(f"<div class='wr-label'>{esc(item['question'])}</div><div class='wr-headline'>"
                    f"{esc(item['answer'])}</div>")
                md_list([o["text"] + (f" ({SRC_SHORT.get(o['source'], o['source'])})" if o["source"] else "")
                         for o in item["observations"][:3]])
                md_list(item["interpretations"], "why wr-interp")
                if item["not_available"]:
                    _md("<div class='source'>Not in the data: " + esc("; ".join(item["not_available"])) + "</div>")
    st.write("")
    section("Let Gemini change the plan",
            "Give Gemini permission for the parts it may change. Its proposal is checked (known areas and themes, within "
            "the budget) and scored by the model; it gets one chance to revise using that score. It is applied only if "
            "the model predicts it is at least as good as your current plan, and you can undo it.")
    last = ss.get(k("agent"))
    perms = {p for p in S.PERMISSIONS if ss[wk(f"perm_{p}")]}
    head = ("Permissions and instructions · may change: " + (", ".join(S.PERMISSIONS[p].split(" (")[0].lower()
                                                                       for p in sorted(perms)) or "nothing yet"))
    with st.expander(head, expanded=not last, icon=":material/smart_toy:"):
        _md("<div class='wr-label'>Gemini may change</div>")
        for col, (key_, lab_) in zip(st.columns(3, gap="small"), S.PERMISSIONS.items()):
            with col:
                st.checkbox(lab_, key=wk(f"perm_{key_}"), on_change=_persist, args=(f"perm_{key_}",))
        perms = {p for p in S.PERMISSIONS if ss[wk(f"perm_{p}")]}
        i1, i2 = st.columns([3, 1.3], vertical_alignment="bottom", gap="small")
        with i1:
            st.text_input("Instructions for Gemini (optional)", key=wk("agent_note"), on_change=_persist,
                          args=("agent_note",), placeholder="e.g. Keep at least $200K in Wake; focus on turnout.")
        with i2:
            run_agent = st.button("Let Gemini improve the plan", key="wrb_agent", type="primary", width="stretch",
                                  icon=":material/smart_toy:", disabled=not perms or res.total_spent <= 0)
        if run_agent:
            with st.status("Gemini is revising the plan…", expanded=True) as status:
                st.write("1 · Sending the plan, model outputs, both sides' spend and messaging (" +
                         ", ".join(sorted(perms)) + " may change).")
                st.write("2 · Validating Gemini's proposal and scoring it with the model; one revision round.")
                try:
                    out = S.gemini_plan(ps, M["mix"], perms, str(ss[wk("agent_note")]))
                except S.GeminiError as exc:
                    status.update(label="Gemini could not change the plan", state="error")
                    st.error(str(exc))
                else:
                    best, before = out["best"], out["before"]
                    better = (best["after"]["win_prob"], best["after"]["net_votes"]) >= (before["win_prob"],
                                                                                        before["net_votes"])
                    out["applied"] = better
                    if better:
                        prev = {"mix": ss[k("mix")], "msgs": message_state()}
                        # Freeze the plan that was scored: a recommended plan would otherwise re-optimize when
                        # messages change, moving area dollars without the 'areas' permission.
                        ss[k("mix")] = best["mix"]
                        ss[k("ed_nonce")] += 1
                        if "messages" in perms:
                            set_messages(best["messages"])
                        ss[k("undo")] = {**prev, "scopes": {"mix", "messages"} if "messages" in perms else {"mix"},
                                         "applied_mix": ss[k("mix")], "applied_msgs": message_state()}
                    ss[k("agent")] = out
                    status.update(label="Applied Gemini's changes" if better else "Kept your plan: Gemini's "
                                  "proposal scored lower", state="complete")
                    st.rerun()
    out = ss.get(k("agent"))
    if out:
        render_agent_result(out)
    step_nav(5)

source("Detail by region: Region Analysis. All opponent ads: Opponent Tracker.")
for _key in [x for x in ss if str(x).startswith(f"wrw_{R}_")]:
    ss[f"wrp_{_key[4:]}"] = ss[_key]
