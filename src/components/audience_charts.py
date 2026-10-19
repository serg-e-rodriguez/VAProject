"""
Audience & Demographic Charts - North Carolina Focus
Focuses on Demographic Opportunity & Gap Analysis:
Identifying which demographic groups of North Carolina voters are viewing political ads the least.
Supports dynamic metric toggling via drop-down menu selections.
"""

from __future__ import annotations

import altair as alt
import pandas as pd


METRIC_CONFIG = {
    "Estimated Impressions": {
        "col": "impressions_est",
        "format": "~s",
        "tooltip_format": ",",
        "prefix": "",
        "title": "Total Estimated Impressions"
    },
    "Estimated Spend ($ USD)": {
        "col": "spend_usd_est",
        "format": "$,~s",
        "tooltip_format": "$,.2f",
        "prefix": "$",
        "title": "Total Estimated Spend ($ USD)"
    },
    "Number of Ad Creatives": {
        "col": "ad_count",
        "format": "~s",
        "tooltip_format": ",",
        "prefix": "",
        "title": "Number of Ad Creatives"
    }
}


def create_nc_demographic_gap_chart(
    df_demographics: pd.DataFrame,
    metric_label: str = "Estimated Impressions"
) -> alt.Chart:
    """
    Ranks NC voter age cohorts by the selected metric (Impressions, Spend, or Ad Count).
    Highlights under-served cohorts viewing the least ads with alert coloring.
    """
    if df_demographics.empty or "age_targeting" not in df_demographics.columns:
        return alt.Chart(pd.DataFrame({"msg": ["No NC demographic data available"]})).mark_text().encode(text="msg:N")

    cfg = METRIC_CONFIG.get(metric_label, METRIC_CONFIG["Estimated Impressions"])
    col = cfg["col"]

    if col == "ad_count":
        agg = (
            df_demographics.groupby("age_targeting", as_index=False)
            .agg(ad_count=("ad_id", "count"))
            .sort_values(by=col, ascending=True)
        )
    else:
        agg = (
            df_demographics.groupby("age_targeting", as_index=False)[col]
            .sum()
            .sort_values(by=col, ascending=True)
        )

    total_val = agg[col].sum()
    agg["share_pct"] = (agg[col] / total_val) * 100 if total_val > 0 else 0.0

    # Flag bottom 2 cohorts as "Outreach Priority (Under-served in NC)"
    agg["reach_tier"] = "Standard / Reached"
    if len(agg) > 0:
        bottom_indices = agg.index[:min(2, len(agg))]
        agg.loc[bottom_indices, "reach_tier"] = "🚨 High Priority Outreach (Least Viewed)"

    highlight = alt.selection_point(fields=["reach_tier"], bind="legend")

    chart = (
        alt.Chart(agg)
        .mark_bar(cornerRadiusEnd=6, size=24)
        .encode(
            x=alt.X(
                f"{col}:Q",
                title=f"NC Voters: {cfg['title']}",
                axis=alt.Axis(format=cfg["format"], grid=True)
            ),
            y=alt.Y(
                "age_targeting:N",
                sort="x",
                title="Voter Age Cohort"
            ),
            color=alt.Color(
                "reach_tier:N",
                scale=alt.Scale(
                    domain=["🚨 High Priority Outreach (Least Viewed)", "Standard / Reached"],
                    range=["#ef4444", "#3b82f6"]
                ),
                legend=alt.Legend(title="Outreach Status", orient="top")
            ),
            opacity=alt.condition(highlight, alt.value(1.0), alt.value(0.35)),
            tooltip=[
                alt.Tooltip("age_targeting:N", title="Age Cohort"),
                alt.Tooltip(f"{col}:Q", title=metric_label, format=cfg["tooltip_format"]),
                alt.Tooltip("share_pct:Q", title="Share of Total (%)", format=".1f"),
                alt.Tooltip("reach_tier:N", title="Campaign Action")
            ]
        )
        .add_params(highlight)
        .properties(
            title=alt.TitleParams(
                text=f"North Carolina Demographic Opportunity Gap ({metric_label})",
                subtitle="Age cohorts in red receive the least political ad delivery and represent critical voter mobilization opportunities",
                fontSize=15,
                subtitleFontSize=12,
                subtitleColor="#94a3b8"
            ),
            height=320
        )
    )

    text = (
        alt.Chart(agg)
        .mark_text(align="left", dx=6, color="#cbd5e1", fontSize=11, fontWeight="bold")
        .encode(
            x=alt.X(f"{col}:Q"),
            y=alt.Y("age_targeting:N", sort="x"),
            text=alt.Text("share_pct:Q", format=".1f")
        )
    )

    return chart + text


