"""
Regional & Geographic Charts - North Carolina Focus
Focuses on North Carolina Regional Competitor Spend Intelligence:
Mapping and ranking ad expenditures across NC Designated Market Areas (DMAs).
Supports dynamic metric and dimension toggling via drop-down menu selections.
"""

from __future__ import annotations

import altair as alt
import pandas as pd


METRIC_CONFIG = {
    "Total Spend ($ USD)": {
        "col": "spend_usd",
        "format": "$,~s",
        "tooltip_format": "$,.2f",
        "title": "Total Spend ($ USD)"
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


def create_nc_dma_ranking_chart(
    df_geo: pd.DataFrame,
    metric_label: str = "Total Spend ($ USD)"
) -> alt.Chart:
    """
    Ranks North Carolina's 6 Designated Market Areas (DMAs) by the selected metric.
    Exposes battleground media market saturation across North Carolina.
    """
    if df_geo.empty or "nc_dma" not in df_geo.columns:
        return alt.Chart(pd.DataFrame({"msg": ["No NC DMA data available"]})).mark_text().encode(text="msg:N")

    cfg = METRIC_CONFIG.get(metric_label, METRIC_CONFIG["Total Spend ($ USD)"])
    col = cfg["col"] if cfg["col"] in df_geo.columns else "spend_usd"

    if col == "ad_count":
        agg = (
            df_geo.groupby("nc_dma", as_index=False)
            .agg(ad_count=("advertiser_id", "count"))
            .sort_values(by=col, ascending=False)
        )
    else:
        agg = (
            df_geo.groupby("nc_dma", as_index=False)[col]
            .sum()
            .sort_values(by=col, ascending=False)
        )

    hover = alt.selection_point(on="mouseover", empty=True)

    chart = (
        alt.Chart(agg)
        .mark_bar(cornerRadiusEnd=5, color="#f59e0b", size=22)
        .encode(
            x=alt.X(
                f"{col}:Q",
                title=f"NC Market: {cfg['title']}",
                axis=alt.Axis(format=cfg["format"], grid=True)
            ),
            y=alt.Y(
                "nc_dma:N",
                sort="-x",
                title="NC Media Market (DMA)"
            ),
            opacity=alt.condition(hover, alt.value(1.0), alt.value(0.75)),
            tooltip=[
                alt.Tooltip("nc_dma:N", title="Media Market"),
                alt.Tooltip(f"{col}:Q", title=metric_label, format=cfg["tooltip_format"])
            ]
        )
        .add_params(hover)
        .properties(
            title=alt.TitleParams(
                text=f"North Carolina Media Market Saturation ({metric_label})",
                subtitle="Designated Market Areas (DMAs) ranked by competitor political advertising intensity",
                fontSize=15,
                subtitleFontSize=12,
                subtitleColor="#94a3b8"
            ),
            height=320
        )
    )

    text = (
        alt.Chart(agg)
        .mark_text(align="left", dx=6, color="#e2e8f0", fontSize=11)
        .encode(
            x=alt.X(f"{col}:Q"),
            y=alt.Y("nc_dma:N", sort="-x"),
            text=alt.Text(f"{col}:Q", format=cfg["format"])
        )
    )

    return chart + text


def create_nc_advertiser_breakdown_chart(
    df_geo: pd.DataFrame,
    metric_label: str = "Total Spend ($ USD)"
) -> alt.Chart:
    """
    Stacked bar chart detailing spend by competitor PAC / advertiser within each NC media market.
    """
    if df_geo.empty or "advertiser_name" not in df_geo.columns or "nc_dma" not in df_geo.columns:
        return alt.Chart(pd.DataFrame()).mark_text()

    cfg = METRIC_CONFIG.get(metric_label, METRIC_CONFIG["Total Spend ($ USD)"])
    col = cfg["col"] if cfg["col"] in df_geo.columns else "spend_usd"

    select_adv = alt.selection_point(fields=["advertiser_name"], bind="legend")

    chart = (
        alt.Chart(df_geo)
        .mark_bar(cornerRadiusEnd=3)
        .encode(
            x=alt.X(f"{col}:Q", title=cfg["title"], axis=alt.Axis(format=cfg["format"])),
            y=alt.Y("nc_dma:N", sort="-x", title="NC Media Market (DMA)"),
            color=alt.Color(
                "advertiser_name:N",
                scale=alt.Scale(scheme="category10"),
                legend=alt.Legend(title="Competitor / PAC", orient="bottom", columns=2)
            ),
            opacity=alt.condition(select_adv, alt.value(1.0), alt.value(0.2)),
            tooltip=[
                alt.Tooltip("nc_dma:N", title="Market"),
                alt.Tooltip("advertiser_name:N", title="Competitor PAC"),
                alt.Tooltip(f"{col}:Q", title=metric_label, format=cfg["tooltip_format"])
            ]
        )
        .add_params(select_adv)
        .properties(
            title=alt.TitleParams(
                text=f"Competitor Spending Share Across NC Media Markets ({metric_label})",
                subtitle="Click an advertiser in the legend below to isolate their regional investment footprint in NC",
                fontSize=14,
                subtitleFontSize=11,
                subtitleColor="#94a3b8"
            ),
            height=340
        )
    )
    return chart


def create_nc_pac_market_share_chart(df_geo: pd.DataFrame) -> alt.Chart:
    """100% normalized stacked bar chart showing competitor PAC market share percentage in each NC DMA."""
    if df_geo.empty or "advertiser_name" not in df_geo.columns:
        return alt.Chart(pd.DataFrame()).mark_text()

    chart = (
        alt.Chart(df_geo)
        .mark_bar()
        .encode(
            x=alt.X("spend_usd:Q", stack="normalize", title="Expenditure Share (%)", axis=alt.Axis(format="%")),
            y=alt.Y("nc_dma:N", title="NC Media Market"),
            color=alt.Color("advertiser_name:N", scale=alt.Scale(scheme="tableau10"), legend=alt.Legend(title="Competitor PAC", orient="bottom", columns=2)),
            tooltip=[
                alt.Tooltip("nc_dma:N", title="Market"),
                alt.Tooltip("advertiser_name:N", title="Competitor"),
                alt.Tooltip("spend_usd:Q", title="Spend ($)", format="$,.2f")
            ]
        )
        .properties(
            title=alt.TitleParams(
                text="Competitor Market Share Distribution (% of Market Total)",
                subtitle="Proportion of total ad dollars commanded by each political organization in North Carolina",
                fontSize=14,
                subtitleFontSize=11,
                subtitleColor="#94a3b8"
            ),
            height=300
        )
    )
    return chart


def create_nc_county_heatmap_chart(
    df_county: pd.DataFrame,
    metric_label: str = "Total Spend ($ USD)"
) -> alt.Chart:
    """
    Renders an interactive North Carolina County Spend Heatmap.
    Displays counties ranked by expenditure intensity with a yellow-orange-red heatmap color gradient,
    interactive hover highlights, and comprehensive tooltips.
    """
    if df_county.empty:
        return alt.Chart(pd.DataFrame({"msg": ["No NC County spend data available"]})).mark_text().encode(text="msg:N")

    cfg = METRIC_CONFIG.get(metric_label, METRIC_CONFIG["Total Spend ($ USD)"])
    col = cfg["col"] if cfg["col"] in df_county.columns else "spend_usd"

    hover = alt.selection_point(on="mouseover", empty=True)

    chart = (
        alt.Chart(df_county)
        .mark_bar(cornerRadiusEnd=5, size=16)
        .encode(
            x=alt.X(
                f"{col}:Q",
                title=f"NC County: {cfg['title']}",
                axis=alt.Axis(format=cfg["format"], grid=True)
            ),
            y=alt.Y(
                "county_name:N",
                sort="-x",
                title="North Carolina County"
            ),
            color=alt.Color(
                f"{col}:Q",
                scale=alt.Scale(scheme="yelloworangered"),
                legend=alt.Legend(
                    title=f"Heatmap Intensity ({metric_label})",
                    orient="bottom",
                    format=cfg["format"],
                    gradientLength=280
                )
            ),
            opacity=alt.condition(hover, alt.value(1.0), alt.value(0.8)),
            tooltip=[
                alt.Tooltip("county_name:N", title="NC County"),
                alt.Tooltip("nc_dma:N", title="Media Market (DMA)"),
                alt.Tooltip("spend_tier:N", title="Spending Tier"),
                alt.Tooltip(f"{col}:Q", title=metric_label, format=cfg["tooltip_format"])
            ]
        )
        .add_params(hover)
        .properties(
            title=alt.TitleParams(
                text=f"North Carolina County Spend Heatmap ({metric_label})",
                subtitle="County-level expenditure intensity ranking across North Carolina battleground regions",
                fontSize=15,
                subtitleFontSize=12,
                subtitleColor="#94a3b8"
            ),
            height=580
        )
    )

    text = (
        alt.Chart(df_county)
        .mark_text(align="left", dx=6, color="#f8fafc", fontSize=10)
        .encode(
            x=alt.X(f"{col}:Q"),
            y=alt.Y("county_name:N", sort="-x"),
            text=alt.Text(f"{col}:Q", format=cfg["format"])
        )
    )

    return chart + text


def create_nc_county_choropleth_chart(
    df_county: pd.DataFrame,
    metric_label: str = "Total Spend ($ USD)"
) -> alt.Chart:
    """
    Renders an interactive geographic choropleth map of North Carolina counties.
    Joins TopoJSON county geometries on FIPS codes and applies a yellow-orange-red heatmap color scheme.
    """
    if df_county.empty:
        return alt.Chart(pd.DataFrame({"msg": ["No NC County spend data available"]})).mark_text().encode(text="msg:N")

    cfg = METRIC_CONFIG.get(metric_label, METRIC_CONFIG["Total Spend ($ USD)"])
    col = cfg["col"] if cfg["col"] in df_county.columns else "spend_usd"

    counties_url = "https://cdn.jsdelivr.net/npm/us-atlas@3/counties-10m.json"
    counties = alt.topo_feature(counties_url, "counties")

    hover = alt.selection_point(on="mouseover", empty=True)

    choropleth = (
        alt.Chart(counties)
        .mark_geoshape(stroke="#334155", strokeWidth=0.7)
        .transform_lookup(
            lookup="id",
            from_=alt.LookupData(
                df_county,
                "fips",
                ["county_name", "nc_dma", "spend_usd", "impressions_est", "spend_tier"]
            )
        )
        .transform_filter(
            (alt.datum.id >= 37000) & (alt.datum.id < 38000)
        )
        .encode(
            color=alt.Color(
                f"{col}:Q",
                scale=alt.Scale(scheme="yelloworangered"),
                legend=alt.Legend(
                    title=f"NC County {metric_label}",
                    orient="bottom",
                    format=cfg["format"],
                    gradientLength=320
                )
            ),
            opacity=alt.condition(hover, alt.value(1.0), alt.value(0.85)),
            tooltip=[
                alt.Tooltip("county_name:N", title="NC County"),
                alt.Tooltip("nc_dma:N", title="Media Market (DMA)"),
                alt.Tooltip("spend_tier:N", title="Spend Priority Tier"),
                alt.Tooltip("spend_usd:Q", title="Estimated Spend ($)", format="$,.2f"),
                alt.Tooltip("impressions_est:Q", title="Est. Impressions", format=",")
            ]
        )
        .add_params(hover)
        .project(
            type="albersUsa"
        )
        .properties(
            title=alt.TitleParams(
                text=f"Geographic Heatmap: North Carolina County Political Ad Spend ({metric_label})",
                subtitle="Regional saturation map highlighting top advertising epicenters (Mecklenburg, Wake, Guilford)",
                fontSize=15,
                subtitleFontSize=12,
                subtitleColor="#94a3b8"
            ),
            width=700,
            height=380
        )
    )

    return choropleth


# Alias for backward compatibility
create_nc_market_share_chart = create_nc_pac_market_share_chart

