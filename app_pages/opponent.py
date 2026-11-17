"""
Opponent Tracker: what Republicans are spending in this race, on which platforms, with which
messages, aimed at whom — and their latest ads.
"""

import pandas as pd
import streamlit as st

from campaign_intel.data.loaders import (
    audience_by_side,
    channel_by_side,
    fmt_money,
    load_creatives,
    new_activity,
    snapshot_date,
    spend_summary,
    themes_by_side,
    top_advertisers,
    weekly_by_channel,
    went_dark,
)
from campaign_intel.config import RACES
from campaign_intel.processing.themes import theme_labels
from campaign_intel.state import race, theme
from campaign_intel.ui.components import chart, ad_card, bullets, kpi, page_header, section, source
from campaign_intel.viz.charts import age_reach, channel_weeks, ranked_bars, side_pair_bars, theme_compare

R, T = race(), theme()
labels = theme_labels()
s = spend_summary(R)
snap = snapshot_date()
gop_adv = top_advertisers(R, "GOP side", n=12)
gop_adv = gop_adv[gop_adv["spend"] >= 1000]
cre = load_creatives(R, "GOP side")
ch = channel_by_side(R)
gop_ch = ch[ch["side_group"] == "GOP side"].sort_values("spend", ascending=False)

page_header(f"Opponent Tracker · {RACES[R]['label']}",
            "What Republicans are spending, where, on which messages, and who they are trying to reach.")

k1, k2, k3, k4 = st.columns(4, gap="small")
with k1:
    kpi("Republican spend this race", fmt_money(s["gop"]), f"vs our {fmt_money(s['dem'])} · since Jul 1",
        tone="bad" if s["gop"] > s["dem"] else "neutral")
with k2:
    chg = (s["gop_4w"] / s["gop_prev4w"] - 1) * 100 if s["gop_prev4w"] else 0
    dark = went_dark(s)
    kpi("Last 4 weeks", fmt_money(s["gop_4w"]),
        f"No ads since {dark} — they've gone dark" if dark else f"{chg:+.0f}% vs the 4 weeks before",
        tone="good" if dark or chg <= 0 else "bad")
with k3:
    top_ch = gop_ch.iloc[0] if len(gop_ch) else None
    kpi("Their top platform", top_ch["channel"] if top_ch is not None else "—",
        f"{top_ch['share']:.0%} of Republican spend" if top_ch is not None else "")
with k4:
    new7 = cre[cre["start"] >= snap - pd.Timedelta(days=7)]
    kpi("New Republican ads, last 7 days", f"{new7['ad_id'].nunique():,}",
        f"from {new7['advertiser'].nunique()} advertisers" if len(new7) else "No new flights",
        tone="bad" if len(new7) else "neutral")

# ----------------------------------------------------------------------------- where the money goes
st.markdown("<div class='group-title'>Where their money goes</div>", unsafe_allow_html=True)
c1, c2 = st.columns([7, 5], gap="medium")
with c1, st.container(border=True):
    section("Republican spend per week, by platform")
    wk = weekly_by_channel(R, "GOP side")
    if len(wk):
        chart(channel_weeks(wk, T))
    else:
        st.caption("No Republican spend attributed to this race.")
with c2, st.container(border=True):
    section("Platform mix: them vs us", "Share of each side's spend by platform.")
    order = ch.groupby("channel")["spend"].sum().sort_values(ascending=False).index.tolist()
    chart(side_pair_bars(ch, "channel", "share", T, order=order))

c3, c4 = st.columns([6, 6], gap="medium")
with c3, st.container(border=True):
    section("Who is paying for it", "Top Republican committees and PACs in this race.")
    if len(gop_adv):
        chart(ranked_bars(gop_adv, "advertiser", "spend", T, height=max(160, 30 * len(gop_adv))))
with c4, st.container(border=True):
    section("New activity, last 7 days", "Republican advertisers that launched ads in the past week.")
    na = new_activity(R)
    if na.empty:
        st.caption("No new Republican ads in the last 7 days of the snapshot.")
    else:
        st.dataframe(na.head(10), hide_index=True, width="stretch",
                     column_config={"advertiser": "Advertiser", "new_ads": "New ads",
                                    "spend": st.column_config.NumberColumn("Est. NC spend", format="dollar"),
                                    "platforms": "Platform"})
    source(f"Snapshot through {snap:%b %d, %Y}. Spend for new ads is what the platforms have reported so far.")

