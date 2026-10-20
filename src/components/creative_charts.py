"""
Creative & Ad Content Charts - North Carolina Focus
Separated into two dedicated subsections:
1. Google Political Ads (BigQuery): Video vs. Image vs. Text spend, impressions, and CPM efficiency.
2. Meta Ad Library (Meta API): Empirical demographic format delivery, Video vs. Image adoption curves across age cohorts, and gender breakdown.
"""

from __future__ import annotations

import altair as alt
import pandas as pd

try:
    from src.data.preprocessor import check_gender_data_exists
except ModuleNotFoundError:
    try:
        from data.preprocessor import check_gender_data_exists
    except ModuleNotFoundError:
        def check_gender_data_exists(df: pd.DataFrame, col: str) -> bool:
            return False


METRIC_CONFIG = {
    "Estimated Spend ($ USD)": {
        "col": "spend_usd_est",
        "format": "$,~s",
        "tooltip_format": "$,.2f",
        "title": "Estimated Spend ($ USD)"
    },
    "Estimated Impressions": {
        "col": "impressions_est",
        "format": "~s",
        "tooltip_format": ",",
        "title": "Estimated Impressions"
    },
    "Number of Ad Creatives": {
        "col": "ad_count",
        "format": "~s",
        "tooltip_format": ",",
        "title": "Number of Ad Creatives"
    }
}

META_METRIC_CONFIG = {
    "Delivered Impressions": {
        "col": "demographic_impressions",
        "format": "~s",
        "tooltip_format": ",",
        "title": "Delivered Impressions"
    },
    "Delivered Spend ($ USD)": {
        "col": "demographic_spend_usd",
        "format": "$,~s",
        "tooltip_format": "$,.2f",
        "title": "Delivered Spend ($ USD)"
    },
    "Number of Ad Creatives": {
        "col": "ad_count",
        "format": "~s",
        "tooltip_format": ",",
        "title": "Number of Ad Creatives"
    }
}


# ==============================================================================
# 1. GOOGLE POLITICAL ADS (BIGQUERY) FUNCTIONS
# ==============================================================================

def filter_google_creatives(
    df: pd.DataFrame,
    selected_age: str = "All Ages",
    selected_gender: str = "All Genders"
) -> pd.DataFrame:
    """Filters Google BigQuery creative records by target age cohort and gender segment."""
    if df.empty:
        return df

    filtered = df.copy()

    if selected_age != "All Ages" and "age_targeting" in filtered.columns:
        filtered = filtered[filtered["age_targeting"].astype(str).str.contains(selected_age, case=False, na=False)]

    if selected_gender != "All Genders" and "gender_targeting" in filtered.columns:
        if selected_gender == "Female":
            filtered = filtered[filtered["gender_targeting"].astype(str).str.contains("Female", case=False, na=False)]
        elif selected_gender == "Male":
            filtered = filtered[filtered["gender_targeting"].astype(str).str.contains("Male", case=False, na=False)]
        elif selected_gender == "Broad / Untargeted":
            filtered = filtered[filtered["gender_targeting"].astype(str).str.contains("Not targeted", case=False, na=False)]

    return filtered


