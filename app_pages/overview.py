"""
Overview: where the race stands, who is spending, and the electorate we have to win.
"""

import streamlit as st

from campaign_intel import model_check as M
from campaign_intel.data.loaders import (
    channel_by_side,
    fmt_margin,
    fmt_money,
    fmt_num,
    load_regions,
    load_statewide,
    party_totals,
    path_to_win,
    senate_nominees,
    spend_summary,
    timeframe_label,
    top_advertisers,
    weekly_by_side,
    went_dark,
)
from campaign_intel.state import race, theme
from campaign_intel.ui.components import (
    bullets,
    callout,
    chart,
    kpi,
    no_data,
    page_header,
    party_tone,
    pct,
    section,
    source,
    timeframe_banner,
)
from campaign_intel.viz.charts import (
    district_board,
    ranked_bars,
    registered_vs_voted,
    side_pair_bars,
    weekly_sides,
)

R, T = race(), theme()
sw = load_statewide()
s = spend_summary(R)
regions = load_regions(R)
pt = party_totals("state", "NC")
state_margin = (sw["pres24_dem"] - sw["pres24_rep"]) / sw["pres24_total"] * 100

# ----------------------------------------------------------------------------- header + KPIs
if R == "senate":
    nom = senate_nominees()
    page_header(f"US Senate · {nom['dem']} (D) vs {nom['rep']} (R)",
                "Where the race stands, who is spending, and the voters we need.")
else:
    page_header("US House · 14 congressional districts",
                "Where the seats stand, who is spending, and the voters we need in each district.")

cov = timeframe_banner(R)
TF = timeframe_label()
k1, k2, k3, k4 = st.columns(4, gap="small")
with k1:
    if s["partisan"]:
        kpi("Ad spend in this race", fmt_money(s["partisan"]),
            f"Democrats {fmt_money(s['dem'])} · Republicans {fmt_money(s['gop'])}",
            help=f"Google + Meta political ads attributed to this race, NC share, {TF}.")
    else:
        kpi("Ad spend in this race", "No data", f"No race ads found in {TF}")
with k2:
    d4 = (s["dem_share_4w"] - s["dem_share_prev4w"]) * 100
    kpi("Our share of the ad war", pct(s["dem_share"]) if s["partisan"] else "No data",
        f"Last 4 weeks {pct(s['dem_share_4w'])} ({pct(d4, signed=True)} vs the 4 before)" if s["partisan"]
        else "Nothing to compare in this timeframe",
        tone="dem" if s["partisan"] else "neutral",
        help="Democratic-side share of all Dem + GOP spend in this race.")
if R == "senate":
    ptw = path_to_win(state_margin, sw["voted22_total"], pt)
    with k3:
        kpi("Where we start", fmt_margin(state_margin),
            f"2024 president in NC · ≈{fmt_num(abs(ptw['gap']))} net votes to "
            f"{'make up' if ptw['gap'] > 0 else 'protect'} in a midterm",
            tone=party_tone(state_margin),
            help="2024 presidential margin applied to a 2022-sized midterm electorate.")
    est = M.estimates(R)
    est_pct = est["proj_votes"].sum() / est["proj_turnout"].sum() * 100
    with k4:
        kpi("Model estimate", fmt_margin(est_pct),
            f"Before new ads · {M.baseline_win_prob(R):.0%} chance to win · national mood {M.DEFAULT_ENV:+.0f} pts",
            tone=party_tone(est_pct),
            help="The model's baseline: 2024 margin on a midterm-sized electorate, shifted by the national-mood "
                 "assumption, before any new ad spending. Model Check compares it with the 2026 result.")
else:
    lean_d = int((regions["dem_margin_pct"] > 0).sum())
    battle = int((regions["dem_margin_pct"].abs() < 8).sum())
    held_d = int((regions["held_by_2024"] == "Dem").sum())
    regions = regions.merge(M.estimates(R)[["unit_id", "proj_pct"]], on="unit_id", how="left")
    fav_d = int((regions["proj_pct"] > 0).sum())
    with k3:
        kpi("Where we start", f"{lean_d} of 14 lean D",
            f"By 2024 president margin · {battle} battlegrounds within 8 pts", tone="dem")
    with k4:
        kpi("Model estimate", f"D {fav_d} – R {14 - fav_d}",
            f"Seats each side is favoured in before new ads · held after 2024: D {held_d} – R {14 - held_d}",
            tone=party_tone(fav_d - 7),
            help="The model's baseline per district: 2024 margin on a midterm-sized electorate, shifted by the "
                 "national-mood assumption, before any new ad spending.")

