"""
Spend & Platform Performance Charts - North Carolina Focus
Pacing over time, platform comparison, and ad creative format efficiency.
Supports dynamic toggles via drop-down menus.
"""

from __future__ import annotations

import altair as alt
import pandas as pd


def create_nc_spend_trajectory_chart(
    df_weekly: pd.DataFrame,
    view_mode: str = "Weekly Expenditure Pace"
) -> alt.Chart:
    """
    Visualizes NC political advertising spend trajectory over time.
    Supports switching between weekly velocity and cumulative trajectory.
    Configured with clean bottom legend and axis padding to prevent clipping or collisions.
    """
    if df_weekly.empty or "week_start_date" not in df_weekly.columns:
        return alt.Chart(pd.DataFrame({"msg": ["No NC pacing data available"]})).mark_text().encode(text="msg:N")

    agg = (
        df_weekly.groupby(["week_start_date", "advertiser_name"], as_index=False)["spend_usd"]
        .sum()
        .sort_values(by="week_start_date")
    )

    if view_mode == "Cumulative Spend Trajectory":
        agg["spend_metric"] = agg.groupby("advertiser_name")["spend_usd"].cumsum()
        title_text = "Cumulative Political Ad Spend Trajectory in North Carolina"
        y_title = "Cumulative Spend ($ USD)"
    else:
        agg["spend_metric"] = agg["spend_usd"]
        title_text = "Weekly Political Ad Spend Velocity in North Carolina"
        y_title = "Weekly Spend ($ USD)"

    max_metric = agg["spend_metric"].max() if not agg.empty else 1.0

    brush = alt.selection_interval(encodings=["x"])

    chart = (
        alt.Chart(agg)
        .mark_line(point=alt.OverlayMarkDef(filled=True, size=28), strokeWidth=2.5)
        .encode(
            x=alt.X(
                "week_start_date:T",
                title="Campaign Week",
                axis=alt.Axis(format="%b %d, %Y", grid=True, titlePadding=10, labelPadding=6)
            ),
            y=alt.Y(
                "spend_metric:Q",
                title=y_title,
                scale=alt.Scale(domainMax=max_metric * 1.12),
                axis=alt.Axis(format="$,~s", grid=True, titlePadding=12)
            ),
            color=alt.Color(
                "advertiser_name:N",
                scale=alt.Scale(scheme="tableau10"),
                legend=alt.Legend(title="Competitor PAC / Campaign", orient="bottom", columns=2, titlePadding=8)
            ),
            tooltip=[
                alt.Tooltip("week_start_date:T", title="Week Of", format="%B %d, %Y"),
                alt.Tooltip("advertiser_name:N", title="Organization"),
                alt.Tooltip("spend_metric:Q", title=y_title, format="$,.2f")
            ]
        )
        .add_params(brush)
        .properties(
            title=alt.TitleParams(
                text=title_text,
                subtitle=f"{view_mode} across active political campaigns in NC (pan & zoom enabled)",
                fontSize=15,
                subtitleFontSize=12,
                subtitleColor="#94a3b8"
            ),
            height=340
        )
        .interactive()
    )
    return chart


def create_nc_format_efficiency_chart(df_creatives: pd.DataFrame) -> alt.Chart:
    """Analyzes creative ad formats (VIDEO, IMAGE, TEXT) in North Carolina with domain headroom."""
    if df_creatives.empty or "ad_type" not in df_creatives.columns:
        return alt.Chart(pd.DataFrame()).mark_text()

    agg = (
        df_creatives.groupby("ad_type", as_index=False)
        .agg(
            spend_usd_est=("spend_usd_est", "sum"),
            impressions_est=("impressions_est", "sum"),
            ad_count=("ad_id", "count")
        )
    )

    agg["cpm_est"] = (agg["spend_usd_est"] / agg["impressions_est"]) * 1000
    max_spend = agg["spend_usd_est"].max() if not agg.empty else 1.0

    base = alt.Chart(agg).encode(
        x=alt.X("ad_type:N", title="Ad Creative Format", axis=alt.Axis(labelAngle=0, labelPadding=6))
    )

    bar = base.mark_bar(cornerRadiusEnd=5, color="#10b981", size=32).encode(
        y=alt.Y(
            "spend_usd_est:Q",
            title="Total NC Spend ($ USD)",
            scale=alt.Scale(domainMax=max_spend * 1.16),
            axis=alt.Axis(format="$,~s", titlePadding=10)
        ),
        tooltip=[
            alt.Tooltip("ad_type:N", title="Format"),
            alt.Tooltip("spend_usd_est:Q", title="NC Spend", format="$,.2f"),
            alt.Tooltip("impressions_est:Q", title="NC Impressions", format=","),
            alt.Tooltip("cpm_est:Q", title="Est. CPM", format="$,.2f"),
            alt.Tooltip("ad_count:Q", title="Creatives Count", format=",")
        ]
    )

    text = base.mark_text(align="center", dy=-8, color="#cbd5e1", fontSize=11, fontWeight="bold").encode(
        y=alt.Y("spend_usd_est:Q"),
        text=alt.Text("spend_usd_est:Q", format="$,~s")
    )

    return (bar + text).properties(
        title=alt.TitleParams(
            text="Ad Format Performance & Expenditure in NC",
            subtitle="Allocation of capital across Video, Image, and Text ad creatives targeting NC",
            fontSize=14,
            subtitleFontSize=11,
            subtitleColor="#94a3b8"
        ),
        height=300
    )