def create_google_format_distribution_chart(
    df_google: pd.DataFrame,
    metric_label: str = "Estimated Spend ($ USD)",
    selected_age: str = "All Ages",
    selected_gender: str = "All Genders"
) -> alt.Chart:
    """
    Visualizes Google Political Ads format distribution (Video, Image, Text) from BigQuery.
    """
    if df_google.empty or "ad_type" not in df_google.columns:
        return alt.Chart(pd.DataFrame({"msg": [f"No Google ad creatives found for {selected_age} / {selected_gender}"]})).mark_text().encode(text="msg:N")

    cfg = METRIC_CONFIG.get(metric_label, METRIC_CONFIG["Estimated Spend ($ USD)"])
    col = cfg["col"]

    if col == "ad_count":
        agg = (
            df_google.groupby("ad_type", as_index=False)
            .agg(ad_count=("ad_id", "count"))
            .sort_values(by=col, ascending=False)
        )
    else:
        agg = (
            df_google.groupby("ad_type", as_index=False)[col]
            .sum()
            .sort_values(by=col, ascending=False)
        )

    total_val = agg[col].sum()
    agg["share_pct"] = (agg[col] / total_val) * 100 if total_val > 0 else 0.0
    max_val = agg[col].max() if not agg.empty else 1.0

    color_scale = alt.Scale(
        domain=["VIDEO", "IMAGE", "TEXT"],
        range=["#4285F4", "#34A853", "#FBBC05"]  # Google palette
    )

    chart = (
        alt.Chart(agg)
        .mark_bar(cornerRadiusEnd=6, size=35)
        .encode(
            x=alt.X("ad_type:N", title="Google Ad Creative Format", axis=alt.Axis(labelAngle=0, labelPadding=6)),
            y=alt.Y(
                f"{col}:Q",
                title=cfg["title"],
                scale=alt.Scale(domainMax=max_val * 1.16),
                axis=alt.Axis(format=cfg["format"], grid=True, titlePadding=10)
            ),
            color=alt.Color("ad_type:N", scale=color_scale, legend=None),
            tooltip=[
                alt.Tooltip("ad_type:N", title="Google Format"),
                alt.Tooltip(f"{col}:Q", title=metric_label, format=cfg["tooltip_format"]),
                alt.Tooltip("share_pct:Q", title="Format Share (%)", format=".1f")
            ]
        )
        .properties(
            title=alt.TitleParams(
                text=f"Google Ad Format Breakdown for [{selected_age} | {selected_gender}] ({metric_label})",
                subtitle="Analyzes YouTube Video vs. Display Images vs. Search Text in BigQuery data (2024–Current)",
                fontSize=14,
                subtitleFontSize=11,
                subtitleColor="#94a3b8"
            ),
            height=300
        )
    )

    text = (
        alt.Chart(agg)
        .mark_text(align="center", dy=-8, color="#cbd5e1", fontSize=12, fontWeight="bold")
        .encode(
            x=alt.X("ad_type:N"),
            y=alt.Y(f"{col}:Q"),
            text=alt.Text("share_pct:Q", format=".1f")
        )
    )

    return chart + text


def create_google_format_cpm_chart(
    df_google: pd.DataFrame,
    selected_age: str = "All Ages",
    selected_gender: str = "All Genders"
) -> alt.Chart:
    """Calculates estimated CPM ($ / 1,000 impressions) by ad format on Google."""
    if df_google.empty or "ad_type" not in df_google.columns:
        return alt.Chart(pd.DataFrame()).mark_text()

    agg = (
        df_google.groupby("ad_type", as_index=False)
        .agg(
            spend_usd_est=("spend_usd_est", "sum"),
            impressions_est=("impressions_est", "sum")
        )
    )
    agg = agg[agg["impressions_est"] > 0].copy()
    agg["cpm_est"] = (agg["spend_usd_est"] / agg["impressions_est"]) * 1000.0
    max_cpm = agg["cpm_est"].max() if not agg.empty else 1.0

    color_scale = alt.Scale(
        domain=["VIDEO", "IMAGE", "TEXT"],
        range=["#4285F4", "#34A853", "#FBBC05"]
    )

    chart = (
        alt.Chart(agg)
        .mark_bar(cornerRadiusEnd=5, size=30)
        .encode(
            x=alt.X("ad_type:N", title="Google Ad Creative Format", axis=alt.Axis(labelAngle=0, labelPadding=6)),
            y=alt.Y(
                "cpm_est:Q",
                title="Estimated CPM ($ / 1k Impressions)",
                scale=alt.Scale(domainMax=max_cpm * 1.16),
                axis=alt.Axis(format="$,.2f", grid=True, titlePadding=10)
            ),
            color=alt.Color("ad_type:N", scale=color_scale, legend=None),
            tooltip=[
                alt.Tooltip("ad_type:N", title="Format"),
                alt.Tooltip("cpm_est:Q", title="Est. CPM", format="$,.2f"),
                alt.Tooltip("spend_usd_est:Q", title="Spend", format="$,.0f"),
                alt.Tooltip("impressions_est:Q", title="Impressions", format=",")
            ]
        )
        .properties(
            title=alt.TitleParams(
                text=f"Google Format Delivery Efficiency (CPM) for [{selected_age} | {selected_gender}]",
                subtitle="Identifies which Google format (YouTube Video vs. Display vs. Search) delivers impressions most cost-effectively",
                fontSize=14,
                subtitleFontSize=11,
                subtitleColor="#94a3b8"
            ),
            height=300
        )
    )

    text = (
        alt.Chart(agg)
        .mark_text(align="center", dy=-8, color="#e2e8f0", fontSize=11, fontWeight="bold")
        .encode(
            x=alt.X("ad_type:N"),
            y=alt.Y("cpm_est:Q"),
            text=alt.Text("cpm_est:Q", format="$,.2f")
        )
    )

    return chart + text


