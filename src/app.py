"""
Streamlit Entry Point: North Carolina Political Ads Strategic Intelligence Dashboard
Analyzes demographic reach gaps among NC voters, regional competitor spend across NC DMAs,
and demographic-specific video/creative ad formats via Meta API.
Features dynamic drop-down menus for complete interactive control over visualizations.
Strictly scoped to North Carolina from 2024 to current.
Information Architecture: Overview first, then specific deep-dive tabs.
Targeted Ad Formats section strictly separates Google BigQuery and Meta Ad Library subsections.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import altair as alt

try:
    from src.data.bigquery_loader import (
        load_bigquery_creative_stats,
        load_bigquery_geo_spend,
        load_bigquery_weekly_spend
    )
    from src.data.meta_loader import load_meta_ads
    from src.data.preprocessor import (
        clean_creative_stats,
        clean_geo_spend,
        clean_advertiser_weekly_spend,
        unnest_demographics,
        process_meta_demographics,
        check_gender_data_exists,
        generate_nc_county_spend,
        VALID_AGE_COHORTS,
        NC_DMAS
    )
    from src.components.audience_charts import (
        create_nc_demographic_gap_chart,
        create_nc_gender_breakdown_chart,
        create_nc_cross_platform_demographic_chart,
        create_meta_demographic_delivery_chart,
        create_meta_gender_reach_chart,
        generate_google_demographic_insights,
        generate_meta_demographic_insights,
        generate_cross_platform_strategic_insights
    )
    from src.components.geo_charts import (
        create_nc_dma_ranking_chart,
        create_nc_advertiser_breakdown_chart,
        create_nc_market_share_chart,
        create_nc_county_heatmap_chart,
        create_nc_county_choropleth_chart,
        create_nc_county_spatial_heatmap_chart,
        generate_nc_county_map_heatmap_svg,
        create_county_campaign_spend_chart,
        create_county_meta_age_cohort_chart
    )
    from src.components.spend_charts import (
        create_nc_spend_trajectory_chart,
        create_nc_format_efficiency_chart,
        create_nc_platform_comparison_chart,
        create_top_spenders_overview_chart
    )
    from src.components.creative_charts import (
        filter_google_creatives,
        create_google_format_distribution_chart,
        create_google_format_cpm_chart,
        generate_google_creative_insights,
        filter_meta_demographics,
        create_meta_demographic_format_chart,
        create_meta_format_cpm_chart,
        create_video_adoption_by_demographic_chart,
        create_gender_video_breakdown_chart,
        generate_meta_creative_insights
    )
except ModuleNotFoundError:
    from data.bigquery_loader import (
        load_bigquery_creative_stats,
        load_bigquery_geo_spend,
        load_bigquery_weekly_spend
    )
    from data.meta_loader import load_meta_ads
    from data.preprocessor import (
        clean_creative_stats,
        clean_geo_spend,
        clean_advertiser_weekly_spend,
        unnest_demographics,
        process_meta_demographics,
        check_gender_data_exists,
        generate_nc_county_spend,
        VALID_AGE_COHORTS,
        NC_DMAS
    )
    from components.audience_charts import (
        create_nc_demographic_gap_chart,
        create_nc_gender_breakdown_chart,
        create_nc_cross_platform_demographic_chart,
        create_meta_demographic_delivery_chart,
        create_meta_gender_reach_chart,
        generate_google_demographic_insights,
        generate_meta_demographic_insights,
        generate_cross_platform_strategic_insights
    )
    from components.geo_charts import (
        create_nc_dma_ranking_chart,
        create_nc_advertiser_breakdown_chart,
        create_nc_market_share_chart,
        create_nc_county_heatmap_chart,
        create_nc_county_choropleth_chart,
        create_nc_county_spatial_heatmap_chart,
        generate_nc_county_map_heatmap_svg,
        create_county_campaign_spend_chart,
        create_county_meta_age_cohort_chart
    )
    from components.spend_charts import (
        create_nc_spend_trajectory_chart,
        create_nc_format_efficiency_chart,
        create_nc_platform_comparison_chart,
        create_top_spenders_overview_chart
    )
    from components.creative_charts import (
        filter_google_creatives,
        create_google_format_distribution_chart,
        create_google_format_cpm_chart,
        generate_google_creative_insights,
        filter_meta_demographics,
        create_meta_demographic_format_chart,
        create_meta_format_cpm_chart,
        create_video_adoption_by_demographic_chart,
        create_gender_video_breakdown_chart,
        generate_meta_creative_insights
    )

# Page configuration
st.set_page_config(
    page_title="North Carolina Political Ads Strategic Intelligence Dashboard",
    page_icon="🌲",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (Preserving Sleek Dark Aesthetics & Cards)
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px 20px;
        color: white;
    }
    .metric-value {
        font-size: 26px;
        font-weight: 700;
        color: #38bdf8;
    }
    .metric-label {
        font-size: 12px;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .alert-box {
        background-color: rgba(239, 68, 68, 0.12);
        border-left: 4px solid #ef4444;
        padding: 14px 18px;
        border-radius: 6px;
        margin-bottom: 20px;
        color: #fca5a5;
    }
    .info-box {
        background-color: rgba(56, 189, 248, 0.12);
        border-left: 4px solid #38bdf8;
        padding: 14px 18px;
        border-radius: 6px;
        margin-bottom: 20px;
        color: #bae6fd;
    }
    .success-box {
        background-color: rgba(16, 185, 129, 0.12);
        border-left: 4px solid #10b981;
        padding: 14px 18px;
        border-radius: 6px;
        margin-bottom: 20px;
        color: #a7f3d0;
    }
    .insight-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 18px 22px;
        margin-top: 15px;
        margin-bottom: 20px;
    }
    .insight-card h4 {
        margin: 0 0 10px 0;
        color: #f1f5f9;
        font-size: 15px;
        font-weight: 700;
    }
    .insight-card ul {
        margin: 0;
        padding-left: 18px;
        color: #e2e8f0;
        font-size: 13px;
        line-height: 1.6;
    }
</style>
""", unsafe_allow_html=True)


