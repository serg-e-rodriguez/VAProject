"""
Region Analysis: the NC map for the selected race (counties for Senate, districts for House).
Selecting a region opens its Audience Analysis — who lives there, who they lean to, why, and
what it takes for us to win it.
"""

import html
import json

import pandas as pd
import streamlit as st

from campaign_intel import model_check as M
from campaign_intel.config import RACES
from campaign_intel.data.loaders import (
    DIM_ORDER,
    fmt_margin,
    fmt_money,
    fmt_num,
    google_cd_reported,
    load_demographics,
    load_regions,
    party_totals,
    path_to_win,
    region_advertisers,
    statewide_untargeted,
    timeframe_label,
    unit_type,
)
from campaign_intel.state import race, set_state, theme
from campaign_intel.ui.components import (
    bullets,
    callout,
    chart,
    kpi,
    kpi_vs,
    no_data,
    page_header,
    party_tone,
    pill,
    section,
    source,
    timeframe_banner,
)
from campaign_intel.viz.charts import party_mix, ranked_bars, turnout_gap
from campaign_intel.viz.maps import choropleth

R, T = race(), theme()
UT = unit_type(R)
words = RACES[R]
regions = load_regions(R).merge(M.estimates(R)[["unit_id", "proj_pct"]], on="unit_id", how="left")
by_id = regions.set_index("unit_id")

page_header("Region Analysis",
            f"Click a {words['unit_word']} on the map (or pick one from the list) to open its Audience Analysis.")
cov = timeframe_banner(R, sources=("google",))  # area-level ad spend comes from Google's geo-targeting only
TF = timeframe_label()

# ----------------------------------------------------------------------------- map
METRICS = {
    "2024 lean": ("dem_margin_pct", "2024 margin (D−R)", "diverging", "+.1f"),
    "Model estimate": ("proj_pct", "Model estimate (D−R)", "diverging", "+.1f"),
    "Turnout 2022": ("turnout22", "2022 midterm turnout", "sequential_neutral", ".0%"),
    "Dems to turn out": ("dems_skipped22", "Registered Dems who didn't vote in 2022", "sequential", ",.0f"),
    "Ad edge": ("ad_net_dem", "Geo-targeted ad spend, Dem minus GOP ($)", "diverging", "$,.0f"),
}
# Shown when the pointer rests on an option (and under the map for the selected one).
METRIC_HELP = {
    "2024 lean": f"Our starting point: the 2024 presidential margin in each {words['unit_word']}, Democrat minus "
                 "Republican, in points. Blue = the Democrat carried it, red = the Republican did.",
    "Model estimate": f"Where the model expects each {words['unit_word']} to land this midterm before any new ads: "
                      "the 2024 margin on a midterm-sized electorate, shifted by the national-mood assumption "
                      f"({M.DEFAULT_ENV:+.0f} pts toward Democrats). Blue = we are favoured, red = they are.",
    "Turnout 2022": f"Share of registered voters in each {words['unit_word']} who voted in the last midterm (2022). "
                    "Stronger colour = higher turnout.",
    "Dems to turn out": "Registered Democrats who skipped the 2022 midterm: the voters a turnout program goes after. "
                        "Stronger blue = more of them.",
    "Ad edge": f"Google ad dollars aimed at each {words['unit_word']} in this race, Democrats minus Republicans. "
               "Blue = we out-spend them, red = they out-spend us. Statewide and Meta ads are not included.",
}


def _metric_tooltips() -> None:
    """Give each 'Colour the map by' option a native hover tooltip (the browser shows it after a short pause).
    Streamlit's segmented control has no per-option help, so a small script sets each button's title."""
    st.html("<script>(function(){window.__mapMetricTips=" + json.dumps(METRIC_HELP) + ";"
            "const apply=()=>document.querySelectorAll('.st-key-map_metric button').forEach(b=>{"
            "const t=(window.__mapMetricTips||{})[b.innerText.trim()];if(t&&b.title!==t)b.title=t;});"
            "apply();if(!window.__mapMetricObs){window.__mapMetricObs=new MutationObserver(apply);"
            "window.__mapMetricObs.observe(document.body,{childList:true,subtree:true});}})();</script>",
            unsafe_allow_javascript=True)


def _pick_from_list():
    set_state(region=st.session_state["region_select"])