def generate_google_creative_insights(df_google: pd.DataFrame) -> list[str]:
    """Generates automated strategic campaign insights for Google Political Ads creatives."""
    insights: list[str] = []
    if df_google.empty or "ad_type" not in df_google.columns:
        return ["Insufficient Google BigQuery creative records to compute automated insights."]

    total_spend = df_google["spend_usd_est"].sum()
    format_spend = df_google.groupby("ad_type")["spend_usd_est"].sum()
    format_imps = df_google.groupby("ad_type")["impressions_est"].sum()

    video_spend = format_spend.get("VIDEO", 0.0)
    video_share = (video_spend / total_spend * 100) if total_spend > 0 else 0.0

    image_spend = format_spend.get("IMAGE", 0.0)
    image_share = (image_spend / total_spend * 100) if total_spend > 0 else 0.0

    text_spend = format_spend.get("TEXT", 0.0)
    text_share = (text_spend / total_spend * 100) if total_spend > 0 else 0.0

    insights.append(
        f"**Google Video Allocation Dominance:** YouTube Video ads account for **{video_share:.1f}% (${video_spend:,.0f})** "
        f"of all tracked Google political advertising dollars in North Carolina, prioritizing high-recall audiovisual storytelling."
    )

    # CPM Comparison
    video_cpm = (video_spend / format_imps.get("VIDEO", 1)) * 1000 if format_imps.get("VIDEO", 0) > 0 else 0.0
    image_cpm = (image_spend / format_imps.get("IMAGE", 1)) * 1000 if format_imps.get("IMAGE", 0) > 0 else 0.0

    if video_cpm > 0 and image_cpm > 0:
        if video_cpm > image_cpm:
            insights.append(
                f"**CPM Cost Premium:** YouTube Video commands a higher CPM (**${video_cpm:.2f}**) compared to Display Images (**${image_cpm:.2f}**). "
                f"While video delivers higher persuasion value, static banners offer a lower-cost frequency driver for name ID."
            )
        else:
            insights.append(
                f"**Video Efficiency Opportunity:** YouTube Video ads deliver at an attractive CPM of **${video_cpm:.2f}**, "
                f"providing competitive cost efficiency compared to display static creative inventory."
            )

    insights.append(
        f"**Tactical Mix Recommendation:** Maintain a **70/20/10 budget split** on Google (70% YouTube Non-Skippable Video for persuasion, "
        f"20% Display for turnout mobilization, and 10% Search Text Ads for rapid-response news spikes)."
    )

    return insights


# ==============================================================================
# 2. META AD LIBRARY (META API) FUNCTIONS
# ==============================================================================

def filter_meta_demographics(
    df_meta_demo: pd.DataFrame,
    selected_age: str = "All Ages",
    selected_gender: str = "All Genders"
) -> pd.DataFrame:
    """Filters Meta demographic audience delivery data by age cohort and gender."""
    if df_meta_demo.empty:
        return df_meta_demo

    filtered = df_meta_demo.copy()

    if selected_age != "All Ages" and "age_group" in filtered.columns:
        filtered = filtered[filtered["age_group"].astype(str) == selected_age]

    if selected_gender != "All Genders" and "gender" in filtered.columns:
        filtered = filtered[filtered["gender"].astype(str).str.lower() == selected_gender.lower()]

    return filtered


