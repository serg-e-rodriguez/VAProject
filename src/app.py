"""
Streamlit Entry Point: North Carolina Political Ads Strategic Intelligence Dashboard
Analyzes demographic reach gaps among NC voters and regional competitor spend across NC DMAs.
Features dynamic drop-down menus for complete interactive control over visualizations.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
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
        generate_nc_county_spend,
        NC_DMAS
    )
    from src.components.audience_charts import (
        create_nc_demographic_gap_chart,
        create_nc_gender_breakdown_chart,
        create_nc_cross_platform_demographic_chart
    )
    from src.components.geo_charts import (
        create_nc_dma_ranking_chart,
        create_nc_advertiser_breakdown_chart,
        create_nc_market_share_chart,
        create_nc_county_heatmap_chart,
        create_nc_county_choropleth_chart
    )
    from src.components.spend_charts import (
        create_nc_spend_trajectory_chart,
        create_nc_format_efficiency_chart,
        create_nc_platform_comparison_chart
    )
    from src.components.creative_charts import (
        filter_creatives_by_demographic,
        create_demographic_format_distribution_chart,
        create_format_cpm_efficiency_chart
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
        generate_nc_county_spend,
        NC_DMAS
    )
    from components.audience_charts import (
        create_nc_demographic_gap_chart,
        create_nc_gender_breakdown_chart,
        create_nc_cross_platform_demographic_chart
    )
    from components.geo_charts import (
        create_nc_dma_ranking_chart,
        create_nc_advertiser_breakdown_chart,
        create_nc_market_share_chart,
        create_nc_county_heatmap_chart,
        create_nc_county_choropleth_chart
    )
    from components.spend_charts import (
        create_nc_spend_trajectory_chart,
        create_nc_format_efficiency_chart,
        create_nc_platform_comparison_chart
    )
    from components.creative_charts import (
        filter_creatives_by_demographic,
        create_demographic_format_distribution_chart,
        create_format_cpm_efficiency_chart
    )

# Page configuration
st.set_page_config(
    page_title="North Carolina Political Ads Intelligence Dashboard",
    page_icon="🌲",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
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
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 16px;
    }
    .info-box {
        background-color: rgba(59, 130, 246, 0.12);
        border-left: 4px solid #3b82f6;
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 16px;
    }
    .dropdown-container {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 14px;
    }
</style>
""", unsafe_allow_html=True)