def _pick_from_map(key: str):
    """Map click: select that area. Runs only when the map's selection actually changes."""
    try:
        sel = st.session_state[key]["selection"]["unit_pick"] or []
    except (KeyError, TypeError):
        sel = []
    uid = str(sel[0].get("unit_id") or sel[0].get("properties.unit_id") or "") if sel else ""
    if uid in by_id.index:
        st.session_state["_map_pick"] = uid
        st.session_state["region_select"] = uid  # keep the dropdown in step with the map
        set_state(region=uid)


cur = st.session_state.get("region")
cur = cur if cur in by_id.index else None
# The area was changed somewhere other than the map (the dropdown, another page, the race switch): start the
# map with a fresh selection. Otherwise its old click is still "selected", and clicking that area again
# (or, after a redraw, any area) does not register as a change, so nothing happens.
if st.session_state.get("_map_pick") not in (None, cur):
    st.session_state["_map_nonce"] = st.session_state.get("_map_nonce", 0) + 1
    st.session_state["_map_pick"] = None
map_key = f"region_map_{st.session_state.get('_map_nonce', 0)}"
if st.session_state.get("region_select") != cur:
    st.session_state["region_select"] = cur

with st.container(border=True):
    top_l, top_r = st.columns([7, 3], vertical_alignment="bottom")
    with top_l:
        metric = st.segmented_control(
            "Colour the map by", list(METRICS), default=list(METRICS)[0], key="map_metric",
            help="Rest the pointer on an option to see what it shows.") or list(METRICS)[0]
        _metric_tooltips()
    with top_r:
        opts = regions.sort_values("district_num" if UT == "cd" else "label")["unit_id"].tolist()
        st.selectbox(f"Or pick a {words['unit_word']}", opts, index=None,
                     format_func=lambda u: by_id.loc[u, "label"], placeholder=f"Search {words['units_word']}…",
                     key="region_select", on_change=_pick_from_list)
    col, label, scale, fmt = METRICS[metric]
    m_col, l_col = st.columns([8, 3], gap="medium")
    with m_col:
        dom = (40.0 if UT == "county" else 25.0) if col in ("dem_margin_pct", "proj_pct") else None
        map_chart = choropleth(UT, regions.assign(name=regions["label"]), col, label, scale=scale, theme=T, fmt=fmt,
                               extra_tooltips=[("dem_margin_pct", "2024 president (D−R)", "+.1f"),
                                               ("proj_pct", "Model estimate (D−R)", "+.1f"),
                                               ("registered_voters", "Registered voters", ",.0f")],
                               highlight=cur, swing_pts=None, height=440 if UT == "county" else 470, domain_max=dom)
        chart(map_chart, on_select=lambda: _pick_from_map(map_key), selection_mode="unit_pick", key=map_key)
        st.caption(f"**{metric}:** {METRIC_HELP[metric]}")
        if col == "ad_net_dem" and not cov["google"]["has_data"]:
            no_data(f"No Google ads in {TF}, so there is no geo-targeted spend to map (every area shows $0).")
        source("Map colours: blue = Democratic, red = Republican. Hover for details, click to select.")
    with l_col:
        if R == "senate":
            section("Where our votes are", "Counties with the most registered Democrats who skipped the 2022 midterm.")
            top = regions.nlargest(10, "dems_skipped22")[["label", "dems_skipped22"]]
            st.dataframe(top, hide_index=True, width="stretch", height=390,
                         column_config={"label": "County",
                                        "dems_skipped22": st.column_config.NumberColumn("Dems to turn out", format="%d")})
        else:
            section("Battlegrounds", "Districts by 2024 presidential margin (closest first).")
            b = regions.assign(abs_m=regions["dem_margin_pct"].abs()).sort_values("abs_m")
            st.dataframe(b[["label", "lean", "dem_margin_pct", "proj_pct"]], hide_index=True,
                         width="stretch", height=420,
                         column_config={"label": "District", "lean": "Rating",
                                        "dem_margin_pct": st.column_config.NumberColumn("2024", format="%+.1f"),
                                        "proj_pct": st.column_config.NumberColumn("Model", format="%+.1f")})

if not cur:
    callout(f"Select a {words['unit_word']} on the map to see its Audience Analysis.")
    st.stop()

# ----------------------------------------------------------------------------- audience analysis
u = by_id.loc[cur]
pt = party_totals(UT, cur)
pts = pt.set_index("party")
state_pt = party_totals("state", "NC").set_index("party")
ptw = path_to_win(u["dem_margin_pct"], u["expected_turnout"], pt)

