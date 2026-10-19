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


def create_nc_county_spatial_heatmap_chart(
    df_county: pd.DataFrame,
    metric_label: str = "Total Spend ($ USD)"
) -> alt.Chart:
    """
    Renders an interactive spatial heatmap chart of North Carolina counties based on geographic coordinates.
    Overlays county spending intensity circles onto the geographic footprint of North Carolina.
    """
    if df_county.empty or "x" not in df_county.columns or "y" not in df_county.columns:
        return alt.Chart(pd.DataFrame()).mark_text()

    cfg = METRIC_CONFIG.get(metric_label, METRIC_CONFIG["Total Spend ($ USD)"])
    col = cfg["col"] if cfg["col"] in df_county.columns else "spend_usd"

    hover = alt.selection_point(on="mouseover", empty=True)

    # Base heat glow circles
    heat_glow = (
        alt.Chart(df_county)
        .mark_circle(opacity=0.35)
        .encode(
            x=alt.X("x:Q", title="West ⟵ North Carolina Geographic Longitude ⟶ East", axis=alt.Axis(labels=False, ticks=False)),
            y=alt.Y("y:Q", title="North ⟵ Latitude ⟶ South", scale=alt.Scale(reverse=True), axis=alt.Axis(labels=False, ticks=False)),
            size=alt.Size(f"{col}:Q", scale=alt.Scale(range=[300, 3200]), legend=None),
            color=alt.Color(f"{col}:Q", scale=alt.Scale(scheme="yelloworangered"), legend=None)
        )
    )

    # Core county nodes
    heat_nodes = (
        alt.Chart(df_county)
        .mark_circle(stroke="#f8fafc", strokeWidth=1.5, opacity=0.92)
        .encode(
            x=alt.X("x:Q"),
            y=alt.Y("y:Q", scale=alt.Scale(reverse=True)),
            size=alt.Size(
                f"{col}:Q",
                scale=alt.Scale(range=[80, 1100]),
                legend=alt.Legend(title=f"Expenditure Scale", orient="bottom", columns=3)
            ),
            color=alt.Color(
                f"{col}:Q",
                scale=alt.Scale(scheme="yelloworangered"),
                legend=alt.Legend(title=f"Heatmap Intensity ({metric_label})", orient="bottom", gradientLength=260)
            ),
            opacity=alt.condition(hover, alt.value(1.0), alt.value(0.85)),
            tooltip=[
                alt.Tooltip("county_name:N", title="NC County"),
                alt.Tooltip("nc_dma:N", title="Media Market (DMA)"),
                alt.Tooltip("spend_tier:N", title="Spend Tier"),
                alt.Tooltip(f"{col}:Q", title=metric_label, format=cfg["tooltip_format"]),
                alt.Tooltip("impressions_est:Q", title="Est. Impressions", format=",")
            ]
        )
        .add_params(hover)
    )

    # Labels for top counties
    labels = (
        alt.Chart(df_county[df_county["spend_tier"].isin(["🔥 Very High", "🟡 High"])])
        .mark_text(dy=-18, fontSize=11, fontWeight="bold", color="#ffffff")
        .encode(
            x=alt.X("x:Q"),
            y=alt.Y("y:Q", scale=alt.Scale(reverse=True)),
            text=alt.Text("county_name:N")
        )
    )

    chart = (heat_glow + heat_nodes + labels).properties(
        title=alt.TitleParams(
            text=f"North Carolina County Heatmap ({metric_label})",
            subtitle="Geographic intensity plot highlighting spending concentrations in Mecklenburg (Charlotte), Wake (Raleigh), and the Piedmont Triad",
            fontSize=15,
            subtitleFontSize=12,
            subtitleColor="#94a3b8"
        ),
        width=780,
        height=380
    )
    return chart