def create_meta_demographic_format_chart(
    df_meta_demo_filtered: pd.DataFrame,
    metric_label: str = "Delivered Impressions",
    selected_age: str = "All Ages",
    selected_gender: str = "All Genders"
) -> alt.Chart:
    """
    Visualizes ad formats (Video, Image, Text) delivered to the chosen age & gender group on Meta.
    Leverages empirical demographic_distribution data from the Meta Graph API.
    """
    if df_meta_demo_filtered.empty or "ad_type" not in df_meta_demo_filtered.columns:
        return alt.Chart(pd.DataFrame({"msg": [f"No Meta ad distribution data found for {selected_age} / {selected_gender}"]})).mark_text().encode(text="msg:N")

    cfg = META_METRIC_CONFIG.get(metric_label, META_METRIC_CONFIG["Delivered Impressions"])
    col = cfg["col"]

    if col == "ad_count":
        agg = (
            df_meta_demo_filtered.groupby("ad_type", as_index=False)
            .agg(ad_count=("ad_id", "nunique"))
            .sort_values(by=col, ascending=False)
        )
    else:
        agg = (
            df_meta_demo_filtered.groupby("ad_type", as_index=False)[col]
            .sum()
            .sort_values(by=col, ascending=False)
        )

    total_val = agg[col].sum()
    agg["share_pct"] = (agg[col] / total_val) * 100 if total_val > 0 else 0.0
    max_val = agg[col].max() if not agg.empty else 1.0

    color_scale = alt.Scale(
        domain=["VIDEO", "IMAGE", "TEXT"],
        range=["#6366f1", "#0668E1", "#f59e0b"]  # Meta indigo / blue / amber
    )

    chart = (
        alt.Chart(agg)
        .mark_bar(cornerRadiusEnd=6, size=35)
        .encode(
            x=alt.X("ad_type:N", title="Meta Ad Creative Format", axis=alt.Axis(labelAngle=0, labelPadding=6)),
            y=alt.Y(
                f"{col}:Q",
                title=cfg["title"],
                scale=alt.Scale(domainMax=max_val * 1.16),
                axis=alt.Axis(format=cfg["format"], grid=True, titlePadding=10)
            ),
            color=alt.Color("ad_type:N", scale=color_scale, legend=None),
            tooltip=[
                alt.Tooltip("ad_type:N", title="Meta Format"),
                alt.Tooltip(f"{col}:Q", title=metric_label, format=cfg["tooltip_format"]),
                alt.Tooltip("share_pct:Q", title="Delivery Share (%)", format=".1f")
            ]
        )
        .properties(
            title=alt.TitleParams(
                text=f"Meta Format Delivery to [{selected_age} | {selected_gender}] ({metric_label})",
                subtitle="Delivered reach based on Meta Graph API demographic_distribution (2024–Current)",
                fontSize=14,
                subtitleFontSize=11,
                subtitleColor="#94a3b8"
            ),
            height=300
        )
    )

    text = (
        alt.Chart(agg)
        .mark_text(align="center", dy=-8, color="#cbd5e1", fontSize=12, fontWeight="bold")
        .encode(
            x=alt.X("ad_type:N"),
            y=alt.Y(f"{col}:Q"),
            text=alt.Text("share_pct:Q", format=".1f")
        )
    )

    return chart + text


def create_meta_format_cpm_chart(
    df_meta_demo_filtered: pd.DataFrame,
    selected_age: str = "All Ages",
    selected_gender: str = "All Genders"
) -> alt.Chart:
    """Calculates estimated CPM ($ / 1,000 impressions) by ad format on Meta."""
    if df_meta_demo_filtered.empty or "ad_type" not in df_meta_demo_filtered.columns:
        return alt.Chart(pd.DataFrame()).mark_text()

    agg = (
        df_meta_demo_filtered.groupby("ad_type", as_index=False)
        .agg(
            demographic_spend_usd=("demographic_spend_usd", "sum"),
            demographic_impressions=("demographic_impressions", "sum")
        )
    )
    agg = agg[agg["demographic_impressions"] > 0].copy()
    agg["cpm_est"] = (agg["demographic_spend_usd"] / agg["demographic_impressions"]) * 1000.0
    max_cpm = agg["cpm_est"].max() if not agg.empty else 1.0

    color_scale = alt.Scale(
        domain=["VIDEO", "IMAGE", "TEXT"],
        range=["#6366f1", "#0668E1", "#f59e0b"]
    )

    chart = (
        alt.Chart(agg)
        .mark_bar(cornerRadiusEnd=5, size=30)
        .encode(
            x=alt.X("ad_type:N", title="Meta Ad Creative Format", axis=alt.Axis(labelAngle=0, labelPadding=6)),
            y=alt.Y(
                "cpm_est:Q",
                title="Delivered CPM ($ / 1k Impressions)",
                scale=alt.Scale(domainMax=max_cpm * 1.16),
                axis=alt.Axis(format="$,.2f", grid=True, titlePadding=10)
            ),
            color=alt.Color("ad_type:N", scale=color_scale, legend=None),
            tooltip=[
                alt.Tooltip("ad_type:N", title="Format"),
                alt.Tooltip("cpm_est:Q", title="Est. Delivered CPM", format="$,.2f"),
                alt.Tooltip("demographic_spend_usd:Q", title="Delivered Spend", format="$,.2f"),
                alt.Tooltip("demographic_impressions:Q", title="Delivered Impressions", format=",")
            ]
        )
        .properties(
            title=alt.TitleParams(
                text=f"Meta CPM Delivery Cost for [{selected_age} | {selected_gender}]",
                subtitle="Calculates delivery cost efficiency for Video vs. Image ads reaching this voter cohort",
                fontSize=14,
                subtitleFontSize=11,
                subtitleColor="#94a3b8"
            ),
            height=300
        )
    )

    text = (
        alt.Chart(agg)
        .mark_text(align="center", dy=-8, color="#e2e8f0", fontSize=11, fontWeight="bold")
        .encode(
            x=alt.X("ad_type:N"),
            y=alt.Y("cpm_est:Q"),
            text=alt.Text("cpm_est:Q", format="$,.2f")
        )
    )

    return chart + text