st.markdown("<div class='group-title'>Audience Analysis</div>", unsafe_allow_html=True)
m24, mest = u["dem_margin_pct"], u["proj_pct"]
heads = [pill(f"{u['lean']} (2024 president: {fmt_margin(m24)})", "dem" if m24 > 0 else "rep")]
if pd.notna(mest):
    heads.append(pill(f"Model estimate: {fmt_margin(mest)}", "dem" if mest > 0 else "rep"))
if UT == "cd":
    heads.append(pill(f"{u['dem_candidate']} (D) vs {u['rep_candidate']} (R)"))
st.markdown(f"<div class='region-head'><h2>{html.escape(u['label'])}</h2>{''.join(heads)}</div>", unsafe_allow_html=True)

reg_tot = pt["reg24"].sum()
dem_t, rep_t, una_t = (pts.loc[p, "turnout22"] for p in ("Dem", "Rep", "Unaffiliated"))
k1, k2, k3, k4 = st.columns(4, gap="small")
with k1:
    kpi("Registered voters", fmt_num(reg_tot),
        f"D {pts.loc['Dem', 'reg24'] / reg_tot:.0%} · R {pts.loc['Rep', 'reg24'] / reg_tot:.0%} · "
        f"Unaffiliated {pts.loc['Unaffiliated', 'reg24'] / reg_tot:.0%}")
with k2:
    kpi("2022 midterm turnout", f"{u['turnout22']:.0%}", f"Dems {dem_t:.0%} · Reps {rep_t:.0%} · Unaffiliated {una_t:.0%}",
        )
with k3:
    kpi("Where we start", fmt_margin(m24),
        (f"≈{fmt_num(ptw['gap'])} net votes to make up in a midterm" if ptw["gap"] > 0
         else f"≈{fmt_num(-ptw['gap'])} net-vote cushion in a midterm"), tone=party_tone(m24))
with k4:
    if cov["google"]["has_data"]:
        kpi_vs("Targeted ads here", fmt_money(u["ad_dem"]), fmt_money(u["ad_gop"]),
               f"Democrats vs Republicans · Google ads aimed at this area · {TF}")
    else:
        kpi("Targeted ads here", "No data", f"No Google ads in {TF}")

# Demographic breakdowns
st.write("")
DIM_LABEL = {"age": "Age", "race": "Race / ethnicity", "gender": "Gender"}
dim = st.segmented_control("Break voters down by", list(DIM_LABEL), default="age", format_func=DIM_LABEL.get,
                           key="aud_dim") or "age"
demo = load_demographics(UT, cur, dim)
order = DIM_ORDER[dim]
d1, d2 = st.columns(2, gap="medium")
with d1, st.container(border=True):
    section(f"Who lives here, by {DIM_LABEL[dim].lower()}", "Party registration within each group (number = registered voters).")
    chart(party_mix(demo, order, T))
with d2, st.container(border=True):
    section(f"Who shows up, by {DIM_LABEL[dim].lower()}",
            "Share of registered Democrats vs Republicans in each group who voted in the 2022 midterm.")
    chart(turnout_gap(demo, order, T))