def create_nc_platform_comparison_chart(df_combined: pd.DataFrame) -> alt.Chart:
    """
    Compares Google Political Ads vs. Meta Ad Library metrics in North Carolina.
    Provides domain headroom and value annotations to prevent text clipping or mark collision.
    """
    if df_combined.empty or "platform" not in df_combined.columns:
        return alt.Chart(pd.DataFrame()).mark_text()

    agg = (
        df_combined.groupby("platform", as_index=False)
        .agg(
            spend_usd_est=("spend_usd_est", "sum"),
            impressions_est=("impressions_est", "sum"),
            ad_count=("ad_id", "count")
        )
    )

    max_spend = agg["spend_usd_est"].max() if not agg.empty else 1.0

    bar = (
        alt.Chart(agg)
        .mark_bar(cornerRadiusEnd=6, size=44)
        .encode(
            x=alt.X("platform:N", title="Advertising Platform", axis=alt.Axis(labelAngle=0, labelPadding=6)),
            y=alt.Y(
                "spend_usd_est:Q",
                title="Total Spend in NC ($ USD)",
                scale=alt.Scale(domainMax=max_spend * 1.16),
                axis=alt.Axis(format="$,~s", titlePadding=10)
            ),
            color=alt.Color(
                "platform:N",
                scale=alt.Scale(domain=["Google", "Meta"], range=["#4285F4", "#0668E1"]),
                legend=None
            ),
            tooltip=[
                alt.Tooltip("platform:N", title="Platform"),
                alt.Tooltip("spend_usd_est:Q", title="NC Spend", format="$,.2f"),
                alt.Tooltip("impressions_est:Q", title="NC Impressions", format=","),
                alt.Tooltip("ad_count:Q", title="Total Creatives", format=",")
            ]
        )
    )

    text = (
        alt.Chart(agg)
        .mark_text(align="center", dy=-8, color="#cbd5e1", fontSize=12, fontWeight="bold")
        .encode(
            x=alt.X("platform:N"),
            y=alt.Y("spend_usd_est:Q"),
            text=alt.Text("spend_usd_est:Q", format="$,~s")
        )
    )

    return (bar + text).properties(
        title=alt.TitleParams(
            text="Platform Budget Allocation in NC: Google vs. Meta",
            subtitle="Comparison of ad dollars distributed across search/YouTube vs. Facebook/Instagram in NC",
            fontSize=14,
            subtitleFontSize=11,
            subtitleColor="#94a3b8"
        ),
        height=300
    )


def create_top_spenders_overview_chart(df: pd.DataFrame, top_n: int = 8) -> alt.Chart:
    """
    Ranks the top political spenders in North Carolina across platforms.
    Uses grouped bar offset (`yOffset='platform:N'`) so Google and Meta bars are cleanly aligned
    side-by-side without overlapping or colliding.
    """
    if df.empty or "advertiser_name" not in df.columns:
        return alt.Chart(pd.DataFrame()).mark_text()

    agg = (
        df.groupby(["advertiser_name", "platform"], as_index=False)["spend_usd_est"]
        .sum()
    )

    top_names = (
        agg.groupby("advertiser_name")["spend_usd_est"]
        .sum()
        .sort_values(ascending=False)
        .head(top_n)
        .index.tolist()
    )

    agg = agg[agg["advertiser_name"].isin(top_names)].copy()
    max_spend = agg["spend_usd_est"].max() if not agg.empty else 1.0

    chart = (
        alt.Chart(agg)
        .mark_bar(cornerRadiusEnd=4, size=14)
        .encode(
            y=alt.Y(
                "advertiser_name:N",
                sort="-x",
                title="PAC / Campaign Organization",
                axis=alt.Axis(labelPadding=6, titlePadding=10)
            ),
            yOffset="platform:N",
            x=alt.X(
                "spend_usd_est:Q",
                title="Total Estimated Spend ($ USD)",
                scale=alt.Scale(domainMax=max_spend * 1.15),
                axis=alt.Axis(format="$,~s", titlePadding=10)
            ),
            color=alt.Color(
                "platform:N",
                scale=alt.Scale(domain=["Google", "Meta"], range=["#4285F4", "#0668E1"]),
                legend=alt.Legend(title="Platform", orient="bottom", titlePadding=8)
            ),
            tooltip=[
                alt.Tooltip("advertiser_name:N", title="Spender"),
                alt.Tooltip("platform:N", title="Platform"),
                alt.Tooltip("spend_usd_est:Q", title="Spend", format="$,.2f")
            ]
        )
        .properties(
            title=alt.TitleParams(
                text=f"Top {top_n} Political Advertisers in North Carolina (2024–Current)",
                subtitle="Google and Meta investments aligned side-by-side to compare digital allocation without overlap",
                fontSize=14,
                subtitleFontSize=11,
                subtitleColor="#94a3b8"
            ),
            height=340
        )
    )
    return chart