def generate_nc_county_map_heatmap_svg(
    df_county: pd.DataFrame,
    metric_label: str = "Total Spend ($ USD)"
) -> str:
    """
    Generates a rich, interactive SVG image of North Carolina and its counties
    with a continuous heatmap overlay applied over the image to showcase which regions
    and counties are receiving the most attention and funding from political spenders.
    """
    if df_county.empty:
        return "<div style='color:#94a3b8; text-align:center;'>No county spend data available.</div>"

    max_spend = df_county["spend_usd"].max() if not df_county.empty else 1.0
    if max_spend <= 0:
        max_spend = 1.0

    # Build SVG heat blooms and county markers
    heat_blooms_svg = []
    county_markers_svg = []

    # Sort so smaller circles render on top of bigger ones
    sorted_df = df_county.sort_values(by="spend_usd", ascending=True)

    for i, row in sorted_df.iterrows():
        c_name = row["county_name"]
        spend = row["spend_usd"]
        dma = row["nc_dma"]
        ratio = min(max(spend / max_spend, 0.05), 1.0)
        
        # Calculate pixel coordinates in 900x420 viewport
        px = int(row.get("x", 50) * 8.4) + 30
        py = int(row.get("y", 50) * 3.4) + 40

        # Heat color calculation
        if ratio >= 0.70:
            color = "#ef4444"  # Intense red
            bloom_r = int(45 + ratio * 45)
            bloom_op = 0.55
        elif ratio >= 0.35:
            color = "#f97316"  # Vibrant orange
            bloom_r = int(32 + ratio * 35)
            bloom_op = 0.42
        elif ratio >= 0.15:
            color = "#eab308"  # Yellow
            bloom_r = int(22 + ratio * 25)
            bloom_op = 0.32
        else:
            color = "#38bdf8"  # Cool sky blue / low
            bloom_r = 15
            bloom_op = 0.18

        node_r = int(6 + ratio * 14)

        # Heat bloom element (creates smooth radiant blur overlay)
        heat_blooms_svg.append(
            f'<circle cx="{px}" cy="{py}" r="{bloom_r}" fill="{color}" opacity="{bloom_op}" filter="url(#heat-blur)" />'
        )

        # Core county node with hover title
        is_top = ratio >= 0.35
        label_svg = ""
        if is_top:
            label_svg = f'<text x="{px}" y="{py - node_r - 4}" fill="#ffffff" font-size="11" font-weight="700" text-anchor="middle" style="text-shadow: 0 1px 4px rgba(0,0,0,0.9);">{c_name} (${spend/1e3:,.0f}k)</text>'

        county_markers_svg.append(f"""
        <g class="county-node" style="cursor:pointer;">
            <circle cx="{px}" cy="{py}" r="{node_r}" fill="{color}" stroke="#ffffff" stroke-width="1.8" opacity="0.95">
                <title>{c_name} County ({dma})&#10;Spend: ${spend:,.2f}&#10;Impressions: {row['impressions_est']:,}</title>
            </circle>
            {label_svg}
        </g>
        """)

    blooms_str = "\n".join(heat_blooms_svg)
    nodes_str = "\n".join(county_markers_svg)

    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{
    margin: 0;
    padding: 0;
    background: transparent;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #f8fafc;
}}
.map-card {{
    background: linear-gradient(145deg, #0b1120 0%, #0f172a 100%);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 18px 20px;
    box-shadow: 0 10px 25px -5px rgba(0,0,0,0.5);
}}
.county-node:hover circle {{
    stroke: #38bdf8 !important;
    stroke-width: 3px !important;
    opacity: 1 !important;
}}
</style>
</head>
<body>
<div class="map-card">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 12px; flex-wrap:wrap;">
        <div>
            <h4 style="margin:0; color:#f8fafc; font-size:16px; font-weight:700;">🗺️ North Carolina County Political Ad Spend Heatmap</h4>
            <p style="margin:4px 0 0 0; color:#94a3b8; font-size:12px;">Visualizing regional saturation and competitor funding epicenters overlaid on the geographic map of North Carolina counties</p>
        </div>
        <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid #334155; border-radius: 8px; padding: 5px 12px; font-size: 11px; color: #38bdf8; font-weight:600;">
            North Carolina Battleground Counties (2024–Current)
        </div>
    </div>

    <svg viewBox="0 0 880 380" width="100%" height="auto" style="border-radius: 8px; background: #070d18; display:block;">
        <defs>
            <filter id="heat-blur" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="15" />
            </filter>
            <linearGradient id="legend-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stop-color="#38bdf8" />
                <stop offset="25%" stop-color="#22c55e" />
                <stop offset="55%" stop-color="#eab308" />
                <stop offset="80%" stop-color="#f97316" />
                <stop offset="100%" stop-color="#ef4444" />
            </linearGradient>
        </defs>

        <!-- North Carolina Map Silhouette & County Region Footprint -->
        <path d="M 55,220 L 120,200 L 160,190 L 210,180 L 260,160 L 340,145 L 410,130 L 490,125 L 610,125 L 730,130 L 775,170 L 825,185 L 800,235 L 740,285 L 685,315 L 640,295 L 590,260 L 530,260 L 480,255 L 410,265 L 370,285 L 330,270 L 280,265 L 220,255 L 165,260 L 110,265 Z" 
              fill="#10192b" stroke="#334155" stroke-width="2" opacity="0.95" />

        <!-- County Guideline Grid -->
        <path d="M 260,160 L 280,265 M 340,145 L 370,285 M 410,130 L 410,265 M 490,125 L 530,260 M 610,125 L 590,260 M 730,130 L 685,315" 
              stroke="#1e293b" stroke-width="1.2" stroke-dasharray="4,4" />

        <!-- Geographic Region Labels -->
        <text x="110" y="165" fill="#475569" font-size="11" font-weight="600" letter-spacing="1">WESTERN MOUNTAINS</text>
        <text x="325" y="120" fill="#475569" font-size="11" font-weight="600" letter-spacing="1">PIEDMONT / CHARLOTTE</text>
        <text x="555" y="110" fill="#475569" font-size="11" font-weight="600" letter-spacing="1">TRIANGLE (RDU)</text>
        <text x="700" y="155" fill="#475569" font-size="11" font-weight="600" letter-spacing="1">COASTAL PLAIN</text>

        <!-- Continuous Radiant Heatmap Layer -->
        {blooms_str}

        <!-- County Nodes & Labels Layer -->
        {nodes_str}

        <!-- Heatmap Intensity Legend -->
        <g transform="translate(30, 340)">
            <text x="0" y="14" fill="#94a3b8" font-size="11" font-weight="600">HEAT INTENSITY:</text>
            <rect x="120" y="4" width="240" height="12" rx="6" fill="url(#legend-gradient)" />
            <text x="120" y="27" fill="#64748b" font-size="10">Low Spend (<$150k)</text>
            <text x="230" y="27" fill="#64748b" font-size="10" text-anchor="middle">Moderate ($150k-$400k)</text>
            <text x="360" y="27" fill="#ef4444" font-size="10" font-weight="700" text-anchor="end">🔥 Saturation (>$1M)</text>

            <circle cx="530" cy="10" r="5" fill="#ef4444" />
            <text x="542" y="14" fill="#e2e8f0" font-size="11">Mecklenburg & Wake Epicenters</text>

            <circle cx="720" cy="10" r="5" fill="#eab308" />
            <text x="732" y="14" fill="#e2e8f0" font-size="11">Triad & Coastal Saturation</text>
        </g>
    </svg>
</div>
</body>
</html>
"""
    return html_content


# Alias for backward compatibility
create_nc_market_share_chart = create_nc_pac_market_share_chart