# ----------------------------------------------------------------------------- House: district board
if R == "house":
    st.markdown("<div class='group-title'>The seats</div>", unsafe_allow_html=True)
    with st.container(border=True):
        section("District by district: where we start and where the model has us",
                "Hollow dot = 2024 presidential margin on the new lines (our starting point). "
                f"Solid dot = the model's estimate (national mood {M.DEFAULT_ENV:+.0f} pts, before new ads). "
                "Shaded band = within 5 points.")
        chart(district_board(regions, T, end_col="proj_pct", end_title="Model estimate",
                             end_words=("Dem favoured", "Rep favoured")))
        close = regions[(regions["held_by_2024"] == "Rep") & (regions["proj_pct"].abs() < 8)]
        if len(close):
            source(f"Republican-held seats within 8 points in the model: {', '.join(close['label'])}. "
                   "These are the pickup targets.")

# ----------------------------------------------------------------------------- money
st.markdown("<div class='group-title'>The money</div>", unsafe_allow_html=True)
c1, c2 = st.columns([7, 5], gap="medium")
with c1, st.container(border=True):
    section("Who is out-spending whom, week by week", "Ad spend per week on Google and Meta, by side.")
    w = weekly_by_side(R)
    if w.empty:
        no_data(f"No weekly ad spend in {TF}.", "Pick a longer or later timeframe in the sidebar.")
    else:
        chart(weekly_sides(w, T))
    gop_trend = (s["gop_4w"] / s["gop_prev4w"] - 1) * 100 if s["gop_prev4w"] else 0
    dark = went_dark(s)
    if w.empty:
        pass
    elif dark:
        callout(f"Republicans have gone dark online since {dark}",
                f"No Republican Google or Meta ads (≥ $1K) in this race since {dark}. Last 4 weeks: "
                f"Democrats {fmt_money(s['dem_4w'])}, Republicans {fmt_money(s['gop_4w'])}.", tone="dem")
    else:
        source(f"Last 4 weeks: Democrats {fmt_money(s['dem_4w'])}, Republicans {fmt_money(s['gop_4w'])} "
               f"({gop_trend:+.0f}% vs the 4 weeks before).")
with c2, st.container(border=True):
    section("Biggest spenders", "Top 10 committees and PACs in this race.")
    top = top_advertisers(R, n=10)
    if top.empty:
        no_data(f"No Democratic or Republican advertisers in {TF}.")
    else:
        chart(ranked_bars(top, "advertiser", "spend", T, height=320))

c3, c4 = st.columns([5, 7], gap="medium")
with c3, st.container(border=True):
    section("Where each side puts its money", "Share of each side's spend by platform.")
    ch = channel_by_side(R)
    order = ch.groupby("channel")["spend"].sum().sort_values(ascending=False).index.tolist()
    if ch.empty:
        no_data(f"No platform spend in {TF}.")
    else:
        chart(side_pair_bars(ch, "channel", "share", T, order=order))
with c4, st.container(border=True):
    section("What the spending tells us")
    piv = ch.pivot_table(index="channel", columns="side_group", values="share", fill_value=0)
    items = []
    if {"Dem side", "GOP side"} <= set(piv.columns):
        main = piv.sum(axis=1).idxmax()
        items.append(f"Both sides fight mainly on {main}: {piv.loc[main, 'Dem side']:.0%} of our spend, "
                     f"{piv.loc[main, 'GOP side']:.0%} of theirs.")
        gap = (piv["GOP side"] - piv["Dem side"]).sort_values()
        if gap.iloc[-1] >= 0.03:
            items.append(f"Republicans put more into {gap.index[-1]} ({piv.loc[gap.index[-1], 'GOP side']:.0%} of their "
                         f"spend vs {piv.loc[gap.index[-1], 'Dem side']:.0%} of ours).")
        if gap.iloc[0] <= -0.03:
            items.append(f"We put more into {gap.index[0]} ({piv.loc[gap.index[0], 'Dem side']:.0%} vs "
                         f"{piv.loc[gap.index[0], 'GOP side']:.0%}).")
    if s["partisan"]:
        ratio = s["dem"] / s["gop"] if s["gop"] else float("inf")
        items.append(f"Across the race we spend ${ratio:.1f} for every $1 Republicans spend." if s["gop"] else
                     "No Republican spend attributed to this race yet.")
    t_gop = top[top["side_group"] == "GOP side"]
    if len(t_gop):
        items.append(f"Largest Republican spender: {t_gop.iloc[0]['advertiser']} ({fmt_money(t_gop.iloc[0]['spend'])}).")
    if items:
        bullets(items)
    else:
        no_data(f"No ad spend to compare in {TF}.")
    source(f"Spend is Google + Meta political ads attributed to this race, NC share only, {TF} "
           f"(midpoints of the ranges the platforms report). Not included: {fmt_money(s['other_races'])} from party "
           f"committees, issue groups and state/local races, and {fmt_money(s['unclassified'])} in this race from "
           f"groups we could not place on a side.")