def create_video_adoption_by_demographic_chart(df_meta_processed: pd.DataFrame) -> alt.Chart:
    """
    Visualizes Video vs. Image vs. Text ad format breakdown across ALL age demographics in North Carolina,
    leveraging Facebook / Meta Ad Library API demographic distribution data.
    Directly reveals which age cohorts receive the highest proportion of video advertising.
    """
    VALID_AGE_COHORTS = ["18-24", "25-34", "35-44", "45-54", "55-64", "≥65"]
    clean_meta = df_meta_processed[
        df_meta_processed["age_group"].astype(str).str.strip().isin(VALID_AGE_COHORTS)
    ].copy()
    if clean_meta.empty:
        return alt.Chart(pd.DataFrame()).mark_text()

    agg = (
        clean_meta.groupby(["age_group", "ad_type"], as_index=False)["demographic_impressions"]
        .sum()
    )

    total_per_age = agg.groupby("age_group")["demographic_impressions"].transform("sum")
    agg["format_share_pct"] = (agg["demographic_impressions"] / total_per_age) * 100

    color_scale = alt.Scale(
        domain=["VIDEO", "IMAGE", "TEXT"],
        range=["#6366f1", "#0668E1", "#f59e0b"]
    )

    chart = (
        alt.Chart(agg)
        .mark_bar(cornerRadiusEnd=3)
        .encode(
            x=alt.X("format_share_pct:Q", stack="normalize", title="Format Impression Share (%)", axis=alt.Axis(format="%", titlePadding=10)),
            y=alt.Y("age_group:N", sort=VALID_AGE_COHORTS, title="NC Voter Age Cohort", axis=alt.Axis(labelPadding=6, titlePadding=10)),
            color=alt.Color("ad_type:N", scale=color_scale, legend=alt.Legend(title="Ad Format (Meta API)", orient="bottom", titlePadding=8)),
            tooltip=[
                alt.Tooltip("age_group:N", title="Age Cohort"),
                alt.Tooltip("ad_type:N", title="Format"),
                alt.Tooltip("format_share_pct:Q", title="Share of Audience", format=".1f"),
                alt.Tooltip("demographic_impressions:Q", title="Delivered Impressions", format=",.0f")
            ]
        )
        .properties(
            title=alt.TitleParams(
                text="Meta Video vs. Image Delivery by NC Voter Age Cohort",
                subtitle="Compares the proportion of Video ads delivered to younger voters vs. older demographics on Meta",
                fontSize=14,
                subtitleFontSize=11,
                subtitleColor="#94a3b8"
            ),
            height=320
        )
    )
    return chart


