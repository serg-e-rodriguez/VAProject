"""
Opponent Tracker (UI_Design.md §6.3): what is the other side spending, where, on what message,
and what changed recently?
"""

import pandas as pd
import streamlit as st

from campaign_intel.data.loaders import (
    fmt_money,
    load_advertisers,
    load_alerts,
    load_creatives,
    load_manifest,
    load_sov_weekly,
    load_weekly_by_side,
)
from campaign_intel.processing.themes import theme_labels
from campaign_intel.ui.components import chart_card_header, creative_card, kpi_card
from campaign_intel.ui.topbar import render_topbar
from campaign_intel.viz.charts import area_with_band, ranked_bar, share_of_voice_line, side_scale

render_topbar("Opponent Tracker & Creative Ledger")
theme = st.session_state.get("theme", "dark")
labels = theme_labels()
snap = pd.Timestamp(load_manifest().get("built_at", pd.Timestamp.today().isoformat())[:10])

w = load_weekly_by_side()
gop_w = w[w["side_group"] == "GOP side"].sort_values("week_start")
cre = load_creatives("GOP side", limit=5000)
adv = load_advertisers()
gop_adv = adv[adv["side_group"] == "GOP side"]

c1, c2, c3, c4 = st.columns(4, gap="medium")
with c1:
    last4 = gop_w.tail(4)["nc_spend_mid"].sum()
    prev4 = gop_w.iloc[-8:-4]["nc_spend_mid"].sum()
    kpi_card("GOP-side NC spend, last 4 weeks", fmt_money(last4),
             delta=f"{(last4 / prev4 - 1) * 100:+.0f}% vs prior 4" if prev4 else None, good_direction="down",
             fidelity="modeled", band="Google + Meta, NC-apportioned", spark_data=gop_w["nc_spend_mid"].tail(8).tolist())
with c2:
    new48 = cre[cre["start"] >= snap - pd.Timedelta(days=2)]
    new7 = cre[cre["start"] >= snap - pd.Timedelta(days=7)]
    kpi_card("New GOP-side ads", f"{len(new7):,} in 7 days", delta=f"{len(new48):,} in last 48h", good_direction="down",
             fidelity="observed", band="Ads whose delivery started in the window")
with c3:
    flat = cre[cre["start"] >= snap - pd.Timedelta(days=28)].explode("message_themes").dropna(subset=["message_themes"])
    ts = flat.groupby("message_themes")["nc_spend_mid"].sum().sort_values(ascending=False)
    top_t = labels.get(ts.index[0], ts.index[0]) if len(ts) else "—"
    kpi_card("Dominant GOP message (28 days)", top_t, delta=f"{ts.iloc[0] / ts.sum():.0%} of themed spend" if len(ts) else None,
             good_direction="neutral", fidelity="modeled", band="Keyword theme classifier on Meta ad text")
with c4:
    top_a = gop_adv.iloc[0] if len(gop_adv) else None
    kpi_card("Biggest GOP-side spender", top_a["advertiser"] if top_a is not None else "—",
             delta=fmt_money(top_a["nc_spend_mid"]) if top_a is not None else None, good_direction="neutral",
             fidelity="modeled", band="NC-apportioned, this cycle")

st.write("")
h1, h2 = st.columns([7, 5], gap="medium")
with h1, st.container(border=True):
    chart_card_header("GOP-side vs Dem-side weekly spend", "Modeled NC spend, low–high band", fidelity="modeled")
    st.altair_chart(area_with_band(w[w["side_group"].isin(["Dem side", "GOP side"])], "week_start", "nc_spend_mid",
                                   "nc_spend_low", "nc_spend_high", "side_group", theme=theme), width="stretch")
with h2, st.container(border=True):
    chart_card_header("Dem share of voice", "Dem-side share of partisan NC spend per week (50% = parity)", fidelity="modeled")
    st.altair_chart(share_of_voice_line(load_sov_weekly(), theme), width="stretch")

g1, g2 = st.columns([7, 5], gap="medium")
with g1, st.container(border=True):
    chart_card_header("GOP-side creative library", "Real ads from the Meta Ad Library and Google Transparency Report · "
                      "newest first", fidelity="observed")
    f1, f2, f3, f4 = st.columns([1.2, 1.4, 1, 1], vertical_alignment="bottom")
    themes_avail = sorted({t for th in cre["message_themes"] for t in th})
    tf = f1.selectbox("Theme", ["All"] + themes_avail, format_func=lambda x: labels.get(x, x), key="opp_theme")
    af = f2.selectbox("Advertiser", ["All"] + gop_adv["advertiser"].head(30).tolist(), key="opp_adv")
    pf = f3.selectbox("Platform", ["All", "Meta", "Google"], key="opp_plat")
    big = f4.toggle("Hide ads < $1k", value=True, key="opp_big")
    view = cre[cre["spend_high"] >= 1000] if big else cre
    if tf != "All":
        view = view[view["message_themes"].map(lambda th: tf in th)]
    if af != "All":
        view = view[view["advertiser"] == af]
    if pf != "All":
        view = view[view["platform"] == pf]
    st.caption(f"{len(view):,} ads match · showing 12")
    for r in view.head(12).itertuples():
        band = (f"≥ ${r.spend_low:,.0f}" if r.open_ended else f"${r.spend_low:,.0f} – ${r.spend_high:,.0f}")
        nc = f" · NC ≈ {r.nc_share:.0%}" if pd.notna(r.nc_share) and r.nc_share < 0.99 else ""
        body = r.body or f"[{r.format.title()} ad — open in the Google Ads Transparency Report to view the creative]"
        creative_card(advertiser=r.advertiser, date_str=f"{r.start:%b %d, %Y}", body=body, spend_band=band + nc,
                      top_demo=r.top_demo, themes=[labels.get(t, t) for t in r.message_themes],
                      url=r.url or "https://www.facebook.com/ads/library/", platform=r.platform)
with g2, st.container(border=True):
    chart_card_header("GOP-side committees & PACs", "Modeled NC spend this cycle", fidelity="modeled")
    st.altair_chart(ranked_bar(gop_adv.head(12), "advertiser", "nc_spend_mid", theme, title="NC spend",
                               low_col="nc_spend_low", high_col="nc_spend_high", color_col="side_group",
                               color_scale=side_scale(theme)), width="stretch")
    st.dataframe(gop_adv.head(25)[["advertiser", "platforms", "n_ads", "active_7d", "nc_spend_mid", "top_theme"]]
                 .assign(top_theme=lambda d: d["top_theme"].map(lambda x: labels.get(x, x))),
                 hide_index=True, width="stretch",
                 column_config={"advertiser": "Advertiser", "n_ads": "Ads", "active_7d": "Active 7d",
                                "nc_spend_mid": st.column_config.NumberColumn("NC spend", format="dollar"),
                                "top_theme": "Top theme"})
    st.markdown("##### 🚨 Recent activity alerts")
    al = load_alerts()
    if al.empty:
        st.caption("No GOP-side alerts in the last 7 days of the snapshot.")
    for r in al.head(6).itertuples():
        st.markdown(f"{'🔴' if r.severity == 'high' else '🟠'} {r.text}")