# Why it leans + path to win
w1, w2 = st.columns([6, 6], gap="medium")
leans_d = m24 > 0
with w1, st.container(border=True):
    section(f"Why {u['label']} leans {'Democratic' if leans_d else 'Republican'}")
    why = []
    d_sh, r_sh = pts.loc["Dem", "reg24"] / reg_tot, pts.loc["Rep", "reg24"] / reg_tot
    sd = state_pt.loc["Dem", "reg24"] / state_pt["reg24"].sum()
    sr = state_pt.loc["Rep", "reg24"] / state_pt["reg24"].sum()
    why.append(f"Registration: {d_sh:.0%} Democrats vs {r_sh:.0%} Republicans "
               f"(statewide {sd:.0%} vs {sr:.0%}). "
               + ("Democrats out-register Republicans here." if d_sh > r_sh else "Republicans out-register us here."))
    tg = (rep_t - dem_t) * 100
    if abs(tg) >= 1:
        why.append(f"Turnout: {rep_t:.0%} of registered Republicans voted in 2022 vs {dem_t:.0%} of Democrats — "
                   + (f"a {tg:.0f}-point turnout edge for the GOP." if tg > 0 else f"a {-tg:.0f}-point edge for us."))
    race_mix = load_demographics(UT, cur, "race").groupby(["group", "party"])["reg24"].sum().unstack().fillna(0)
    race_mix = race_mix.reindex(columns=["Dem", "Rep", "Unaffiliated", "Other party"], fill_value=0)
    size = race_mix.sum(axis=1)
    big = race_mix[(size / size.sum() >= 0.08) & (race_mix.index != "Undesignated")]
    if len(big):
        lean = (big["Dem"] - big["Rep"]) / big.sum(axis=1)
        g_d, g_r = lean.idxmax(), lean.idxmin()
        if lean[g_d] > 0.1:
            why.append(f"Base: {g_d} voters are {size[g_d] / size.sum():.0%} of the rolls and register "
                       f"{big.loc[g_d, 'Dem'] / size[g_d]:.0%} Democratic.")
        if lean[g_r] < -0.05:
            why.append(f"Opposition: {g_r} voters are {size[g_r] / size.sum():.0%} of the rolls and register "
                       f"{big.loc[g_r, 'Rep'] / size[g_r]:.0%} Republican.")
    age = load_demographics(UT, cur, "age").groupby(["group", "party"])["reg24"].sum().unstack().fillna(0)
    young = age.loc[[g for g in ["18–25", "26–40"] if g in age.index]]
    if len(young):
        ys = young.sum().sum()
        why.append(f"Voters under 40 are {ys / age.sum().sum():.0%} of the rolls and "
                   f"{young['Unaffiliated'].sum() / ys:.0%} of them are unaffiliated — the persuasion pool.")
    if pd.notna(mest):
        why.append(f"The model expects {fmt_margin(mest)} here this midterm before any new ads "
                   f"(national mood {M.DEFAULT_ENV:+.0f} pts vs 2024 on a midterm-sized electorate).")
    bullets(why)
    source("NCSBE voter registration (Nov 2024) and 2022 voter history. Party = party of registration, "
           "not vote choice.")

with w2, st.container(border=True):
    section("Our path to win here")
    closing = max(0.0, (rep_t - dem_t)) * pts.loc["Dem", "reg24"]
    if ptw["gap"] > 0:
        callout(f"≈{fmt_num(ptw['gap'])} net votes behind at the 2024 margin",
                f"Turn out {ptw['mobilize_share']:.0%} of the {fmt_num(ptw['dems_skipped'])} Democrats who skipped 2022, "
                f"or win unaffiliated voters by {ptw['una_points']:.0f} more points (net).", tone="rep")
    else:
        callout(f"≈{fmt_num(-ptw['gap'])} net-vote cushion at the 2024 margin",
                f"Bank it: {fmt_num(ptw['dems_skipped'])} registered Democrats here skipped the 2022 midterm.",
                tone="dem")
    skipped = demo[demo["party"] == "Dem"].sort_values("skipped22", ascending=False)
    skipped = skipped[skipped["group"] != "Undesignated"].head(2)
    tips = []
    if closing >= 50:
        tips.append(f"Matching Republican turnout among our registered voters is worth ≈{fmt_num(closing)} votes here.")
    if len(skipped):
        tips.append("Biggest groups of Democrats who skipped 2022 (by " + DIM_LABEL[dim].lower() + "): "
                    + "; ".join(f"{r.group} ({fmt_num(r.skipped22)})" for r in skipped.itertuples()) + ".")
    tips.append(f"{fmt_num(pts.loc['Unaffiliated', 'reg24'])} unaffiliated voters live here; "
                f"{una_t:.0%} of them voted in 2022.")
    bullets(tips)

    section("Who's advertising here", f"Google ads geo-targeted to this area, this race, {TF}.")
    adv = region_advertisers(R, cur, n=6)
    if len(adv):
        chart(ranked_bars(adv, "advertiser", "spend", T, height=max(120, 34 * len(adv))))
    else:
        no_data(f"No geo-targeted Google ads for this race here in {TF}." if cov["google"]["has_data"]
                else f"No Google ads in {TF}.")
    un = statewide_untargeted(R)
    note = (f"Plus statewide ads that reach everyone (not geo-targeted, incl. all Meta): Democrats "
            f"{fmt_money(un.get('Dem side', 0))}, Republicans {fmt_money(un.get('GOP side', 0))}.")
    if UT == "cd":
        g = google_cd_reported(cur)
        if g:
            note += (f" Google reports {fmt_money(g)} in political ads (all advertisers) targeted to this district "
                     "over the whole cycle (Google's total; not limited to the timeframe).")
    source(note + " ZIP-targeted ads are split evenly across the ZIPs they target (approximate).")