# ----------------------------------------------------------------------------- electorate & turnout
st.markdown("<div class='group-title'>Electorate & turnout</div>", unsafe_allow_html=True)
e1, e2 = st.columns([6, 6], gap="medium")
with e1, st.container(border=True):
    section("Registered voters vs. who showed up in the 2022 midterm",
            "Light bar = registered · solid bar = voted. Statewide, by party registration.")
    chart(registered_vs_voted(pt, T))
    reg = pt.set_index("party")
    t22 = sw["voted22_total"] / pt["reg22"].sum()
    t24 = sw["pres24_total"] / sw["registered_2024"]
    source(f"Turnout drops from {t24:.0%} in a presidential year (2024) to {t22:.0%} in a midterm (2022). "
           f"Unaffiliated voters are the largest bloc ({reg.loc['Unaffiliated', 'reg24'] / pt['reg24'].sum():.0%} "
           f"of {fmt_num(pt['reg24'].sum())} registered) and the least likely to vote.")
with e2, st.container(border=True):
    dem_t, rep_t = reg.loc["Dem", "turnout22"], reg.loc["Rep", "turnout22"]
    if R == "senate":
        section("Our path to win statewide")
        if ptw["gap"] > 0:
            callout(f"We start ≈{fmt_num(ptw['gap'])} net votes behind",
                    f"NC voted {fmt_margin(state_margin)} for president in 2024. In a midterm-sized electorate "
                    f"({fmt_num(sw['voted22_total'])} voters) that is the deficit to close.", tone="rep")
        else:
            callout(f"We start ≈{fmt_num(-ptw['gap'])} net votes ahead", "Protect the lead.", tone="dem")
        bullets([
            f"Turnout: {fmt_num(ptw['dems_skipped'])} registered Democrats skipped the 2022 midterm. "
            f"Turning out {ptw['mobilize_share']:.0%} of them closes the gap on its own.",
            f"Persuasion: about {fmt_num(ptw['una_voters'])} unaffiliated voters cast midterm ballots. "
            f"Winning them by {ptw['una_points']:.1f} more points closes it too.",
            f"The turnout gap is the problem: {rep_t:.0%} of registered Republicans voted in 2022 vs "
            f"{dem_t:.0%} of registered Democrats.",
        ])
        source("Gap = 2024 presidential margin × 2022 turnout. Pools from NCSBE voter registration (2024) and "
               "2022 voter history. Mixes of both levers work too; see Region Analysis for where the votes are.")
    else:
        section("What it takes to flip our targets",
                "The 8 closest Republican-leaning districts by 2024 presidential margin. "
                "Votes to flip = that deficit in a midterm-sized electorate.")
        b = regions[regions["dem_margin_pct"] < 0].nlargest(8, "dem_margin_pct").copy()
        b["votes_needed"] = (-b["dem_margin_pct"] / 100 * b["expected_turnout"]).clip(lower=0)
        b["need_share"] = b["votes_needed"] / b["dems_skipped22"]
        b = b.sort_values("dem_margin_pct", ascending=False)
        st.dataframe(
            b[["label", "dem_candidate", "dem_margin_pct", "votes_needed", "dems_skipped22", "need_share"]],
            hide_index=True, width="stretch",
            column_config={
                "label": "District", "dem_candidate": "Our nominee",
                "dem_margin_pct": st.column_config.NumberColumn("2024 margin", format="%+.1f"),
                "votes_needed": st.column_config.NumberColumn("Votes to flip", format="%d"),
                "dems_skipped22": st.column_config.NumberColumn("Dems who skipped 2022", format="%d"),
                "need_share": st.column_config.ProgressColumn("Share of them to turn out", format="percent",
                                                              min_value=0.0, max_value=1.0),
            })
        source(f"Statewide, {rep_t:.0%} of registered Republicans voted in 2022 vs {dem_t:.0%} of registered "
               "Democrats — closing that turnout gap is the cheapest path in every district above.")