def create_gender_video_breakdown_chart(df_meta_processed: pd.DataFrame) -> alt.Chart | None:
    """
    Visualizes ad format breakdown delivered to Female vs. Male voters in NC using Meta API data.
    Uses grouped bar offset (`xOffset='ad_type:N'`) so formats are cleanly aligned side-by-side
    without overlapping or column facet collisions.
    Returns None if gender data does not exist in the dataset.
    """
    if not check_gender_data_exists(df_meta_processed, "gender"):
        return None

    clean_gender_df = df_meta_processed[
        df_meta_processed["gender"].astype(str).str.lower().isin(["female", "male"])
    ].copy()
    clean_gender_df["gender_label"] = clean_gender_df["gender"].astype(str).str.capitalize()

    agg = (
        clean_gender_df.groupby(["gender_label", "ad_type"], as_index=False)["demographic_impressions"]
        .sum()
    )

    total_per_gender = agg.groupby("gender_label")["demographic_impressions"].transform("sum")
    agg["share_pct"] = (agg["demographic_impressions"] / total_per_gender) * 100

    color_scale = alt.Scale(
        domain=["VIDEO", "IMAGE", "TEXT"],
        range=["#6366f1", "#0668E1", "#f59e0b"]
    )

    chart = (
        alt.Chart(agg)
        .mark_bar(cornerRadiusEnd=4, size=24)
        .encode(
            x=alt.X("gender_label:N", title="NC Voter Gender Segment", axis=alt.Axis(labelAngle=0, labelPadding=6, titlePadding=10)),
            xOffset="ad_type:N",
            y=alt.Y("share_pct:Q", title="Delivery Share (%)", scale=alt.Scale(domain=[0, 100]), axis=alt.Axis(format=".0f", grid=True, titlePadding=10)),
            color=alt.Color("ad_type:N", scale=color_scale, legend=alt.Legend(title="Ad Format (Meta API)", orient="bottom", titlePadding=8)),
            tooltip=[
                alt.Tooltip("gender_label:N", title="Gender"),
                alt.Tooltip("ad_type:N", title="Format"),
                alt.Tooltip("share_pct:Q", title="Share (%)", format=".1f"),
                alt.Tooltip("demographic_impressions:Q", title="Impressions", format=",.0f")
            ]
        )
        .properties(
            title=alt.TitleParams(
                text="Meta Ad Format Distribution by Gender (Meta API)",
                subtitle="Video vs. Static Image penetration compared side-by-side between Female and Male voters",
                fontSize=14,
                subtitleFontSize=11,
                subtitleColor="#94a3b8"
            ),
            height=320
        )
    )
    return chart



def generate_meta_creative_insights(df_meta_demo: pd.DataFrame) -> list[str]:
    """Generates automated strategic campaign insights for Meta ad creatives."""
    insights: list[str] = []
    if df_meta_demo.empty:
        return ["Insufficient Meta demographic delivery data to compute automated insights."]

    total_imps = df_meta_demo["demographic_impressions"].sum()
    video_imps = df_meta_demo[df_meta_demo["ad_type"] == "VIDEO"]["demographic_impressions"].sum()
    video_pct = (video_imps / total_imps * 100) if total_imps > 0 else 0.0

    insights.append(
        f"**High Video Saturation on Meta:** Video creatives generate **{video_pct:.1f}%** of all empirical "
        f"impressions delivered across Facebook and Instagram in North Carolina, outperforming static images."
    )

    # Youth video adoption
    youth_df = df_meta_demo[df_meta_demo["age_group"].isin(["18-24", "25-34"])]
    if not youth_df.empty:
        youth_total = youth_df["demographic_impressions"].sum()
        youth_video = youth_df[youth_df["ad_type"] == "VIDEO"]["demographic_impressions"].sum()
        youth_video_pct = (youth_video / youth_total * 100) if youth_total > 0 else 0.0
        insights.append(
            f"**Youth Video Consumption Spike:** Among North Carolina voters aged 18–34, Video ads account for "
            f"**{youth_video_pct:.1f}%** of delivered impressions, establishing short-form video (Reels/Stories) as the primary battleground for young voters."
        )

    # Gender breakdown
    female_df = df_meta_demo[df_meta_demo["gender"] == "female"]
    male_df = df_meta_demo[df_meta_demo["gender"] == "male"]

    if not female_df.empty and not male_df.empty:
        f_video_pct = (female_df[female_df["ad_type"] == "VIDEO"]["demographic_impressions"].sum() / female_df["demographic_impressions"].sum() * 100) if female_df["demographic_impressions"].sum() > 0 else 0.0
        m_video_pct = (male_df[male_df["ad_type"] == "VIDEO"]["demographic_impressions"].sum() / male_df["demographic_impressions"].sum() * 100) if male_df["demographic_impressions"].sum() > 0 else 0.0

        insights.append(
            f"**Gender Creative Dynamics:** Delivered video penetration is **{f_video_pct:.1f}% for Female voters** and **{m_video_pct:.1f}% for Male voters**. "
            f"Deploy video testimonials for women suburban voters in Wake/Mecklenburg and rapid-pace issue clips for men."
        )

    insights.append(
        "**Strategic Budget Directive:** Allocate at least 65% of Meta creative production to 15-second vertical video assets (9:16) "
        "optimized for mobile-first consumption with open captions."
    )

    return insights


# ==============================================================================
# 3. BACKWARD-COMPATIBLE ALIASES
# ==============================================================================

filter_creatives_by_demographic = filter_google_creatives
create_demographic_format_distribution_chart = create_google_format_distribution_chart
create_format_cpm_efficiency_chart = create_google_format_cpm_chart