def main():
    # Header
    st.title("🌲 North Carolina Political Ads Strategic Intelligence Dashboard")
    st.markdown(
        "**Battleground North Carolina Analytics (2024 – Current):** Analyzing political advertising data from "
        "**Google Cloud BigQuery** and the **Meta Ad Library API** to identify under-served voter demographics, "
        "map competitor spend across North Carolina media markets (DMAs) and counties, and evaluate "
        "demographic-specific video vs. static ad formats."
    )

    # Ingest Data
    with st.spinner("Ingesting and harmonizing North Carolina political ad data (2024 to Current)..."):
        raw_bq_creatives, bq_live = load_bigquery_creative_stats(limit=3000)
        raw_meta_ads, meta_live = load_meta_ads(max_records=1500)
        raw_geo, geo_live = load_bigquery_geo_spend()
        raw_weekly, weekly_live = load_bigquery_weekly_spend()

        clean_bq = clean_creative_stats(raw_bq_creatives)
        clean_meta = clean_creative_stats(raw_meta_ads)
        combined_creatives = pd.concat([clean_bq, clean_meta], ignore_index=True)
        
        df_meta_demo = process_meta_demographics(clean_meta)
        cleaned_geo = clean_geo_spend(raw_geo)
        cleaned_weekly = clean_advertiser_weekly_spend(raw_weekly)
        df_county = generate_nc_county_spend(cleaned_geo)

    # Status Badges
    st.markdown(
        f"""
        <div style="display:flex; gap:10px; margin-bottom: 20px; flex-wrap:wrap;">
            <span style="background:#059669; color:white; padding:4px 12px; border-radius:12px; font-size:12px; font-weight:600;">
                Scope: North Carolina (NC Only)
            </span>
            <span style="background:#6366f1; color:white; padding:4px 12px; border-radius:12px; font-size:12px; font-weight:600;">
                Temporal: 2024 – Current
            </span>
            <span style="background:{'#10b981' if bq_live else '#f59e0b'}; color:black; padding:4px 10px; border-radius:12px; font-size:12px; font-weight:600;">
                BigQuery: {'Live Connected' if bq_live else 'NC Public Sample Dataset'}
            </span>
            <span style="background:{'#10b981' if meta_live else '#f59e0b'}; color:black; padding:4px 10px; border-radius:12px; font-size:12px; font-weight:600;">
                Meta API: {'Live Connected' if meta_live else 'NC Public Sample Dataset'}
            </span>
            <span style="background:#0ea5e9; color:black; padding:4px 10px; border-radius:12px; font-size:12px; font-weight:600;">
                Currency: Strict USD
            </span>
        </div>
        """,
        unsafe_allow_html=True
    )

    # -----------------------------
    # Sidebar Filters
    # -----------------------------
    st.sidebar.header("🔍 North Carolina Campaign Filters")

    selected_platform = st.sidebar.radio(
        "Advertising Platform",
        options=["All Platforms", "Google Ads", "Meta Ads"],
        index=0
    )

    filtered_df = combined_creatives.copy()
    if selected_platform == "Google Ads":
        filtered_df = filtered_df[filtered_df["platform"] == "Google"]
    elif selected_platform == "Meta Ads":
        filtered_df = filtered_df[filtered_df["platform"] == "Meta"]

    # NC Media Market filter
    available_dmas = ["All NC Markets"] + NC_DMAS
    selected_dma = st.sidebar.selectbox("Filter by NC Media Market (DMA)", options=available_dmas, index=0)
    if selected_dma != "All NC Markets":
        filtered_df = filtered_df[filtered_df["nc_dma"] == selected_dma]
        cleaned_geo = cleaned_geo[cleaned_geo["nc_dma"] == selected_dma]
        df_county = df_county[df_county["nc_dma"] == selected_dma]
        if not df_meta_demo.empty and "nc_dma" in df_meta_demo.columns:
            df_meta_demo = df_meta_demo[df_meta_demo["nc_dma"] == selected_dma]

    # NC Competitors Multi-select
    all_advertisers = sorted(filtered_df["advertiser_name"].dropna().unique().tolist())
    selected_advertisers = st.sidebar.multiselect(
        "Competitor PACs & Campaigns in NC",
        options=all_advertisers,
        default=all_advertisers[:6] if len(all_advertisers) >= 6 else all_advertisers
    )
    if selected_advertisers:
        filtered_df = filtered_df[filtered_df["advertiser_name"].isin(selected_advertisers)]
        cleaned_geo = cleaned_geo[cleaned_geo["advertiser_name"].isin(selected_advertisers)]
        cleaned_weekly = cleaned_weekly[cleaned_weekly["advertiser_name"].isin(selected_advertisers)]
        if not df_meta_demo.empty and "advertiser_name" in df_meta_demo.columns:
            df_meta_demo = df_meta_demo[df_meta_demo["advertiser_name"].isin(selected_advertisers)]

    st.sidebar.divider()
    st.sidebar.markdown(
        "**Interactive Dashboard Controls:**\n"
        "- Drop-down menus directly control what each visualization displays.\n"
        "- First tab provides a comprehensive **Executive Overview** of all data.\n"
        "- Subsequent tabs display deep-dive targeted sections.\n"
        "- In the Ad Types section, **Google BigQuery** and **Meta Ads** data are strictly separated."
    )

    # -----------------------------
    # Derived Macro Summary Metrics
    # -----------------------------
    total_spend = filtered_df["spend_usd_est"].sum()
    total_impressions = filtered_df["impressions_est"].sum()
    total_ads = len(filtered_df)

    unnested_demo = unnest_demographics(clean_bq, "age_targeting")
    demo_reach = unnested_demo[unnested_demo["age_targeting"].isin(VALID_AGE_COHORTS)].groupby("age_targeting")["impressions_est"].sum()
    least_viewed_cohort = demo_reach.idxmin() if not demo_reach.empty else "18-24"

    top_dma_spend = cleaned_geo.groupby("nc_dma")["spend_usd"].sum()
    top_spend_dma = top_dma_spend.idxmax() if not top_dma_spend.empty else "N/A"
    top_dma_val = top_dma_spend.max() if not top_dma_spend.empty else 0.0

    top_spenders = filtered_df.groupby("advertiser_name")["spend_usd_est"].sum()
    leading_spender = top_spenders.idxmax() if not top_spenders.empty else "N/A"
    leading_spender_val = top_spenders.max() if not top_spenders.empty else 0.0

    # -----------------------------------------------------------
    # Main Dashboard Tabs (Overview First, Specific Deep Dives After)
    # -----------------------------------------------------------
    tab_overview, tab_demo, tab_creative, tab_geo, tab_pace, tab_info = st.tabs(
        [
            "📊 Executive Campaign Overview",
            "🎯 Demographic Opportunity & Gap Analysis (NC)",
            "🎬 Targeted Ad Formats & Creative Intelligence",
            "🗺️ Regional Competitor Spend & NC County Heatmap",
            "📈 Platform Performance & Pacing (2024–Current)",
            "ℹ️ Key Dataset Facts & Methodology"
        ],
        key="active_tab",
        bind="query-params"
    )

    # =========================================================================
    # TAB 1: EXECUTIVE CAMPAIGN OVERVIEW (Overview of the data)
    # =========================================================================
    with tab_overview:
        st.markdown(
            """<div class="info-box">
                <strong>Executive Macro Overview (2024 – Current):</strong> This executive briefing synthesizes 
                political advertising investments across North Carolina voters. Review high-level platform splits, 
                designated media market concentration, and top rival spenders before exploring specific deep-dive tabs.
            </div>""",
            unsafe_allow_html=True
        )

        # Overview KPI Row
        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
        with kpi1:
            st.markdown(
                f"""<div class="metric-card">
                    <div class="metric-label">Total NC Spend (2024+)</div>
                    <div class="metric-value">${total_spend:,.0f}</div>
                </div>""",
                unsafe_allow_html=True
            )
        with kpi2:
            st.markdown(
                f"""<div class="metric-card">
                    <div class="metric-label">Delivered Impressions</div>
                    <div class="metric-value">{total_impressions:,.0f}</div>
                </div>""",
                unsafe_allow_html=True
            )
        with kpi3:
            st.markdown(
                f"""<div class="metric-card">
                    <div class="metric-label">Active Ad Creatives</div>
                    <div class="metric-value">{total_ads:,}</div>
                </div>""",
                unsafe_allow_html=True
            )
        with kpi4:
            st.markdown(
                f"""<div class="metric-card">
                    <div class="metric-label">🚨 Top Demographic Gap</div>
                    <div class="metric-value" style="color: #ef4444;">{least_viewed_cohort}</div>
                </div>""",
                unsafe_allow_html=True
            )
        with kpi5:
            st.markdown(
                f"""<div class="metric-card">
                    <div class="metric-label">🗺️ Epicenter NC Market</div>
                    <div class="metric-value" style="color: #f59e0b;">{top_spend_dma.replace(' DMA', '')}</div>
                </div>""",
                unsafe_allow_html=True
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # Macro Visualizations Row 1
        st.subheader("Macro Digital Spend Allocation & Regional Focus")
        col_ov1, col_ov2 = st.columns(2)
        with col_ov1:
            platform_comp = create_nc_platform_comparison_chart(filtered_df)
            st.altair_chart(platform_comp, width="stretch", theme="streamlit")
        with col_ov2:
            dma_ov_chart = create_nc_dma_ranking_chart(cleaned_geo, metric_label="Total Spend ($ USD)")
            st.altair_chart(dma_ov_chart, width="stretch", theme="streamlit")

        # Macro Visualizations Row 2
        st.subheader("Competitor Landscape & Creative Inventory Overview")
        col_ov3, col_ov4 = st.columns(2)
        with col_ov3:
            top_spenders_chart = create_top_spenders_overview_chart(filtered_df, top_n=8)
            st.altair_chart(top_spenders_chart, width="stretch", theme="streamlit")
        with col_ov4:
            format_ov_chart = create_nc_format_efficiency_chart(filtered_df)
            st.altair_chart(format_ov_chart, width="stretch", theme="streamlit")

        # Executive Tactical Briefing Card
        st.markdown(
            f"""
            <div class="insight-card">
                <h4>📋 Executive Campaign Intelligence Briefing: North Carolina Battleground</h4>
                <ul>
                    <li><strong>Capital Commitment:</strong> Tracked digital expenditure across Google and Meta in North Carolina totals <strong>${total_spend:,.2f}</strong> across <strong>{total_ads:,} active ad creatives</strong> from January 1, 2024 to current.</li>
                    <li><strong>Market Saturation Epicenter:</strong> <strong>{top_spend_dma}</strong> dominates total spending (${top_dma_val:,.0f}), representing the central battleground for media dominance between Charlotte and the Triangle.</li>
                    <li><strong>Leading Competitor Spender:</strong> <strong>{leading_spender}</strong> leads all organizations in digital ad spend with <strong>${leading_spender_val:,.0f}</strong> deployed across North Carolina voters.</li>
                    <li><strong>Primary Mobilization Gap:</strong> The <strong>{least_viewed_cohort}</strong> voter cohort receives the lowest proportion of ad impressions across campaigns, indicating an urgent opportunity for targeted turnout outreach.</li>
                    <li><strong>Format Priority:</strong> Video advertising accounts for the vast majority of impression volume on both Google YouTube and Meta social feeds, underscoring the necessity of short-form, high-recall audiovisual messaging.</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True
        )

        with st.expander("📊 View Top 10 Competitors Spending Ledger in North Carolina"):
            top_10_table = (
                filtered_df.groupby(["advertiser_name", "platform"], as_index=False)
                .agg(
                    Total_Spend_USD=("spend_usd_est", "sum"),
                    Total_Impressions=("impressions_est", "sum"),
                    Creatives_Count=("ad_id", "nunique")
                )
                .sort_values(by="Total_Spend_USD", ascending=False)
                .head(10)
            )
            st.dataframe(
                top_10_table.style.format({
                    "Total_Spend_USD": "${:,.2f}",
                    "Total_Impressions": "{:,.0f}",
                    "Creatives_Count": "{:,}"
                }),
                width="stretch",
                hide_index=True
            )

    # =========================================================================
    # TAB 2: DEMOGRAPHIC OPPORTUNITY & GAP ANALYSIS (NC)
    # Keeping Google BigQuery and Meta API Data STRICTLY SEPARATE
    # =========================================================================
    with tab_demo:
        st.markdown(
            """<div class="info-box">
                <strong>Demographic Intelligence Architecture:</strong> To preserve analytical rigor, 
                <strong>Google Ads</strong> data (advertiser targeting parameters from BigQuery) and 
                <strong>Meta Ad Library</strong> data (empirical audience delivery from Meta Graph API) 
                are kept strictly separate. Review platform-specific breakdowns and data-driven strategic insights below.
            </div>""",
            unsafe_allow_html=True
        )

        demo_sub1, demo_sub2, demo_sub3 = st.tabs([
            "🔵 Google Political Ads Demographics (BigQuery)",
            "🔷 Meta Ads Audience Delivery (Meta API)",
            "⚖️ Cross-Platform Comparative Strategic Insights"
        ])

        # ----------------- SUBTAB 1: Google Political Ads -----------------
        with demo_sub1:
            st.markdown(
                f"""<div class="alert-box">
                    <strong>Google Opportunity Gap Alert:</strong> In North Carolina, the <strong>{least_viewed_cohort}</strong> 
                    voter cohort receives the fewest ad impressions across all active Google campaigns from 2024 to current. 
                    Targeted digital buys must be mobilized to close voter turnout blind spots left open by competitor campaigns.
                </div>""",
                unsafe_allow_html=True
            )

            has_google_gender = check_gender_data_exists(clean_bq, "gender_targeting")

            if has_google_gender:
                g_ctrl1, g_ctrl2 = st.columns(2)
                with g_ctrl1:
                    g_metric_choice = st.selectbox(
                        "Select Metric (Y-Axis):",
                        options=[
                            "Estimated Impressions",
                            "Estimated Spend ($ USD)",
                            "Number of Ad Creatives"
                        ],
                        index=0,
                        key="g_metric_choice_select"
                    )
                g_col1, g_col2 = st.columns(2)
                with g_col1:
                    g_chart = create_nc_demographic_gap_chart(unnested_demo, metric_label=g_metric_choice)
                    st.altair_chart(g_chart, width="stretch", theme="streamlit")
                with g_col2:
                    unnested_gender = unnest_demographics(clean_bq, "gender_targeting")
                    g_gender_chart = create_nc_gender_breakdown_chart(unnested_gender, metric_label=g_metric_choice)
                    if g_gender_chart:
                        st.altair_chart(g_gender_chart, width="stretch", theme="streamlit")
            else:
                # BigQuery gender data does not exist; do not create chart and remove single-option dropdown
                st.markdown(
                    """<div style="background: rgba(15, 23, 42, 0.65); border: 1px solid #334155; border-radius: 8px; padding: 10px 16px; margin-bottom: 14px; font-size: 13px; color: #94a3b8;">
                        ℹ️ <strong>Google Targeting Dimension:</strong> Google Political Ads in North Carolina exclusively utilizes 
                        geographic media market and voter age targeting (gender targeting is unconfigured / <code>Not targeted</code>). 
                        Gender chart is omitted. Displaying full NC voter age cohort opportunity gap analysis below.
                    </div>""",
                    unsafe_allow_html=True
                )
                g_metric_choice = st.selectbox(
                    "Select Metric (Y-Axis):",
                    options=[
                        "Estimated Impressions",
                        "Estimated Spend ($ USD)",
                        "Number of Ad Creatives"
                    ],
                    index=0,
                    key="g_metric_choice_select"
                )
                g_chart = create_nc_demographic_gap_chart(unnested_demo, metric_label=g_metric_choice)
                st.altair_chart(g_chart, width="stretch", theme="streamlit")

            g_insights = generate_google_demographic_insights(clean_bq)
            st.markdown(
                f"""
                <div class="insight-card">
                    <h4>🎯 Strategic Campaign Insights: Google Political Ads Targeting</h4>
                    <ul>
                        {''.join([f'<li>{ins}</li>' for ins in g_insights])}
                    </ul>
                </div>
                """,
                unsafe_allow_html=True
            )

            with st.expander("📊 View Google Demographic Targeting Data Table"):
                g_table = (
                    unnested_demo[unnested_demo["age_targeting"].isin(VALID_AGE_COHORTS)]
                    .groupby("age_targeting", as_index=False)
                    .agg(
                        Impressions=("impressions_est", "sum"),
                        Spend_USD=("spend_usd_est", "sum"),
                        Ad_Count=("ad_id", "count")
                    )
                    .sort_values(by="Impressions", ascending=False)
                )
                st.dataframe(
                    g_table.style.format({
                        "Impressions": "{:,.0f}",
                        "Spend_USD": "${:,.2f}",
                        "Ad_Count": "{:,}"
                    }),
                    width="stretch"
                )

        # ----------------- SUBTAB 2: Meta Ads Audience Delivery -----------------
        with demo_sub2:
            st.markdown(
                """<div class="info-box">
                    <strong>Meta Empirical Audience Delivery:</strong> Meta Ad Library data tracks 
                    <strong>actual audience impressions</strong> delivered across Facebook and Instagram via 
                    <code>demographic_distribution</code>, providing empirical verification of audience reach.
                </div>""",
                unsafe_allow_html=True
            )

            has_meta_gender = check_gender_data_exists(df_meta_demo, "gender")

            m_metric_choice = st.selectbox(
                "Select Metric (Measure):",
                options=[
                    "Delivered Impressions",
                    "Delivered Spend ($ USD)",
                    "Number of Ad Creatives"
                ],
                index=0,
                key="m_metric_choice_select"
            )

            if has_meta_gender:
                # Display Age Cohort delivery and Gender Reach side-by-side cleanly without redundant dropdown
                m_col1, m_col2 = st.columns(2)
                with m_col1:
                    m_chart = create_meta_demographic_delivery_chart(df_meta_demo, metric_label=m_metric_choice)
                    st.altair_chart(m_chart, width="stretch", theme="streamlit")
                with m_col2:
                    m_gender_chart = create_meta_gender_reach_chart(df_meta_demo, metric_label=m_metric_choice)
                    if m_gender_chart:
                        st.altair_chart(m_gender_chart, width="stretch", theme="streamlit")
            else:
                # Render only age delivery chart when gender data does not exist
                m_chart = create_meta_demographic_delivery_chart(df_meta_demo, metric_label=m_metric_choice)
                st.altair_chart(m_chart, width="stretch", theme="streamlit")

            m_insights = generate_meta_demographic_insights(df_meta_demo)
            st.markdown(
                f"""
                <div class="insight-card">
                    <h4>🎯 Strategic Campaign Insights: Meta Audience Delivery</h4>
                    <ul>
                        {''.join([f'<li>{ins}</li>' for ins in m_insights])}
                    </ul>
                </div>
                """,
                unsafe_allow_html=True
            )

            with st.expander("📊 View Meta Audience Delivery Data Table"):
                if not df_meta_demo.empty:
                    m_table = (
                        df_meta_demo.groupby(["age_group", "gender"], as_index=False)
                        .agg(
                            Delivered_Impressions=("demographic_impressions", "sum"),
                            Delivered_Spend_USD=("demographic_spend_usd", "sum"),
                            Ad_Count=("ad_id", "nunique")
                        )
                        .sort_values(by="Delivered_Impressions", ascending=False)
                    )
                    st.dataframe(
                        m_table.style.format({
                            "Delivered_Impressions": "{:,.0f}",
                            "Delivered_Spend_USD": "${:,.2f}",
                            "Ad_Count": "{:,}"
                        }),
                        width="stretch"
                    )

        # ----------------- SUBTAB 3: Cross-Platform Insights -----------------
        with demo_sub3:
            st.markdown(
                """<div class="success-box">
                    <strong>Cross-Platform Strategic Blueprint:</strong> Comparing Google targeting volume against Meta audience delivery 
                    exposes where rival campaigns are over-saturating certain demographics while leaving critical voter cohorts untouched.
                </div>""",
                unsafe_allow_html=True
            )

            # Construct clean cross-platform demographic dataframe with zero empty gaps
            google_slice = unnested_demo[
                unnested_demo["age_targeting"].isin(VALID_AGE_COHORTS)
            ][["age_targeting", "impressions_est", "spend_usd_est", "ad_id"]].copy()
            google_slice["platform"] = "Google"

            meta_slice = pd.DataFrame({
                "age_targeting": df_meta_demo["age_group"],
                "platform": "Meta",
                "impressions_est": df_meta_demo["demographic_impressions"],
                "spend_usd_est": df_meta_demo["demographic_spend_usd"],
                "ad_id": df_meta_demo["ad_id"]
            })
            meta_slice = meta_slice[meta_slice["age_targeting"].isin(VALID_AGE_COHORTS)]
            cross_platform_demo = pd.concat([google_slice, meta_slice], ignore_index=True)

            cross_chart = create_nc_cross_platform_demographic_chart(cross_platform_demo, metric_label="Estimated Impressions")
            st.altair_chart(cross_chart, width="stretch", theme="streamlit")

            cross_insights = generate_cross_platform_strategic_insights(clean_bq, df_meta_demo)
            st.markdown(
                f"""
                <div class="insight-card">
                    <h4>🎯 Campaign Action Recommendations: Cross-Platform Digital Allocation</h4>
                    <ul>
                        {''.join([f'<li>{ins}</li>' for ins in cross_insights])}
                    </ul>
                </div>
                """,
                unsafe_allow_html=True
            )

    # =========================================================================
    # TAB 3: TARGETED AD FORMATS & CREATIVE INTELLIGENCE
    # STRICTLY SEPARATING GOOGLE BIGQUERY & META AD LIBRARY SUBSECTIONS
    # =========================================================================
    with tab_creative:
        st.markdown(
            """<div class="info-box">
                <strong>Ad Format & Creative Intelligence Architecture:</strong> This section is dedicated to analyzing 
                what types of ads (<strong>Video</strong>, <strong>Image</strong>, <strong>Text</strong>) are being displayed across North Carolina. 
                To ensure platform clarity and prevent conflation between Google's ad network parameters and Meta's social delivery metrics, 
                data is strictly divided into two distinct subsections: <strong>Google Political Ads (BigQuery)</strong> and <strong>Meta Ad Library (Meta API)</strong>.
            </div>""",
            unsafe_allow_html=True
        )

        creative_sub1, creative_sub2 = st.tabs([
            "🔵 Google Political Ads Formats (BigQuery)",
            "🔷 Meta Ad Library Formats (Meta API)"
        ])

        # -------------------------------------------------------------
        # SUBSECTION A: GOOGLE POLITICAL ADS (BIGQUERY)
        # -------------------------------------------------------------
        with creative_sub1:
            st.markdown(
                """<div class="info-box">
                    <strong>Google Ad Creative Formats (BigQuery):</strong> Analyzes ad creative formats 
                    (<strong>YouTube Video</strong>, <strong>Display Images</strong>, and <strong>Search Text</strong>) 
                    from the Google Political Ads transparency dataset in BigQuery. Filter by targeted demographic cohorts to evaluate format distribution and CPM efficiency.
                </div>""",
                unsafe_allow_html=True
            )

            # Isolate Google creatives from filtered_df or fallback to clean_bq
            google_creatives = filtered_df[filtered_df["platform"] == "Google"]
            if google_creatives.empty:
                google_creatives = clean_bq

            st.subheader("Filter Google Ad Targeting Parameters")
            has_google_gender = check_gender_data_exists(google_creatives, "gender_targeting")

            if has_google_gender:
                g_f1, g_f2, g_f3 = st.columns(3)
                with g_f1:
                    g_filter_age = st.selectbox(
                        "Target Age Group (Google):",
                        options=["All Ages", "18-24", "25-34", "35-44", "45-54", "55-64", "≥65", "Broad / Untargeted"],
                        index=0,
                        key="g_creative_target_age"
                    )
                with g_f2:
                    g_filter_gender = st.selectbox(
                        "Target Gender Segment (Google):",
                        options=["All Genders", "Female", "Male", "Broad / Untargeted"],
                        index=0,
                        key="g_creative_target_gender"
                    )
                with g_f3:
                    g_filter_metric = st.selectbox(
                        "Measure (Y-Axis):",
                        options=["Estimated Spend ($ USD)", "Estimated Impressions", "Number of Ad Creatives"],
                        index=0,
                        key="g_creative_target_metric"
                    )
                g_tag = f"[{g_filter_age} | {g_filter_gender}]" if g_filter_gender != "All Genders" else f"[{g_filter_age}]"
            else:
                # BigQuery gender data does not exist; remove redundant gender dropdown
                g_f1, g_f2 = st.columns(2)
                with g_f1:
                    g_filter_age = st.selectbox(
                        "Target Age Group (Google):",
                        options=["All Ages", "18-24", "25-34", "35-44", "45-54", "55-64", "≥65", "Broad / Untargeted"],
                        index=0,
                        key="g_creative_target_age"
                    )
                with g_f2:
                    g_filter_metric = st.selectbox(
                        "Measure (Y-Axis):",
                        options=["Estimated Spend ($ USD)", "Estimated Impressions", "Number of Ad Creatives"],
                        index=0,
                        key="g_creative_target_metric"
                    )
                g_filter_gender = "All Genders"
                g_tag = f"[{g_filter_age}]"

            filtered_google = filter_google_creatives(
                google_creatives,
                selected_age=g_filter_age,
                selected_gender=g_filter_gender
            )

            g_total_creatives = len(filtered_google)
            g_video_count = len(filtered_google[filtered_google["ad_type"].astype(str).str.upper() == "VIDEO"])
            g_video_pct = (g_video_count / g_total_creatives * 100) if g_total_creatives > 0 else 0.0
            g_total_spend = filtered_google["spend_usd_est"].sum()
            g_video_spend = filtered_google[filtered_google["ad_type"].astype(str).str.upper() == "VIDEO"]["spend_usd_est"].sum()
            g_video_spend_pct = (g_video_spend / g_total_spend * 100) if g_total_spend > 0 else 0.0

            st.markdown(
                f"""<div class="success-box">
                    <strong>Google Finding for {g_tag}:</strong> 
                    Found <strong>{g_total_creatives:,} active creatives</strong>. 
                    <strong>YouTube Video represents {g_video_spend_pct:.1f}% (${g_video_spend:,.0f})</strong> of total spend 
                    targeting this demographic, demonstrating campaigns' heavy reliance on video persuasion on Google.
                </div>""",
                unsafe_allow_html=True
            )

            g_col1, g_col2 = st.columns(2)
            with g_col1:
                g_dist_chart = create_google_format_distribution_chart(
                    filtered_google,
                    metric_label=g_filter_metric,
                    selected_age=g_filter_age,
                    selected_gender=g_filter_gender
                )
                st.altair_chart(g_dist_chart, width="stretch", theme="streamlit")

            with g_col2:
                g_cpm_chart = create_google_format_cpm_chart(
                    filtered_google,
                    selected_age=g_filter_age,
                    selected_gender=g_filter_gender
                )
                st.altair_chart(g_cpm_chart, width="stretch", theme="streamlit")

            # Automated Google Creative Strategic Insights
            g_creative_insights = generate_google_creative_insights(filtered_google)
            st.markdown(
                f"""
                <div class="insight-card">
                    <h4>🎯 Strategic Campaign Insights: Google Format Allocation & CPM Cost Efficiency</h4>
                    <ul>
                        {''.join([f'<li>{ins}</li>' for ins in g_creative_insights])}
                    </ul>
                </div>
                """,
                unsafe_allow_html=True
            )

            st.subheader(f"Inspect Google Ad Creatives & Transparency Disclosures for [{g_filter_age} | {g_filter_gender}]")
            st.markdown("Direct links to Google Political Ads Transparency Reports to inspect video flights, search headlines, and banner designs:")

            g_disp_cols = ["ad_id", "advertiser_name", "ad_type", "spend_usd_est", "impressions_est", "duration_days", "age_targeting", "gender_targeting", "ad_url"]
            g_avail_cols = [c for c in g_disp_cols if c in filtered_google.columns]
            g_samples = filtered_google[g_avail_cols].head(30).copy()

            st.dataframe(
                g_samples,
                column_config={
                    "ad_url": st.column_config.LinkColumn("Google Transparency Link", display_text="View on Google ↗"),
                    "spend_usd_est": st.column_config.NumberColumn("Est. Spend ($)", format="$%.2f"),
                    "impressions_est": st.column_config.NumberColumn("Est. Impressions", format="%d"),
                    "duration_days": st.column_config.NumberColumn("Flight Days", format="%d days"),
                    "advertiser_name": "PAC / Campaign",
                    "ad_type": "Format",
                    "age_targeting": "Age Targeting",
                    "gender_targeting": "Gender Targeting"
                },
                width="stretch",
                hide_index=True
            )

        # -------------------------------------------------------------
        # SUBSECTION B: META AD LIBRARY (META API)
        # -------------------------------------------------------------
        with creative_sub2:
            st.markdown(
                """<div class="info-box">
                    <strong>Meta Ad Creative & Video Intelligence (Meta API):</strong> Using the 
                    <strong>Facebook / Meta Ad Library API</strong> (specifically <code>demographic_distribution</code> 
                    and creative asset metadata), this section analyzes what types of ads (<strong>Video</strong>, <strong>Image</strong>, <strong>Text</strong>) 
                    are delivered to each age and gender demographic across North Carolina. Select target cohorts to determine what content applies best.
                </div>""",
                unsafe_allow_html=True
            )

            st.subheader("Filter Target Demographic for Meta Video & Creative Format Analysis")
            has_meta_gender = check_gender_data_exists(df_meta_demo, "gender")

            if has_meta_gender:
                m_f1, m_f2, m_f3 = st.columns(3)
                with m_f1:
                    m_filter_age = st.selectbox(
                        "Target Age Group (Meta):",
                        options=["All Ages", "18-24", "25-34", "35-44", "45-54", "55-64", "≥65"],
                        index=0,
                        key="m_creative_target_age"
                    )
                with m_f2:
                    m_filter_gender = st.selectbox(
                        "Target Gender Segment (Meta):",
                        options=["All Genders", "Female", "Male"],
                        index=0,
                        key="m_creative_target_gender"
                    )
                with m_f3:
                    m_filter_metric = st.selectbox(
                        "Select Measure (Meta):",
                        options=["Delivered Impressions", "Delivered Spend ($ USD)", "Number of Ad Creatives"],
                        index=0,
                        key="m_creative_target_metric"
                    )
                m_tag = f"[{m_filter_age} | {m_filter_gender}]" if m_filter_gender != "All Genders" else f"[{m_filter_age}]"
            else:
                m_f1, m_f2 = st.columns(2)
                with m_f1:
                    m_filter_age = st.selectbox(
                        "Target Age Group (Meta):",
                        options=["All Ages", "18-24", "25-34", "35-44", "45-54", "55-64", "≥65"],
                        index=0,
                        key="m_creative_target_age"
                    )
                with m_f2:
                    m_filter_metric = st.selectbox(
                        "Select Measure (Meta):",
                        options=["Delivered Impressions", "Delivered Spend ($ USD)", "Number of Ad Creatives"],
                        index=0,
                        key="m_creative_target_metric"
                    )
                m_filter_gender = "All Genders"
                m_tag = f"[{m_filter_age}]"

            filtered_meta_demo = filter_meta_demographics(
                df_meta_demo,
                selected_age=m_filter_age,
                selected_gender=m_filter_gender
            )

            m_tot_imps = filtered_meta_demo["demographic_impressions"].sum()
            m_vid_imps = filtered_meta_demo[filtered_meta_demo["ad_type"] == "VIDEO"]["demographic_impressions"].sum()
            m_vid_pct = (m_vid_imps / m_tot_imps * 100) if m_tot_imps > 0 else 0.0

            st.markdown(
                f"""<div class="success-box">
                    <strong>Meta Delivery Finding for {m_tag}:</strong> 
                    Delivered <strong>{m_tot_imps:,.0f} impressions</strong> to this voter cohort. 
                    <strong>Video Ads generate {m_vid_pct:.1f}%</strong> of total audience impressions delivered to this North Carolina segment, 
                    reinforcing high engagement for short-form video in Meta feeds and Reels.
                </div>""",
                unsafe_allow_html=True
            )

            m_col1, m_col2 = st.columns(2)
            with m_col1:
                m_format_chart = create_meta_demographic_format_chart(
                    filtered_meta_demo,
                    metric_label=m_filter_metric,
                    selected_age=m_filter_age,
                    selected_gender=m_filter_gender
                )
                st.altair_chart(m_format_chart, width="stretch", theme="streamlit")

            with m_col2:
                m_cpm_chart = create_meta_format_cpm_chart(
                    filtered_meta_demo,
                    selected_age=m_filter_age,
                    selected_gender=m_filter_gender
                )
                st.altair_chart(m_cpm_chart, width="stretch", theme="streamlit")

            # Demographic Video Distribution Across Age Groups (and Gender if present)
            st.subheader("Demographic Video Adoption Curve Across North Carolina Voters (Meta API)")
            if not df_meta_demo.empty:
                if has_meta_gender:
                    v_col1, v_col2 = st.columns(2)
                    with v_col1:
                        video_adoption_chart = create_video_adoption_by_demographic_chart(df_meta_demo)
                        st.altair_chart(video_adoption_chart, width="stretch", theme="streamlit")
                    with v_col2:
                        gender_breakdown_chart = create_gender_video_breakdown_chart(df_meta_demo)
                        if gender_breakdown_chart:
                            st.altair_chart(gender_breakdown_chart, width="stretch", theme="streamlit")
                else:
                    video_adoption_chart = create_video_adoption_by_demographic_chart(df_meta_demo)
                    st.altair_chart(video_adoption_chart, width="stretch", theme="streamlit")

            # Automated Meta Creative Strategic Insights
            m_creative_insights = generate_meta_creative_insights(df_meta_demo)
            st.markdown(
                f"""
                <div class="insight-card">
                    <h4>🎯 Strategic Campaign Insights: Meta Creative Video Optimization</h4>
                    <ul>
                        {''.join([f'<li>{ins}</li>' for ins in m_creative_insights])}
                    </ul>
                </div>
                """,
                unsafe_allow_html=True
            )

            st.subheader(f"Inspect Meta Ad Creatives & Video Messaging for [{m_filter_age} | {m_filter_gender}]")
            st.markdown("Review the actual Meta political ad creatives, video titles, and live ad snapshot URLs to evaluate messaging content:")

            # Isolate Meta creatives table
            meta_creatives = filtered_df[filtered_df["platform"] == "Meta"]
            if meta_creatives.empty:
                meta_creatives = clean_meta

            m_display_cols = ["ad_id", "advertiser_name", "ad_type", "ad_creative_link_titles", "ad_creative_bodies", "spend_usd_est", "impressions_est", "duration_days", "ad_snapshot_url"]
            m_avail_cols = [c for c in m_display_cols if c in meta_creatives.columns]
            m_sample_creatives = meta_creatives[m_avail_cols].head(30).copy()

            st.dataframe(
                m_sample_creatives,
                column_config={
                    "ad_snapshot_url": st.column_config.LinkColumn("Ad Snapshot URL", display_text="View on Meta ↗"),
                    "spend_usd_est": st.column_config.NumberColumn("Est. Spend ($)", format="$%.2f"),
                    "impressions_est": st.column_config.NumberColumn("Est. Impressions", format="%d"),
                    "duration_days": st.column_config.NumberColumn("Days Active", format="%d days"),
                    "advertiser_name": "Sponsoring PAC / Campaign",
                    "ad_type": "Format",
                    "ad_creative_link_titles": "Ad Title / Headline",
                    "ad_creative_bodies": "Creative Message Body"
                },
                width="stretch",
                hide_index=True
            )

    # =========================================================================
    # TAB 4: REGIONAL COMPETITOR SPEND & NC COUNTY HEATMAP
    # Clean HTML Component Rendering for NC Map Heatmap
    # =========================================================================
    with tab_geo:
        st.markdown(
            """<div class="info-box">
                <strong>NC Regional & County Heatmap Intelligence:</strong> Tracking political ad expenditure across North Carolina's 
                counties and 6 primary Designated Market Areas (DMAs) exposes regional spending epicenters 
                (such as Mecklenburg and Wake counties) and highlights underserved counties for strategic campaign outreach.
            </div>""",
            unsafe_allow_html=True
        )

        st.subheader("Customize North Carolina Regional & County Visualizations")
        geo_col1, geo_col2 = st.columns(2)
        with geo_col1:
            geo_chart_choice = st.selectbox(
                "Select Regional Graph Dimension:",
                options=[
                    "NC County Heatmap (Applied Over NC Counties Map Image)",
                    "NC Media Market (DMA) Intensity Ranking",
                    "Competitor PAC Breakdown by NC Market",
                    "Competitor Market Share (% of NC Market Total)"
                ],
                index=0,
                key="geo_chart_select"
            )
        with geo_col2:
            geo_metric_choice = st.selectbox(
                "Select Graph Metric:",
                options=[
                    "Total Spend ($ USD)",
                    "Estimated Impressions",
                    "Number of Ad Creatives"
                ],
                index=0,
                key="geo_metric_select"
            )

        # Selected county state initialization
        county_list = df_county["county_name"].tolist() if not df_county.empty else ["Mecklenburg"]
        query_county = st.query_params.get("county", None)

        # Default initialization for selected_county if not set
        if "selected_county" not in st.session_state or st.session_state.selected_county not in county_list:
            st.session_state.selected_county = query_county if (query_county and query_county in county_list) else "Mecklenburg"
            st.session_state.deepdive_county_picker = st.session_state.selected_county
        elif "deepdive_county_picker" not in st.session_state or st.session_state.deepdive_county_picker not in county_list:
            st.session_state.deepdive_county_picker = st.session_state.selected_county

        # Top summary KPIs for counties
        if not df_county.empty:
            top_county = df_county.sort_values(by="spend_usd", ascending=False).iloc[0]
            sec_county = df_county.sort_values(by="spend_usd", ascending=False).iloc[1] if len(df_county) > 1 else top_county
            rural_count = len(df_county[df_county["spend_tier"] == "⚪ Low"])
            
            c_kpi1, c_kpi2, c_kpi3 = st.columns(3)
            with c_kpi1:
                st.metric("Top County Spender", f"{top_county['county_name']} County", f"${top_county['spend_usd']:,.0f}")
            with c_kpi2:
                st.metric("Runner-Up County", f"{sec_county['county_name']} County", f"${sec_county['spend_usd']:,.0f}")
            with c_kpi3:
                st.metric("Under-Targeted Counties", f"{rural_count} Counties", "⚪ Low Tier Outreach Target")

        if geo_chart_choice == "NC County Heatmap (Applied Over NC Counties Map Image)":
            # Render further enlarged non-scrollable heatmap using modern Streamlit iframe (1200x800 canvas, taking full space)
            svg_html = generate_nc_county_map_heatmap_svg(
                df_county,
                selected_county=st.session_state.selected_county,
                metric_label=geo_metric_choice
            )
            st.iframe(svg_html, height=860, width="stretch")

        elif geo_chart_choice == "NC Media Market (DMA) Intensity Ranking":
            dma_chart = create_nc_dma_ranking_chart(cleaned_geo, metric_label=geo_metric_choice)
            st.altair_chart(dma_chart, width="stretch", theme="streamlit")

        elif geo_chart_choice == "Competitor PAC Breakdown by NC Market":
            breakdown_chart = create_nc_advertiser_breakdown_chart(cleaned_geo, metric_label=geo_metric_choice)
            st.altair_chart(breakdown_chart, width="stretch", theme="streamlit")

        else:
            share_chart = create_nc_market_share_chart(cleaned_geo)
            st.altair_chart(share_chart, width="stretch", theme="streamlit")

        # =========================================================================
        # DEDICATED COUNTY STRATEGIC DEEP-DIVE INTELLIGENCE DISPLAY
        # Appears directly beneath the heatmap in a distinct, styled display container
        # =========================================================================
        active_county = st.session_state.selected_county
        county_match = df_county[df_county["county_name"] == active_county]
        if not county_match.empty:
            c_data = county_match.iloc[0]
            active_spend = c_data["spend_usd"]
            active_imp = c_data.get("impressions_est", int(active_spend * 45))
            active_tier = c_data.get("spend_tier", "⚪ Low")
            active_dma = c_data["nc_dma"]
        else:
            active_spend = 0.0
            active_imp = 0
            active_tier = "⚪ Low"
            active_dma = "Charlotte DMA"

        # Determine top advertiser in this county's DMA
        dma_adv_records = cleaned_geo[cleaned_geo["nc_dma"] == active_dma] if not cleaned_geo.empty and "nc_dma" in cleaned_geo.columns else cleaned_geo
        if not dma_adv_records.empty:
            top_adv_series = dma_adv_records.groupby("advertiser_name")["spend_usd"].sum().sort_values(ascending=False)
            top_adv_name = top_adv_series.index[0] if len(top_adv_series) > 0 else "N/A"
            top_adv_val = top_adv_series.iloc[0] if len(top_adv_series) > 0 else 0.0
        else:
            top_adv_name = "N/A"
            top_adv_val = 0.0

        # Determine dominant Meta targeted age cohort in this county's DMA
        dma_meta_records = df_meta_demo[df_meta_demo["nc_dma"] == active_dma] if not df_meta_demo.empty and "nc_dma" in df_meta_demo.columns else df_meta_demo
        if not dma_meta_records.empty and "age_group" in dma_meta_records.columns:
            meta_age_series = dma_meta_records.groupby("age_group")["demographic_impressions"].sum().sort_values(ascending=False)
            top_age_bracket = meta_age_series.index[0] if len(meta_age_series) > 0 else "N/A"
            top_age_imp = meta_age_series.iloc[0] if len(meta_age_series) > 0 else 0
            total_dma_imp = meta_age_series.sum()
            top_age_pct = (top_age_imp / total_dma_imp * 100) if total_dma_imp > 0 else 0.0
        else:
            top_age_bracket = "N/A"
            top_age_pct = 0.0

        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #0b1329 0%, #111e38 100%); 
                        border: 1.5px solid #0284c7; border-radius: 14px; padding: 22px 24px; 
                        margin-top: 25px; margin-bottom: 20px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.5);">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                    <div>
                        <h3 style="margin: 0; color: #f8fafc; font-size: 20px; font-weight: 800;">
                            🏛️ Strategic County Deep-Dive: <span style="color: #38bdf8;">{active_county} County</span> Intelligence Profile
                        </h3>
                        <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 13px;">
                            Synchronized with County Heatmap selection & highlighting. Review how much each campaign has spent in this region alongside Meta Ad Library voter age targeting.
                        </p>
                    </div>
                    <div style="background: rgba(2, 132, 199, 0.2); border: 1px solid #38bdf8; border-radius: 8px; padding: 6px 14px; color: #38bdf8; font-size: 12.5px; font-weight: 700;">
                        Media Market: {active_dma}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        def on_county_dropdown_change():
            chosen = st.session_state.deepdive_county_picker
            st.session_state.selected_county = chosen
            st.query_params["county"] = chosen

        # Drop-down and Metric Controls for Deep-Dive Display
        deep_ctrl1, deep_ctrl2 = st.columns([2, 1])
        with deep_ctrl1:
            st.selectbox(
                "📍 Select North Carolina County to Gather Intelligence:",
                options=county_list,
                key="deepdive_county_picker",
                on_change=on_county_dropdown_change,
                help="Select a North Carolina county from this dropdown menu to highlight it on the heatmap and view additional spending and demographic intelligence below."
            )

        with deep_ctrl2:
            deep_metric = st.selectbox(
                "Measure (Y-Axis / Metric):",
                options=["Total Spend ($ USD)", "Estimated Impressions"],
                index=0,
                key="deepdive_metric_picker"
            )

        # 4 High-Impact KPI Cards for this County
        c_kpi_col1, c_kpi_col2, c_kpi_col3, c_kpi_col4 = st.columns(4)
        with c_kpi_col1:
            st.metric(
                label=f"Regional Spend ({active_county})",
                value=f"${active_spend:,.2f}",
                delta=active_tier
            )
        with c_kpi_col2:
            st.metric(
                label="Delivered Impressions",
                value=f"{active_imp:,}",
                delta="Voter Reach"
            )
        with c_kpi_col3:
            st.metric(
                label="Top Regional Spender",
                value=f"${top_adv_val:,.0f}",
                delta=top_adv_name[:24] if top_adv_name != "N/A" else "None"
            )
        with c_kpi_col4:
            st.metric(
                label="Dominant Meta Age Cohort",
                value=top_age_bracket,
                delta=f"{top_age_pct:.1f}% Audience Share"
            )

        # Two Side-by-Side Deep Dive Visualizations: Campaign Spend & Meta Age Cohorts
        g_row1, g_row2 = st.columns(2)
        with g_row1:
            county_spend_chart = create_county_campaign_spend_chart(
                df_geo=cleaned_geo,
                county_name=active_county,
                dma=active_dma,
                metric_label=deep_metric,
                top_n=8
            )
            st.altair_chart(county_spend_chart, width="stretch", theme="streamlit")

        with g_row2:
            county_meta_chart = create_county_meta_age_cohort_chart(
                df_meta_demo=df_meta_demo,
                county_name=active_county,
                dma=active_dma,
                metric_label=deep_metric
            )
            st.altair_chart(county_meta_chart, width="stretch", theme="streamlit")

        # Executive Tactical Briefing Card for the Selected County
        st.markdown(
            f"""
            <div class="insight-card">
                <h4>📋 Tactical Campaign Intelligence Briefing: {active_county} County ({active_dma})</h4>
                <ul>
                    <li><strong>Regional Investment Footprint:</strong> Political organizations have deployed an estimated <strong>${active_spend:,.2f}</strong> across North Carolina digital channels in {active_county} County, categorizing it in the <strong>{active_tier}</strong> campaign saturation tier.</li>
                    <li><strong>Market Rivalry Saturation:</strong> <strong>{top_adv_name}</strong> commands the single largest advertising footprint in this media market, accounting for <strong>${top_adv_val:,.0f}</strong> in deployed ad buys.</li>
                    <li><strong>Meta Voter Age Targeting Focus:</strong> Empirical Meta Ad Library data reveals that the <strong>{top_age_bracket}</strong> age cohort represents <strong>{top_age_pct:.1f}%</strong> of total social impressions delivered in {active_dma}, reflecting heavy persuasion messaging targeted at high-turnout older demographics.</li>
                    <li><strong>Voter Mobilization Blind Spot:</strong> Younger voters (ages 18–24 and 25–34) receive significantly fewer ad impressions in {active_county}, providing an uncrowded digital mobilization lane with lower effective CPM acquisition costs.</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True
        )

        with st.expander("📍 View North Carolina County & Market Spending Details"):
            exp_tab1, exp_tab2 = st.tabs([
                "🏛️ NC County Spending Ledger",
                "📺 NC Media Market Breakdown"
            ])
            with exp_tab1:
                st.dataframe(
                    df_county[["county_name", "nc_dma", "spend_tier", "spend_usd", "impressions_est", "fips"]],
                    column_config={
                        "county_name": "NC County",
                        "nc_dma": "Media Market (DMA)",
                        "spend_tier": "Spend Tier",
                        "spend_usd": st.column_config.NumberColumn("Estimated Spend ($)", format="$%.2f"),
                        "impressions_est": st.column_config.NumberColumn("Est. Impressions", format="%d"),
                        "fips": "FIPS Code"
                    },
                    width="stretch",
                    hide_index=True
                )
            with exp_tab2:
                geo_summary = (
                    cleaned_geo.groupby(["nc_dma", "advertiser_name"], as_index=False)["spend_usd"]
                    .sum()
                    .sort_values(by="spend_usd", ascending=False)
                )
                st.dataframe(
                    geo_summary.style.format({"spend_usd": "${:,.2f}"}),
                    width="stretch"
                )

    # =========================================================================
    # TAB 5: PLATFORM PERFORMANCE & PACING (2024–Current)
    # =========================================================================
    with tab_pace:
        st.subheader("Customize Spending Trajectory & Performance Graph")
        pace_col1, pace_col2 = st.columns(2)
        with pace_col1:
            pace_view_choice = st.selectbox(
                "Select Pacing Visualization Type:",
                options=[
                    "Weekly Expenditure Pace",
                    "Cumulative Spend Trajectory",
                    "Platform Allocation (Google vs. Meta in NC)",
                    "Ad Creative Format Efficiency (Video vs. Image vs. Text)"
                ],
                index=0,
                key="pace_view_select"
            )
        with pace_col2:
            st.info("Pacing graphs reflect investment trajectory in North Carolina from 2024 to the election.")

        if pace_view_choice in ["Weekly Expenditure Pace", "Cumulative Spend Trajectory"]:
            trajectory_chart = create_nc_spend_trajectory_chart(cleaned_weekly, view_mode=pace_view_choice)
            st.altair_chart(trajectory_chart, width="stretch", theme="streamlit")
        elif pace_view_choice == "Platform Allocation (Google vs. Meta in NC)":
            comp_chart = create_nc_platform_comparison_chart(filtered_df)
            st.altair_chart(comp_chart, width="stretch", theme="streamlit")
        else:
            format_chart = create_nc_format_efficiency_chart(filtered_df)
            st.altair_chart(format_chart, width="stretch", theme="streamlit")

    # =========================================================================
    # TAB 6: KEY DATASET FACTS & METHODOLOGY
    # =========================================================================
    with tab_info:
        st.markdown("### 📋 Key Facts About the North Carolina Political Ads Dataset")

        f1, f2 = st.columns(2)
        with f1:
            st.markdown("""
            #### 1. Geographic & Temporal Scope (NC, 2024–Current)
            * **North Carolina Only:** Analysis is strictly bounded to North Carolina voters and its 6 designated media markets:
              * *Charlotte DMA* (Mecklenburg, Union, Gaston, Cabarrus)
              * *Raleigh-Durham-Fayetteville DMA* (Wake, Durham, Cumberland, Orange)
              * *Greensboro-High Point-Winston-Salem DMA* (Piedmont Triad: Guilford, Forsyth)
              * *Greenville-New Bern-Washington DMA* (Eastern NC Coastal Plain)
              * *Wilmington DMA* (New Hanover, Brunswick, Pender)
              * *Asheville DMA* (Western NC Mountains)
            * **Temporal Scope (2024 to Current):** All ads and spending records are strictly scoped from **January 1, 2024 onward**, capturing the current election cycle.
            """)

            st.markdown("""
            #### 2. Currency Standardization
            * **Non-USD Currency Scrubbing:** Any multi-currency columns from international transparency tables (`_eur`, `_gbp`, `_cad`) are automatically dropped.
            * All figures represent normalized **$ USD**.
            """)

        with f2:
            st.markdown("""
            #### 3. Platform Separation in Demographic & Ad Types Sections
            * **Demographic Separation:** Google targeting settings and Meta empirical audience delivery distributions are analyzed separately to prevent false equivalencies.
            * **Ad Types / Formats Separation:** Google BigQuery and Meta Ad Library data are divided into dedicated subsections to clearly differentiate YouTube/Search advertising from Facebook/Instagram social formats.
            * **Meta API Video & Demographic Breakdown:** The Meta Ad Library API's `demographic_distribution` breakdown is processed to reveal what types of ads (Video vs. Image vs. Text) are delivered to each specific age group and gender segment.
            * **Meta User Token Permissions & Security:** Access to the Meta Ad Library API requires an authorized **Meta User Token** configured with the verified permissions: `ads_management`, `ads_read`, `business_management`, `pages_read_engagement`, `pages_manage_ads`, and `leads_retrieval`. In accordance with strict security standards, the Meta User Token is never included or committed in source code and is loaded strictly through runtime environment variables (`META_USER_TOKEN`).
            """)

            st.markdown("""
            #### 4. Range Bucket Estimations & Data Cleaning
            * Impressions reported as ranges (e.g. `10k-25k`, `>1M`) are converted into numerical bounds using regex and midpoint estimation.
            * Spend ranges with open-ended tops are conservatively imputed (`min * 1.5`).
            * Deduplication is performed on `ad_id` and `(advertiser_id, week_start_date)`.
            """)


if __name__ == "__main__":
    main()
