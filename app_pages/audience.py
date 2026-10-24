"""
Audience Intelligence Page Layout per UI_Design.md §6.2.
Answers: Which demographics see which messages, and where are the gaps between what they see and what they care about?
"""

import streamlit as st

from campaign_intel.data.loaders import (
    load_survey_platform_benchmarks,
    load_theme_demographic_heatmap,
)
from campaign_intel.ui.components import chart_card_header, kpi_card
from campaign_intel.ui.topbar import render_topbar
from campaign_intel.viz.charts import grouped_bar, heatmap

# 1. Top Bar
render_topbar("Audience Intelligence & Message Delivery")

theme = st.session_state.get("theme", "dark")

# 2. KPI Row
c1, c2, c3, c4 = st.columns(4, gap="medium")

with c1:
    kpi_card(
        label="Top-Reached Age Group",
        value="35–44 Cohort",
        delta="31.4% share",
        good_direction="neutral",
        fidelity="observed",
        band="Meta Delivery Archive",
        spark_data=[22, 26, 29, 31.4]
    )

with c2:
    kpi_card(
        label="Gender Delivery Split",
        value="54% F / 46% M",
        delta="+4.1% F tilt",
        good_direction="neutral",
        fidelity="observed",
        band="Meta Graph API Verified",
        spark_data=[50, 51, 52, 54]
    )

with c3:
    kpi_card(
        label="Fundraising Ads Filtered",
        value="320 Ads",
        delta="ActBlue/WinRed",
        good_direction="neutral",
        fidelity="aggregated",
        band="Excluded from persuasion",
        spark_data=[180, 220, 280, 320]
    )

with c4:
    kpi_card(
        label="Active Themes Detected",
        value="11 Themes",
        delta="+2 emerging",
        good_direction="up",
        fidelity="modeled",
        band="Keyword + NLP Classifier",
        spark_data=[7, 8, 9, 11]
    )

st.write("")

# 3. Hero Card: Theme x Demographic Heatmap
with st.container(border=True):
    head_col, view_col = st.columns([8, 4])
    with head_col:
        chart_card_header(
            title="Theme Delivery Matrix by Demographic Cohort",
            subtitle="Cross-tabulation of empirical creative message exposure across age segments",
            fidelity="modeled"
        )
    with view_col:
        view_type = st.segmented_control(
            "Matrix Perspective",
            options=["Us", "Opponent", "Gap"],
            default="Us",
            key="audience_heatmap_view"
        )

    is_gap = (view_type == "Gap")
    df_heat = load_theme_demographic_heatmap(view_type=view_type or "Us")

    heat_chart = heatmap(
        df=df_heat,
        x_col="age_cohort",
        y_col="theme",
        val_col="pct",
        is_gap=is_gap,
        theme=theme
    )
    st.altair_chart(heat_chart, use_container_width=True)

# 4. Supporting Cards Row (CCES Benchmarks & Message Gap Callouts)
col_survey, col_gaps = st.columns([7, 5], gap="medium")

with col_survey:
    with st.container(border=True):
        chart_card_header(
            title="Social Media Platform Adoption by Age",
            subtitle="CCES 2024 (UNC Module) · Survey-weighted (teamweight) with 95% Confidence Intervals",
            fidelity="aggregated"
        )
        df_platforms = load_survey_platform_benchmarks()
        if not df_platforms.empty:
            chart_plat = grouped_bar(
                df=df_platforms,
                x_col="age_cohort",
                y_col="pct",
                series_col="platform",
                err_low="ci_low",
                err_high="ci_high",
                y_title="Adoption (%)",
                theme=theme
            )
            st.altair_chart(chart_plat, use_container_width=True)
        else:
            st.info("Loading CCES platform benchmarks...")

with col_gaps:
    with st.container(border=True):
        chart_card_header(
            title="Strategic Message Gap Callouts",
            subtitle="Discrepancies between voter issue concern and digital message flights",
            fidelity="modeled"
        )
        st.markdown("""
        <div style="background-color: var(--accent-soft); border-left: 4px solid var(--accent); padding: 12px 14px; border-radius: 8px; margin-bottom: 12px;">
            <strong style="color: var(--accent);">⚠️ 18–34 Women: High Cost-of-Living Concern, Low Economic Delivery</strong>
            <p style="font-size: 12px; margin: 4px 0 0 0; color: var(--text-secondary);">
                CCES survey data indicates 74% high inflation concern, yet 62% of our delivery to this cohort is concentrated in Reproductive Rights.
            </p>
        </div>

        <div style="background-color: rgba(224, 72, 72, 0.08); border-left: 4px solid var(--rep); padding: 12px 14px; border-radius: 8px; margin-bottom: 12px;">
            <strong style="color: var(--rep);">🚨 45–64 Suburban Voters: Opponent Public Safety Saturation</strong>
            <p style="font-size: 12px; margin: 4px 0 0 0; color: var(--text-secondary);">
                Opponents outspend our campaign 3.8:1 on Crime & Law Enforcement messaging in Charlotte and Piedmont media markets.
            </p>
        </div>

        <div style="background-color: rgba(47, 111, 237, 0.08); border-left: 4px solid var(--dem); padding: 12px 14px; border-radius: 8px;">
            <strong style="color: var(--dem);">💡 Seniors (65+): High Prescription Drug Receptivity</strong>
            <p style="font-size: 12px; margin: 4px 0 0 0; color: var(--text-secondary);">
                Healthcare and Medicare price-cap ads demonstrate the highest positive conversion efficiency among persuadable retirees.
            </p>
        </div>
        """, unsafe_allow_html=True)
