"""
Creative & Ad Content Charts - North Carolina Focus
Focuses on Targeted Ad Content & Format Intelligence:
Allows campaign clients to select specific voter age groups and gender segments
to inspect what types of ads (Video, Image, Text) are shown and what content applies best.
"""

from __future__ import annotations

import altair as alt
import pandas as pd


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


def filter_creatives_by_demographic(
    df: pd.DataFrame,
    selected_age: str = "All Ages",
    selected_gender: str = "All Genders"
) -> pd.DataFrame:
    """Filters creative records by target age cohort and gender segment."""
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


def create_demographic_format_distribution_chart(
    df_demographic_creatives: pd.DataFrame,
    selected_age: str = "All Ages",
    selected_gender: str = "All Genders",
    metric_label: str = "Estimated Spend ($ USD)"
) -> alt.Chart:
    """
    Visualizes the ad format breakdown (Video, Image, Text) delivered to the chosen age & gender group.
    """
    if df_demographic_creatives.empty or "ad_type" not in df_demographic_creatives.columns:
        return alt.Chart(pd.DataFrame({"msg": [f"No ad creatives found for {selected_age} / {selected_gender}"]})).mark_text().encode(text="msg:N")

    cfg = METRIC_CONFIG.get(metric_label, METRIC_CONFIG["Estimated Spend ($ USD)"])
    col = cfg["col"]

    if col == "ad_count":
        agg = (
            df_demographic_creatives.groupby("ad_type", as_index=False)
            .agg(ad_count=("ad_id", "count"))
            .sort_values(by=col, ascending=False)
        )
    else:
        agg = (
            df_demographic_creatives.groupby("ad_type", as_index=False)[col]
            .sum()
            .sort_values(by=col, ascending=False)
        )

    total_val = agg[col].sum()
    agg["share_pct"] = (agg[col] / total_val) * 100 if total_val > 0 else 0.0

    color_scale = alt.Scale(
        domain=["VIDEO", "IMAGE", "TEXT"],
        range=["#6366f1", "#10b981", "#f59e0b"]
    )

    chart = (
        alt.Chart(agg)
        .mark_bar(cornerRadiusEnd=6, size=35)
        .encode(
            x=alt.X("ad_type:N", title="Ad Creative Format", axis=alt.Axis(labelAngle=0)),
            y=alt.Y(f"{col}:Q", title=cfg["title"], axis=alt.Axis(format=cfg["format"], grid=True)),
            color=alt.Color("ad_type:N", scale=color_scale, legend=None),
            tooltip=[
                alt.Tooltip("ad_type:N", title="Creative Format"),
                alt.Tooltip(f"{col}:Q", title=metric_label, format=cfg["tooltip_format"]),
                alt.Tooltip("share_pct:Q", title="Format Share (%)", format=".1f")
            ]
        )
        .properties(
            title=alt.TitleParams(
                text=f"Ad Format Distribution for [{selected_age} | {selected_gender}] ({metric_label})",
                subtitle="Compares whether campaigns target this voter segment primarily via Video, Static Images, or Text",
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


def create_format_cpm_efficiency_chart(
    df_demographic_creatives: pd.DataFrame,
    selected_age: str = "All Ages",
    selected_gender: str = "All Genders"
) -> alt.Chart:
    """Calculates estimated CPM ($ / 1,000 impressions) by ad format for the chosen demographic."""
    if df_demographic_creatives.empty or "ad_type" not in df_demographic_creatives.columns:
        return alt.Chart(pd.DataFrame()).mark_text()

    agg = (
        df_demographic_creatives.groupby("ad_type", as_index=False)
        .agg(
            spend_usd_est=("spend_usd_est", "sum"),
            impressions_est=("impressions_est", "sum")
        )
    )
    agg = agg[agg["impressions_est"] > 0].copy()
    agg["cpm_est"] = (agg["spend_usd_est"] / agg["impressions_est"]) * 1000.0

    chart = (
        alt.Chart(agg)
        .mark_bar(cornerRadiusEnd=5, color="#38bdf8", size=30)
        .encode(
            x=alt.X("ad_type:N", title="Ad Creative Format", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("cpm_est:Q", title="Estimated CPM ($ / 1k Impressions)", axis=alt.Axis(format="$,.2f", grid=True)),
            tooltip=[
                alt.Tooltip("ad_type:N", title="Format"),
                alt.Tooltip("cpm_est:Q", title="Est. CPM", format="$,.2f"),
                alt.Tooltip("spend_usd_est:Q", title="Spend", format="$,.0f"),
                alt.Tooltip("impressions_est:Q", title="Impressions", format=",")
            ]
        )
        .properties(
            title=alt.TitleParams(
                text=f"Estimated Delivery Cost (CPM) for [{selected_age} | {selected_gender}]",
                subtitle="Identifies which ad format delivers impressions most cost-effectively to this voter group",
                fontSize=14,
                subtitleFontSize=11,
                subtitleColor="#94a3b8"
            ),
            height=300
        )
    )

    text = (
        alt.Chart(agg)
        .mark_text(align="center", dy=-8, color="#e2e8f0", fontSize=11)
        .encode(
            x=alt.X("ad_type:N"),
            y=alt.Y("cpm_est:Q"),
            text=alt.Text("cpm_est:Q", format="$,.2f")
        )
    )

    return chart + text
