"""
Electorate & Turnout Intelligence Page Layout per UI_Design.md §6.4.
Answers: How many persuadable and mobilizable voters are in each place, and how many have already voted?
"""

import streamlit as st

from campaign_intel.data.loaders import (
    load_geo_baselines,
    load_vote_methods,
)
from campaign_intel.ui.components import chart_card_header, kpi_card
from campaign_intel.ui.topbar import render_topbar
from campaign_intel.viz.charts import grouped_bar
from campaign_intel.viz.maps import choropleth

# 1. Top Bar
render_topbar("NC Electorate & Voter Turnout Intelligence")

theme = st.session_state.get("theme", "dark")
unit_type = st.session_state.get("unit_type", "cd")
geo_mode = st.session_state.get("geo_mode", "district")

# 2. KPI Row
c1, c2, c3, c4 = st.columns(4, gap="medium")

with c1:
    kpi_card(
        label="Registered Voters in Scope",
        value="7,420,000",
        delta="+1.8% vs 2022",
        good_direction="neutral",
        fidelity="aggregated",
        band="NCSBE Statewide Voter File",
        spark_data=[7100, 7200, 7350, 7420]
    )

with c2:
    kpi_card(
        label="Unaffiliated Share (Persuasion)",
        value="37.8% Bloc",
        delta="Largest in NC",
        good_direction="neutral",
        fidelity="aggregated",
        band="2.80M Registered Voters",
        spark_data=[34, 35.5, 36.8, 37.8]
    )

with c3:
    kpi_card(
        label="Low-Propensity Dems (Mobilization)",
        value="542,000 Voters",
        delta="0-of-2 midterms",
        good_direction="neutral",
        fidelity="aggregated",
        band="NCSBE Voter History Filtered",
        spark_data=[480, 510, 530, 542]
    )

with c4:
    kpi_card(
        label="Early Votes Cast (One-Stop)",
        value="1,840,000",
        delta="48.5% of total",
        good_direction="neutral",
        fidelity="aggregated",
        band="MEDSL 2022 Certified Baseline",
        spark_data=[1500, 1650, 1780, 1840]
    )

st.write("")

# 3. Hero Card: Map of Selected Target Universe
with st.container(border=True):
    col_head, col_ctrl = st.columns([7, 5])
    with col_head:
        chart_card_header(
            title="Electorate Geographic Target Density",
            subtitle=f"Showing {'Counties' if geo_mode == 'county' else f'NC {unit_type.upper()} Districts'} · Aggregated voter registration and turnout universes",
            fidelity="aggregated"
        )
    with col_ctrl:
        universe_choice = st.segmented_control(
            "Select Universe",
            options=["Persuasion Universe", "Mobilization Universe", "Already Voted"],
            default="Persuasion Universe",
            key="electorate_universe_choice"
        )

    col_metric_map = {
        "Persuasion Universe": "persuasion_universe",
        "Mobilization Universe": "mobilization_universe",
        "Already Voted": "already_voted",
    }
    metric_key = col_metric_map.get(universe_choice or "Persuasion Universe", "persuasion_universe")

    df_geo = load_geo_baselines(unit_type=unit_type, geo_mode=geo_mode)

    map_chart = choropleth(
        unit_type=unit_type if geo_mode == "district" else "county",
        df_metrics=df_geo,
        metric_col=metric_key,
        metric_label=universe_choice or "Persuasion Universe",
        is_diverging=False,
        theme=theme
    )
    st.altair_chart(map_chart, use_container_width=True)

# 4. Supporting Section: Vote-Method Split & Electorate Universe Table
col_split, col_table = st.columns([6, 6], gap="medium")

with col_split, st.container(border=True):
    chart_card_header(
        title="Historical Vote Method Distribution",
        subtitle="MEDSL 2022 North Carolina U.S. Senate election by mode",
        fidelity="aggregated"
    )
    df_modes = load_vote_methods()
    if not df_modes.empty:
        chart_modes = grouped_bar(
            df=df_modes,
            x_col="vote_method",
            y_col="votes",
            series_col="party_clean",
            y_title="Total Ballots Cast",
            theme=theme
        )
        st.altair_chart(chart_modes, use_container_width=True)
    else:
        st.info("Loading 2022 Senate baseline modes...")

with col_table:
    with st.container(border=True):
        chart_card_header(
            title="District Target Universe Table",
            subtitle="Registration, turnout, and strategic pools by geographic unit",
            fidelity="aggregated"
        )
        if not df_geo.empty:
            disp_cols = ["unit_id", "name", "registered_voters", "persuasion_universe", "mobilization_universe"]
            df_table = df_geo[disp_cols].rename(columns={
                "unit_id": "Unit",
                "name": "Name",
                "registered_voters": "Registered",
                "persuasion_universe": "Persuasion (P_u)",
                "mobilization_universe": "Mobilization (M_u)",
            })
            st.dataframe(
                df_table,
                column_config={
                    "Registered": st.column_config.NumberColumn(format="%,d"),
                    "Persuasion (P_u)": st.column_config.NumberColumn(format="%,d"),
                    "Mobilization (M_u)": st.column_config.NumberColumn(format="%,d"),
                },
                use_container_width=True,
                hide_index=True
            )
