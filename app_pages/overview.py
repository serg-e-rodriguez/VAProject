"""
Overview Page Layout per UI_Design.md §6.1.
Answers: Where is the money going, and where are we out-spent relative to how close the race is?
"""

import streamlit as st

from campaign_intel.data.loaders import (
    load_geo_baselines,
    load_overview_kpis,
    load_platform_mix,
    load_weekly_spend_pacing,
)
from campaign_intel.ui.components import chart_card_header, kpi_card
from campaign_intel.ui.topbar import render_topbar
from campaign_intel.viz.charts import area_with_band, donut
from campaign_intel.viz.maps import choropleth

# 1. Top Bar
render_topbar("Campaign Overview & Ad Landscape")

theme = st.session_state.get("theme", "dark")
unit_type = st.session_state.get("unit_type", "cd")
geo_mode = st.session_state.get("geo_mode", "district")

# 2. KPI Row
kpis = load_overview_kpis()
c1, c2, c3, c4 = st.columns(4, gap="medium")

with c1:
    kpi_card(
        label="Total NC Ad Spend",
        value=kpis["total_spend_mid"],
        delta=kpis["total_spend_delta"],
        good_direction="neutral",
        fidelity="aggregated",
        band=kpis["total_spend_band"],
        spark_data=[12, 14, 15, 17, 18.4]
    )

with c2:
    kpi_card(
        label="Our Share of Voice",
        value=kpis["our_sov"],
        delta=kpis["our_sov_delta"],
        good_direction="up",
        fidelity="aggregated",
        band="Dem vs Rep + Allies",
        spark_data=[39, 41, 42, 43, 44.2]
    )

with c3:
    kpi_card(
        label="Opponent Spend (7d)",
        value=kpis["opp_spend_7d"],
        delta=kpis["opp_spend_7d_delta"],
        good_direction="down",  # Opponent spend up is bad for us
        fidelity="modeled",
        band="Meta + Google Est.",
        spark_data=[520, 540, 590, 610, 620]
    )

with c4:
    kpi_card(
        label="Active Ads (Us vs Them)",
        value=kpis["active_ads_count"],
        delta=kpis["active_ads_delta"],
        good_direction="up",
        fidelity="observed",
        band="Live Snapshot Archives",
        spark_data=[1250, 1310, 1380, 1420]
    )

st.write("")

# 3. Hero Card: Map & Battleground Focus
with st.container(border=True):
    col_head, col_ctrl = st.columns([8, 4])
    with col_head:
        chart_card_header(
            title="Electoral Landscape & Ad Pressure",
            subtitle=f"Showing {'100 NC Counties' if geo_mode == 'county' else f'NC {unit_type.upper()} Districts'} · MEDSL Baseline & Platform Delivery",
            fidelity="modeled"
        )
    with col_ctrl:
        map_metric = st.segmented_control(
            "Map Metric",
            options=["Baseline Margin", "Ad Pressure"],
            default="Baseline Margin",
            key="overview_map_metric"
        )

    df_geo = load_geo_baselines(unit_type=unit_type, geo_mode=geo_mode)

    map_col, list_col = st.columns([8, 4], gap="medium")
    with map_col:
        is_diverging = (map_metric == "Baseline Margin")
        metric_col = "dem_margin_pct" if is_diverging else "total_votes"
        metric_label = "Dem Margin (%)" if is_diverging else "Ad Reach Units"

        map_chart = choropleth(
            unit_type=unit_type if geo_mode == "district" else "county",
            df_metrics=df_geo,
            metric_col=metric_col,
            metric_label=metric_label,
            is_diverging=is_diverging,
            theme=theme
        )
        st.altair_chart(map_chart, use_container_width=True)

    with list_col:
        st.markdown("##### 🎯 Top Battleground Units")
        st.caption("Units within ±5% margin — highest strategic leverage")
        if not df_geo.empty and "dem_margin_pct" in df_geo.columns:
            swing_df = df_geo.copy()
            swing_df["abs_margin"] = swing_df["dem_margin_pct"].abs()
            top_battlegrounds = swing_df.sort_values("abs_margin").head(5)
            disp_table = top_battlegrounds[["unit_id", "name", "dem_margin_pct", "total_votes"]].rename(columns={
                "unit_id": "Unit",
                "name": "Name",
                "dem_margin_pct": "Margin %",
                "total_votes": "Turnout"
            })
            st.dataframe(
                disp_table,
                column_config={
                    "Margin %": st.column_config.NumberColumn(format="%+.1f%%"),
                    "Turnout": st.column_config.NumberColumn(format="%,d"),
                },
                use_container_width=True,
                hide_index=True
            )

# 4. Supporting Cards Row (Spend Pacing & Platform Mix)
col_spend, col_mix = st.columns([7, 5], gap="medium")

with col_spend:
    with st.container(border=True):
        chart_card_header(
            title="Weekly Spend Pacing (Us vs. Opponent)",
            subtitle="Google Political Ads + Meta Ad Library · Monotone curve with low/high uncertainty band",
            fidelity="modeled"
        )
        df_pacing = load_weekly_spend_pacing()
        pacing_chart = area_with_band(
            df=df_pacing,
            x_col="week_start",
            mid_col="spend_mid",
            low_col="spend_low",
            high_col="spend_high",
            series_col="side",
            theme=theme
        )
        st.altair_chart(pacing_chart, use_container_width=True)

with col_mix, st.container(border=True):
    chart_card_header(
        title="Total Market Platform Mix",
        subtitle="Ad spend share across primary channels",
        fidelity="aggregated"
    )
    df_mix = load_platform_mix()
    donut_chart = donut(
        df=df_mix,
        category_col="platform",
        value_col="spend",
        theme=theme
    )
    st.altair_chart(donut_chart, use_container_width=True)