def create_nc_gender_breakdown_chart(
    df: pd.DataFrame,
    metric_label: str = "Estimated Impressions"
) -> alt.Chart:
    """Visualizes gender targeting distribution across North Carolina voters."""
    if df.empty or "gender_targeting" not in df.columns:
        return alt.Chart(pd.DataFrame()).mark_text()

    cfg = METRIC_CONFIG.get(metric_label, METRIC_CONFIG["Estimated Impressions"])
    col = cfg["col"]

    if col == "ad_count":
        agg = (
            df.groupby("gender_targeting", as_index=False)
            .agg(ad_count=("ad_id", "count"))
            .sort_values(by=col, ascending=False)
        )
    else:
        agg = (
            df.groupby("gender_targeting", as_index=False)[col]
            .sum()
            .sort_values(by=col, ascending=False)
        )

    chart = (
        alt.Chart(agg)
        .mark_arc(innerRadius=45, stroke="#1e293b", strokeWidth=2)
        .encode(
            theta=alt.Theta(f"{col}:Q", title=metric_label),
            color=alt.Color(
                "gender_targeting:N",
                scale=alt.Scale(
                    domain=["Female, Male", "Female", "Male", "Not targeted"],
                    range=["#8b5cf6", "#ec4899", "#06b6d4", "#64748b"]
                ),
                legend=alt.Legend(title="Gender Targeting", orient="right")
            ),
            tooltip=[
                alt.Tooltip("gender_targeting:N", title="Audience Segment"),
                alt.Tooltip(f"{col}:Q", title=metric_label, format=cfg["tooltip_format"])
            ]
        )
        .properties(
            title=alt.TitleParams(
                text=f"NC Gender Audience Breakdown ({metric_label})",
                subtitle="Distribution of political advertising delivery across gender groups",
                fontSize=14,
                subtitleFontSize=11,
                subtitleColor="#94a3b8"
            ),
            height=280
        )
    )
    return chart


def create_nc_cross_platform_demographic_chart(
    df_demographics: pd.DataFrame,
    metric_label: str = "Estimated Impressions"
) -> alt.Chart:
    """Compares demographic reach in North Carolina across Google and Meta."""
    if df_demographics.empty or "platform" not in df_demographics.columns:
        return alt.Chart(pd.DataFrame()).mark_text()

    cfg = METRIC_CONFIG.get(metric_label, METRIC_CONFIG["Estimated Impressions"])
    col = cfg["col"]

    if col == "ad_count":
        agg = (
            df_demographics.groupby(["age_targeting", "platform"], as_index=False)
            .agg(ad_count=("ad_id", "count"))
        )
    else:
        agg = (
            df_demographics.groupby(["age_targeting", "platform"], as_index=False)[col]
            .sum()
        )

    chart = (
        alt.Chart(agg)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("platform:N", title="Platform", axis=alt.Axis(labels=True, title=None)),
            y=alt.Y(f"{col}:Q", title=metric_label, axis=alt.Axis(format=cfg["format"])),
            color=alt.Color(
                "platform:N",
                scale=alt.Scale(domain=["Google", "Meta"], range=["#4285F4", "#0668E1"]),
                legend=alt.Legend(title="Platform", orient="top")
            ),
            column=alt.Column(
                "age_targeting:N",
                title="NC Voter Age Cohort",
                header=alt.Header(labelColor="#cbd5e1", titleColor="#e2e8f0")
            ),
            tooltip=[
                alt.Tooltip("age_targeting:N", title="Age Cohort"),
                alt.Tooltip("platform:N", title="Platform"),
                alt.Tooltip(f"{col}:Q", title=metric_label, format=cfg["tooltip_format"])
            ]
        )
        .properties(height=230)
    )
    return chart