def main():
    # Header
    st.title("🌲 North Carolina Political Ads Strategic Intelligence Dashboard")
    st.markdown(
        "**Battleground North Carolina Analytics:** Comparing political advertising data from "
        "**Google Cloud BigQuery** and the **Meta Ad Library** to identify under-served voter demographics "
        "and track competitor spend across North Carolina media markets (DMAs)."
    )

    # Ingest Data
    with st.spinner("Ingesting and harmonizing North Carolina political ad data..."):
        raw_bq_creatives, bq_live = load_bigquery_creative_stats(limit=3000)
        raw_meta_ads, meta_live = load_meta_ads(max_records=1500)
        raw_geo, geo_live = load_bigquery_geo_spend()
        raw_weekly, weekly_live = load_bigquery_weekly_spend()

        clean_bq = clean_creative_stats(raw_bq_creatives)
        clean_meta = clean_creative_stats(raw_meta_ads)
        combined_creatives = pd.concat([clean_bq, clean_meta], ignore_index=True)
        
        cleaned_geo = clean_geo_spend(raw_geo)
        cleaned_weekly = clean_advertiser_weekly_spend(raw_weekly)
        df_county = generate_nc_county_spend(cleaned_geo)

    # Badges
    st.markdown(
        f"""
        <div style="display:flex; gap:12px; margin-bottom: 20px; flex-wrap:wrap;">
            <span style="background:#059669; color:white; padding:4px 12px; border-radius:12px; font-size:12px; font-weight:600;">
                Scope: North Carolina (NC Only)
            </span>
            <span style="background:{'#10b981' if bq_live else '#f59e0b'}; color:black; padding:4px 10px; border-radius:12px; font-size:12px; font-weight:600;">
                BigQuery: {'Live Connected' if bq_live else 'NC Public Sample Dataset'}
            </span>
            <span style="background:{'#10b981' if meta_live else '#f59e0b'}; color:black; padding:4px 10px; border-radius:12px; font-size:12px; font-weight:600;">
                Meta Ad Library: {'Live Connected' if meta_live else 'NC Public Sample Dataset'}
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

    st.sidebar.divider()
    st.sidebar.markdown(
        "**Interactive Feature:**\n"
        "Use the **drop-down menus** located directly above each chart card to change what the visualization displays!"
    )

    # -----------------------------
    # Executive Key Facts & Metrics (NC Scope)
    # -----------------------------
    total_spend = filtered_df["spend_usd_est"].sum()
    total_impressions = filtered_df["impressions_est"].sum()
    total_ads = len(filtered_df)

    unnested_demo = unnest_demographics(filtered_df, "age_targeting")
    demo_reach = unnested_demo.groupby("age_targeting")["impressions_est"].sum()
    least_viewed_cohort = demo_reach.idxmin() if not demo_reach.empty else "N/A"

    top_dma_spend = cleaned_geo.groupby("nc_dma")["spend_usd"].sum()
    top_spend_dma = top_dma_spend.idxmax() if not top_dma_spend.empty else "N/A"
    top_dma_val = top_dma_spend.max() if not top_dma_spend.empty else 0.0

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.markdown(
            f"""<div class="metric-card">
                <div class="metric-label">Total NC Spend Analyzed</div>
                <div class="metric-value">${total_spend:,.0f}</div>
            </div>""",
            unsafe_allow_html=True
        )
    with kpi2:
        st.markdown(
            f"""<div class="metric-card">
                <div class="metric-label">NC Ad Creatives Tracked</div>
                <div class="metric-value">{total_ads:,}</div>
            </div>""",
            unsafe_allow_html=True
        )
    with kpi3:
        st.markdown(
            f"""<div class="metric-card">
                <div class="metric-label">🚨 Top NC Demographic Gap</div>
                <div class="metric-value" style="color: #ef4444;">{least_viewed_cohort}</div>
            </div>""",
            unsafe_allow_html=True
        )
    with kpi4:
        st.markdown(
            f"""<div class="metric-card">
                <div class="metric-label">🗺️ Most Saturated NC Market</div>
                <div class="metric-value" style="color: #f59e0b;">{top_spend_dma.replace(' DMA', '')} (${top_dma_val/1e6:.1f}M)</div>
            </div>""",
            unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # -----------------------------
    # Main Dashboard Tabs
    # -----------------------------
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🎯 Demographic Opportunity & Gap Analysis (NC)",
        "🎬 Targeted Ad Content & Formats (Age & Gender Filter)",
        "🗺️ Regional Competitor Spend & NC County Heatmap",
        "📈 Platform Performance & Pacing (NC)",
        "ℹ️ Key Dataset Facts & Methodology"
    ])

    # -----------------------------------------------------------
    # TAB 1: Demographic Opportunity & Gap Analysis (NC)
    # -----------------------------------------------------------
    with tab1:
        st.markdown(
            f"""<div class="alert-box">
                <strong>Campaign Action Alert:</strong> In North Carolina, the <strong>{least_viewed_cohort}</strong> 
                demographic cohort is receiving the fewest ad impressions across all active campaigns. 
                Our field team must prioritize targeted digital buys and grassroots outreach toward this under-served 
                North Carolina voter group to close voter turnout gaps.
            </div>""",
            unsafe_allow_html=True
        )

        st.subheader("Customize Demographic Visualization")
        ctrl_col1, ctrl_col2 = st.columns(2)
        with ctrl_col1:
            demo_chart_choice = st.selectbox(
                "Select Demographic Graph Dimension:",
                options=[
                    "Voter Age Cohorts (Opportunity Gap Analysis - Least Viewed in NC)",
                    "Gender Targeting Distribution",
                    "Cross-Platform Demographic Penetration (Google vs. Meta in NC)"
                ],
                index=0,
                key="demo_chart_select"
            )
        with ctrl_col2:
            demo_metric_choice = st.selectbox(
                "Select Graph Metric (Y-Axis):",
                options=[
                    "Estimated Impressions",
                    "Estimated Spend ($ USD)",
                    "Number of Ad Creatives"
                ],
                index=0,
                key="demo_metric_select"
            )

        if demo_chart_choice == "Voter Age Cohorts (Opportunity Gap Analysis - Least Viewed in NC)":
            gap_chart = create_nc_demographic_gap_chart(unnested_demo, metric_label=demo_metric_choice)
            st.altair_chart(gap_chart, use_container_width=True, theme="streamlit")
        elif demo_chart_choice == "Gender Targeting Distribution":
            gender_chart = create_nc_gender_breakdown_chart(filtered_df, metric_label=demo_metric_choice)
            st.altair_chart(gender_chart, use_container_width=True, theme="streamlit")
        else:
            cross_chart = create_nc_cross_platform_demographic_chart(unnested_demo, metric_label=demo_metric_choice)
            st.altair_chart(cross_chart, use_container_width=True, theme="streamlit")

        with st.expander("📊 View Detailed North Carolina Demographic Data Table"):
            summary_table = (
                unnested_demo.groupby("age_targeting")
                .agg(
                    Total_Impressions=("impressions_est", "sum"),
                    Total_Spend_USD=("spend_usd_est", "sum"),
                    Total_Ads=("ad_id", "count")
                )
                .sort_values(by="Total_Impressions", ascending=True)
                .reset_index()
            )
            summary_table["Impression_Share"] = (summary_table["Total_Impressions"] / summary_table["Total_Impressions"].sum()) * 100
            st.dataframe(
                summary_table.style.format({
                    "Total_Impressions": "{:,.0f}",
                    "Total_Spend_USD": "${:,.2f}",
                    "Total_Ads": "{:,}",
                    "Impression_Share": "{:.2f}%"
                }),
                use_container_width=True
            )

    # -----------------------------------------------------------
    # TAB 2: Targeted Ad Content & Formats (Age & Gender Filter)
    # -----------------------------------------------------------
    with tab2:
        st.markdown(
            """<div class="info-box">
                <strong>Targeted Creative Intelligence:</strong> Select specific <strong>voter age groups</strong> 
                and <strong>gender segments</strong> to analyze what types of ads (Video, Image, Text) are being deployed 
                to them across North Carolina, evaluate CPM delivery efficiency, and inspect active creative messaging.
            </div>""",
            unsafe_allow_html=True
        )

        st.subheader("Filter Target Demographic for Creative Analysis")
        filter_col1, filter_col2, filter_col3 = st.columns(3)
        with filter_col1:
            client_age = st.selectbox(
                "Select Target Age Group:",
                options=["All Ages", "18-24", "25-34", "35-44", "45-54", "55-64", "≥65"],
                index=0,
                key="client_target_age"
            )
        with filter_col2:
            client_gender = st.selectbox(
                "Select Target Gender Segment:",
                options=["All Genders", "Female", "Male", "Broad / Untargeted"],
                index=0,
                key="client_target_gender"
            )
        with filter_col3:
            client_metric = st.selectbox(
                "Select Measure:",
                options=["Estimated Spend ($ USD)", "Estimated Impressions", "Number of Ad Creatives"],
                index=0,
                key="client_target_metric"
            )

        demo_filtered_creatives = filter_creatives_by_demographic(filtered_df, selected_age=client_age, selected_gender=client_gender)

        st.markdown(f"**Found {len(demo_filtered_creatives):,} ad creatives** targeted to **{client_age}** | **{client_gender}** voters in North Carolina.")

        c_col1, c_col2 = st.columns(2)
        with c_col1:
            format_dist_chart = create_demographic_format_distribution_chart(
                demo_filtered_creatives,
                selected_age=client_age,
                selected_gender=client_gender,
                metric_label=client_metric
            )
            st.altair_chart(format_dist_chart, use_container_width=True, theme="streamlit")

        with c_col2:
            cpm_eff_chart = create_format_cpm_efficiency_chart(
                demo_filtered_creatives,
                selected_age=client_age,
                selected_gender=client_gender
            )
            st.altair_chart(cpm_eff_chart, use_container_width=True, theme="streamlit")

        st.subheader(f"Inspect Active Ad Creatives for [{client_age} | {client_gender}]")
        st.markdown("Review the actual political ad creatives and transparency disclosure links to evaluate messaging content:")

        display_cols = ["ad_id", "advertiser_name", "ad_type", "platform", "spend_usd_est", "impressions_est", "duration_days", "ad_url"]
        available_cols = [c for c in display_cols if c in demo_filtered_creatives.columns]
        sample_creatives = demo_filtered_creatives[available_cols].head(25).copy()

        st.dataframe(
            sample_creatives,
            column_config={
                "ad_url": st.column_config.LinkColumn("Ad Transparency URL", display_text="View Ad Content ↗"),
                "spend_usd_est": st.column_config.NumberColumn("Est. Spend ($)", format="$%.2f"),
                "impressions_est": st.column_config.NumberColumn("Est. Impressions", format="%d"),
                "duration_days": st.column_config.NumberColumn("Days Active", format="%d days"),
                "advertiser_name": "Sponsoring PAC / Campaign",
                "ad_type": "Ad Format",
                "platform": "Platform"
            },
            use_container_width=True,
            hide_index=True
        )

    # -----------------------------------------------------------
    # TAB 3: Regional Competitor Spend & NC County Heatmap
    # -----------------------------------------------------------
    with tab3:
        st.markdown(
            """<div class="info-box">
                <strong>NC Regional & County Strategy:</strong> Tracking political ad expenditure across North Carolina's 
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
                    "NC County Spend Heatmap (Ranked Intensity)",
                    "NC County Geographic Heatmap (Choropleth Map)",
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

        if geo_chart_choice == "NC County Spend Heatmap (Ranked Intensity)":
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

            county_heatmap = create_nc_county_heatmap_chart(df_county, metric_label=geo_metric_choice)
            st.altair_chart(county_heatmap, use_container_width=True, theme="streamlit")

        elif geo_chart_choice == "NC County Geographic Heatmap (Choropleth Map)":
            st.markdown("Geographic distribution of advertising expenditures across North Carolina counties:")
            choropleth_map = create_nc_county_choropleth_chart(df_county, metric_label=geo_metric_choice)
            st.altair_chart(choropleth_map, use_container_width=True, theme="streamlit")

        elif geo_chart_choice == "NC Media Market (DMA) Intensity Ranking":
            dma_chart = create_nc_dma_ranking_chart(cleaned_geo, metric_label=geo_metric_choice)
            st.altair_chart(dma_chart, use_container_width=True, theme="streamlit")

        elif geo_chart_choice == "Competitor PAC Breakdown by NC Market":
            breakdown_chart = create_nc_advertiser_breakdown_chart(cleaned_geo, metric_label=geo_metric_choice)
            st.altair_chart(breakdown_chart, use_container_width=True, theme="streamlit")

        else:
            share_chart = create_nc_market_share_chart(cleaned_geo)
            st.altair_chart(share_chart, use_container_width=True, theme="streamlit")

        with st.expander("📍 View North Carolina County & Market Spending Details"):
            exp_tab1, exp_tab2 = st.tabs(["🏛️ NC County Spending Ledger", "📺 NC Media Market Breakdown"])
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
                    use_container_width=True,
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
                    use_container_width=True
                )

    # -----------------------------------------------------------
    # TAB 4: Platform Performance & Pacing (NC)
    # -----------------------------------------------------------
    with tab4:
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
            st.info("Pacing graphs reflect investment trajectory in North Carolina up to the election.")

        if pace_view_choice in ["Weekly Expenditure Pace", "Cumulative Spend Trajectory"]:
            trajectory_chart = create_nc_spend_trajectory_chart(cleaned_weekly, view_mode=pace_view_choice)
            st.altair_chart(trajectory_chart, use_container_width=True, theme="streamlit")
        elif pace_view_choice == "Platform Allocation (Google vs. Meta in NC)":
            comp_chart = create_nc_platform_comparison_chart(filtered_df)
            st.altair_chart(comp_chart, use_container_width=True, theme="streamlit")
        else:
            format_chart = create_nc_format_efficiency_chart(filtered_df)
            st.altair_chart(format_chart, use_container_width=True, theme="streamlit")

    # -----------------------------------------------------------
    # TAB 5: Key Dataset Facts & Methodology
    # -----------------------------------------------------------
    with tab5:
        st.markdown("### 📋 Key Facts About the North Carolina Political Ads Dataset")

        f1, f2 = st.columns(2)
        with f1:
            st.markdown("""
            #### 1. Geographic Scope: North Carolina Focus
            * **Target Media Markets (DMAs):** Analysis is strictly bounded to North Carolina's 6 designated media markets:
              * *Charlotte DMA* (Mecklenburg, Union, Gaston, Cabarrus)
              * *Raleigh-Durham-Fayetteville DMA* (Wake, Durham, Cumberland, Orange)
              * *Greensboro-High Point-Winston-Salem DMA* (Piedmont Triad: Guilford, Forsyth)
              * *Greenville-New Bern-Washington DMA* (Eastern NC Coastal Plain)
              * *Wilmington DMA* (New Hanover, Brunswick, Pender)
              * *Asheville DMA* (Western NC Mountains)
            * **Exclusion of Non-NC Data:** Campaigns and impressions outside North Carolina are strictly filtered out.
            """)

            st.markdown("""
            #### 2. Currency Standardization
            * **Non-USD Currency Scrubbing:** Any multi-currency columns from international transparency tables (`_eur`, `_gbp`, `_cad`) are automatically dropped.
            * All figures represent normalized **$ USD**.
            """)

        with f2:
            st.markdown("""
            #### 3. Demographic Gap Discovery
            * **Delimited Array Explosion:** Political ads targeting multiple age cohorts (`"18-24, 25-34"`) are exploded into discrete rows.
            * **Alert Mechanism:** Cohorts with the lowest impression penetration among North Carolina voters are highlighted in **red** to pinpoint under-served groups needing voter mobilization.
            """)

            st.markdown("""
            #### 4. Range Bucket Estimations
            * Impressions reported as ranges (e.g. `10k-25k`, `>1M`) are converted into numerical bounds using regex and midpoint estimation.
            * Spend ranges with open-ended tops are conservatively imputed (`min * 1.5`).
            """)


if __name__ == "__main__":
    main()