# ----------------------------------------------------------------------------- message & audience
st.markdown("<div class='group-title'>Their message and audience</div>", unsafe_allow_html=True)
m1, m2 = st.columns([6, 6], gap="medium")
th = themes_by_side(R)
with m1, st.container(border=True):
    section("What they talk about", "Share of each side's Facebook / Instagram spend whose ad text mentions each topic.")
    if len(th):
        chart(theme_compare(th, T))
        p = th.pivot_table(index="theme", columns="side_group", values="share", fill_value=0)
        if {"GOP side", "Dem side"} <= set(p.columns):
            gap = (p["GOP side"] - p["Dem side"]).sort_values(ascending=False)
            items = [f"Their top topic: {p['GOP side'].idxmax()} ({p['GOP side'].max():.0%} of their spend)."]
            if gap.iloc[0] > 0.02:
                items.append(f"Biggest message gap: they push {gap.index[0]} {gap.iloc[0] * 100:.0f} pts more than we do.")
            if gap.iloc[-1] < -0.02:
                items.append(f"We own {gap.index[-1]} ({p.loc[gap.index[-1], 'Dem side']:.0%} of our spend vs "
                             f"{p.loc[gap.index[-1], 'GOP side']:.0%} of theirs).")
            bullets(items)
    else:
        st.caption("No ad text available for this race.")
    source("Keyword topic classifier on ad text. Google ads carry no text, so this covers Meta only.")
with m2, st.container(border=True):
    section("Who their ads reach", "Share of each side's Facebook / Instagram impressions in NC by age.")
    au = audience_by_side(R)
    if len(au):
        chart(age_reach(au, T))
        g = au[au["side_group"] == "GOP side"]
        if len(g):
            older = g[g["age"].isin(["55-64", "65+"])]["share"].sum()
            women = g[g["gender"] == "Women"]["share"].sum()
            d = au[au["side_group"] == "Dem side"]
            d_older = d[d["age"].isin(["55-64", "65+"])]["share"].sum()
            bullets([f"{older:.0%} of their impressions reach people 55+ (ours: {d_older:.0%}).",
                     f"{women:.0%} of their impressions reach women."])
    source("Meta Ad Library delivery breakdowns (who actually saw the ads), weighted by impressions.")

# ----------------------------------------------------------------------------- ad library
st.markdown("<div class='group-title'>Their latest ads</div>", unsafe_allow_html=True)
with st.container(border=True):
    f1, f2, f3 = st.columns([2, 2, 2], vertical_alignment="bottom")
    themes_avail = sorted({t for ts in cre["message_themes"] for t in ts})
    tf = f1.selectbox("Topic", ["All"] + themes_avail, format_func=lambda x: labels.get(x, x), key="opp_theme")
    af = f2.selectbox("Advertiser", ["All"] + gop_adv["advertiser"].tolist(), key="opp_adv")
    pf = f3.selectbox("Platform", ["All", "Meta", "Google"], key="opp_plat")
    small = st.toggle("Include small ads (under $1K)", value=False, key="opp_small")
    view = cre if small else cre[cre["spend_high"] >= 1000]
    if tf != "All":
        view = view[view["message_themes"].map(lambda ts: tf in ts)]
    if af != "All":
        view = view[view["advertiser"] == af]
    if pf != "All":
        view = view[view["platform"] == pf]
    view = view.drop_duplicates(subset=["advertiser", "body"]) if len(view) else view
    st.caption(f"{len(view):,} ads · newest first · showing up to 12")
    cols = st.columns(2, gap="medium")
    for i, r in enumerate(view.head(12).itertuples()):
        band = f"≥ ${r.spend_low:,.0f}" if r.open_ended else f"${r.spend_low:,.0f}–${r.spend_high:,.0f}"
        with cols[i % 2]:
            ad_card(r.advertiser, f"{r.start:%b %d}", r.body, band, r.platform, r.url,
                    audience=r.top_audience if isinstance(r.top_audience, str) else None,
                    themes=[labels.get(t, t) for t in r.message_themes])
