"""
Opponent Tracker Page Layout per UI_Design.md §6.3.
Answers: What is the other side spending, where, on what message, and what changed recently?
"""

import streamlit as st

from campaign_intel.data.loaders import (
    load_opponent_advertiser_table,
    load_opponent_creatives,
    load_weekly_spend_pacing,
)
from campaign_intel.ui.components import chart_card_header, creative_card, kpi_card
from campaign_intel.ui.topbar import render_topbar
from campaign_intel.viz.charts import area_with_band

# 1. Top Bar
render_topbar("Opponent Tracker & Creative Ledger")

theme = st.session_state.get("theme", "dark")

# 2. KPI Row
c1, c2, c3, c4 = st.columns(4, gap="medium")

with c1:
    kpi_card(
        label="Opponent Spend (7d / 30d)",
        value="$620k / $2.4M",
        delta="+9.4% pacing",
        good_direction="down",  # Opponent spend up is bad for us
        fidelity="modeled",
        band="Meta + Google Estimates",
        spark_data=[510, 550, 580, 620]
    )

with c2:
    kpi_card(
        label="New Creatives (48h)",
        value="28 New Flights",
        delta="18 Video, 10 Image",
        good_direction="down",
        fidelity="observed",
        band="Meta API Live Feed",
        spark_data=[12, 19, 24, 28]
    )

with c3:
    kpi_card(
        label="Dominant Opponent Theme",
        value="Economy & Inflation",
        delta="44% of impressions",
        good_direction="neutral",
        fidelity="modeled",
        band="NLP Classification",
        spark_data=[32, 38, 41, 44]
    )

with c4:
    kpi_card(
        label="Top District Target",
        value="CD 13 Toss-Up",
        delta="$142k spend",
        good_direction="neutral",
        fidelity="modeled",
        band="Voter-weight allocation",
        spark_data=[95, 110, 130, 142]
    )

st.write("")

# 3. Hero Card: Share of Voice Over Time
with st.container(border=True):
    chart_card_header(
        title="Share of Voice Over Time (Us vs. Opponent)",
        subtitle="Tracking relative weekly media pressure across North Carolina",
        fidelity="modeled"
    )
    df_pacing = load_weekly_spend_pacing()
    chart_sov = area_with_band(
        df=df_pacing,
        x_col="week_start",
        mid_col="spend_mid",
        low_col="spend_low",
        high_col="spend_high",
        series_col="side",
        theme=theme
    )
    st.altair_chart(chart_sov, use_container_width=True)

# 4. Supporting Section: Creative Library Grid & Advertiser Committees Table
col_creatives, col_table = st.columns([7, 5], gap="medium")

with col_creatives:
    with st.container(border=True):
        chart_card_header(
            title="Inspectable Opponent Creative Gallery",
            subtitle="Live ad copy, spend bands, targeting, and direct Ad Library preview links",
            fidelity="observed"
        )
        # Filters
        f1, f2 = st.columns(2)
        with f1:
            theme_filter = st.selectbox(
                "Filter by Theme",
                options=["All Themes", "Economy", "Crime", "Immigration", "Education"],
                key="opp_theme_filter"
            )
        with f2:
            spend_filter = st.selectbox(
                "Filter by Spend Tier",
                options=["All Tiers", "High (> $20k)", "Medium ($5k – $20k)"],
                key="opp_spend_filter"
            )

        creatives = load_opponent_creatives()
        for cr in creatives:
            if theme_filter != "All Themes" and theme_filter.lower() not in [t.lower() for t in cr["themes"]]:
                continue
            creative_card(
                advertiser=cr["advertiser"],
                date_str=cr["date"],
                body=cr["body"],
                spend_band=cr["spend_band"],
                top_demo=cr["top_demo"],
                themes=cr["themes"],
                url=cr["url"],
                platform=cr["platform"]
            )

with col_table, st.container(border=True):
    chart_card_header(
        title="Opponent Committee & PAC Ledger",
        subtitle="Identified committees, allied PACs, and estimated flight totals",
        fidelity="aggregated"
    )
    df_adv = load_opponent_advertiser_table()
    st.dataframe(
        df_adv,
        column_config={
            "Active Ads": st.column_config.NumberColumn(format="%,d"),
        },
        use_container_width=True,
        hide_index=True
    )

    st.markdown("##### 🚨 Recent Activity Alerts")
    st.markdown("""
        - ⚠️ **NCGOP**: Launched $45k digital blitz on tax policy targeting suburban women.
        - ⚠️ **Carolina Future PAC**: Added 8 new CTV video units targeting Raleigh DMA.
        - ⚠️ **Liberty NC Alliance**: Started Hispanic border security ad targeting.
        """)
