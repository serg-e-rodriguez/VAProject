"""
Regional & Geographic Charts - North Carolina Focus
Focuses on North Carolina Regional Competitor Spend Intelligence:
Mapping and ranking ad expenditures across NC Designated Market Areas (DMAs).
Supports dynamic metric and dimension toggling via drop-down menu selections.
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

    max_val = agg[col].max() if not agg.empty else 1.0
    hover = alt.selection_point(on="mouseover", empty=True)

    chart = (
        alt.Chart(agg)
        .mark_bar(cornerRadiusEnd=5, color="#f59e0b", size=22)
        .encode(
            x=alt.X(
                f"{col}:Q",
                title=f"NC Market: {cfg['title']}",
                scale=alt.Scale(domainMax=max_val * 1.18 if max_val > 0 else 100),
                axis=alt.Axis(format=cfg["format"], grid=True, titlePadding=10, labelPadding=6)
            ),
            y=alt.Y(
                "nc_dma:N",
                sort="-x",
                title="NC Media Market (DMA)",
                axis=alt.Axis(labelPadding=6, titlePadding=10)
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
        .mark_text(align="left", dx=6, color="#e2e8f0", fontSize=11, fontWeight="bold")
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
            x=alt.X(
                f"{col}:Q",
                title=cfg["title"],
                axis=alt.Axis(format=cfg["format"], titlePadding=10, labelPadding=6)
            ),
            y=alt.Y(
                "nc_dma:N",
                sort="-x",
                title="NC Media Market (DMA)",
                axis=alt.Axis(labelPadding=6, titlePadding=10)
            ),
            color=alt.Color(
                "advertiser_name:N",
                scale=alt.Scale(scheme="category10"),
                legend=alt.Legend(title="Competitor / PAC", orient="bottom", columns=2, titlePadding=8)
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

    max_spend = df_county[col].max() if not df_county.empty else 1.0
    hover = alt.selection_point(on="mouseover", empty=True)

    chart = (
        alt.Chart(df_county)
        .mark_bar(cornerRadiusEnd=5, size=16)
        .encode(
            x=alt.X(
                f"{col}:Q",
                title=f"NC County: {cfg['title']}",
                scale=alt.Scale(domainMax=max_spend * 1.18 if max_spend > 0 else 100),
                axis=alt.Axis(format=cfg["format"], grid=True, titlePadding=10, labelPadding=6)
            ),
            y=alt.Y(
                "county_name:N",
                sort="-x",
                title="North Carolina County",
                axis=alt.Axis(labelPadding=6, titlePadding=10)
            ),
            color=alt.Color(
                f"{col}:Q",
                scale=alt.Scale(scheme="yelloworangered"),
                legend=alt.Legend(
                    title=f"Heatmap Intensity ({metric_label})",
                    orient="bottom",
                    format=cfg["format"],
                    gradientLength=280,
                    titlePadding=8
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
        .mark_text(align="left", dx=6, color="#f8fafc", fontSize=10, fontWeight="bold")
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
    selected_county: str = "Mecklenburg",
    metric_label: str = "Total Spend ($ USD)"
) -> str:
    """
    Renders an enlarged, interactive North Carolina Regional Spending Heatmap:
    - Expanded 1200x800 canvas (2.0x base scale) providing ample breathing room for points and labels.
    - Overlays radiant heatmap blooms and county spending nodes directly on top of `nc.jpg`.
    - Point placements strictly calibrated to match real county locations from `nccountynames.jpg`.
    - Synchronized with Streamlit county dropdown selection: selecting any county highlights it on the map and updates the deep-dive display.
    - Prominently highlights the currently selected county with a multi-layered pulsating beacon, dashed rotating ring, cyan glow, and floating pin badge.
    - Completely non-scrollable and expands to use up the full available container space without scrolling or HUD clutter.
    - Note: nccountynames.jpg is used exclusively for spatial context during development and is NOT displayed in the UI.
    """
    if df_county.empty:
        return "<div style='color:#94a3b8; text-align:center;'>No county spend data available.</div>"

    import base64
    from pathlib import Path

    # Resolve path for nc.jpg
    p_nc = Path("nc.jpg")
    if not p_nc.exists():
        p_nc = Path("nc.JPEG")
    if not p_nc.exists():
        found = list(Path(".").glob("**/nc.jpg"))
        if found:
            p_nc = found[0]

    nc_b64 = base64.b64encode(p_nc.read_bytes()).decode("utf-8") if p_nc.exists() else ""

    max_spend = df_county["spend_usd"].max() if not df_county.empty else 1.0
    if max_spend <= 0:
        max_spend = 1.0

    # Directional label offsets calibrated for 1200x800 canvas (2.0x scale) to guarantee labels NEVER collide
    LABEL_CONFIGS = {
        "Mecklenburg": ("end", -18, 4),
        "Gaston": ("end", -18, 22),
        "Cabarrus": ("start", 18, -10),
        "Union": ("start", 18, 20),
        "Forsyth": ("end", -18, -14),
        "Guilford": ("middle", 0, -26),
        "Alamance": ("start", 16, -16),
        "Orange": ("end", -16, 20),
        "Durham": ("end", -18, -12),
        "Wake": ("start", 20, 0),
        "Johnston": ("start", 18, 22),
        "Harnett": ("end", -18, 20),
        "Cumberland": ("middle", 0, 30),
        "Buncombe": ("middle", 0, -26),
        "Henderson": ("end", -18, 20),
        "New Hanover": ("start", 18, -8),
        "Brunswick": ("middle", 0, 30),
        "Pitt": ("start", 18, -10),
        "Craven": ("start", 18, 20),
        "Onslow": ("start", 18, 0),
        "Wayne": ("middle", 0, 26),
        "Rowan": ("end", -18, -10),
        "Catawba": ("end", -18, -10),
        "Iredell": ("middle", 0, -24),
        "Davidson": ("end", -18, 16),
    }

    heat_blooms_svg = []
    normal_markers_svg = []
    selected_marker_svg = []

    # Sort so smaller circles render on top of larger ones
    sorted_df = df_county.sort_values(by="spend_usd", ascending=True)

    for _, row in sorted_df.iterrows():
        c_name = row["county_name"]
        spend = row["spend_usd"]
        dma = row["nc_dma"]
        tier = row.get("spend_tier", "⚪ Low")
        impressions = row.get("impressions_est", int(spend * 45))
        ratio = min(max(spend / max_spend, 0.04), 1.0)
        is_selected = (c_name.strip().lower() == selected_county.strip().lower())

        # Scale calibrated coordinates by 2.0 to match expanded 1200x800 canvas
        px = int(row.get("x", 300) * 2.0)
        py = int(row.get("y", 200) * 2.0)

        # Radiant bloom calculation based on spending intensity
        if ratio >= 0.70:
            color = "#ef4444"  # Red (Epicenter saturation)
            bloom_r = int(60 + ratio * 50)
            bloom_op = 0.65
        elif ratio >= 0.35:
            color = "#f97316"  # Orange (High spending)
            bloom_r = int(45 + ratio * 40)
            bloom_op = 0.52
        elif ratio >= 0.15:
            color = "#eab308"  # Yellow (Moderate)
            bloom_r = int(32 + ratio * 28)
            bloom_op = 0.42
        else:
            color = "#38bdf8"  # Cyan / Light blue (Low)
            bloom_r = 24
            bloom_op = 0.30

        # Highly distinguishable node circle
        node_r = int(9 + ratio * 18)

        # Radiant heat bloom
        heat_blooms_svg.append(
            f'<circle cx="{px}" cy="{py}" r="{bloom_r}" fill="{color}" opacity="{bloom_op}" filter="url(#heat-blur)" />'
        )

        # Directional non-overlapping label with high-contrast dark halo outline
        is_top = ratio >= 0.10 or tier in ["🔥 Very High", "🟡 High", "🟢 Moderate"] or is_selected
        label_svg = ""
        if is_top:
            anchor, dx, dy = LABEL_CONFIGS.get(c_name, ("middle", 0, -node_r - 8))
            lx = px + dx
            ly = py + dy
            active_star = "★ " if is_selected else ""
            label_color = "#38bdf8" if is_selected else "#ffffff"
            label_font_weight = "900" if is_selected else "700"
            label_font_size = "14" if is_selected else "13"
            label_svg = (
                f'<text x="{lx}" y="{ly}" fill="{label_color}" font-size="{label_font_size}" '
                f'font-weight="{label_font_weight}" text-anchor="{anchor}" '
                f'paint-order="stroke fill" stroke="#070d18" stroke-width="5.5" stroke-linejoin="round" '
                f'filter="url(#text-shadow)">'
                f'{active_star}{c_name} <tspan font-weight="600" fill="#cbd5e1">(${spend/1e3:,.0f}k)</tspan></text>'
            )

        if is_selected:
            # Multi-layered pulsating beacon and pin badge for selected county
            active_ring_svg = (
                f'<circle cx="{px}" cy="{py}" r="{node_r + 6}" fill="none" stroke="#38bdf8" stroke-width="2.8" opacity="0.9">'
                f'<animate attributeName="r" values="{node_r + 6};{node_r + 32}" dur="2s" repeatCount="indefinite" />'
                f'<animate attributeName="opacity" values="0.9;0" dur="2s" repeatCount="indefinite" />'
                f'</circle>'
                f'<circle cx="{px}" cy="{py}" r="{node_r + 11}" fill="none" stroke="#38bdf8" stroke-width="3" stroke-dasharray="5,4">'
                f'<animateTransform attributeName="transform" type="rotate" from="0 {px} {py}" to="360 {px} {py}" dur="5s" repeatCount="indefinite" />'
                f'</circle>'
                f'<circle cx="{px}" cy="{py}" r="{node_r + 4}" fill="none" stroke="#ffffff" stroke-width="2.5" />'
            )
            # Floating Callout Badge Pin directly above the selected county
            badge_y = py - node_r - 26
            badge_svg = (
                f'<g class="selected-badge" transform="translate({px}, {badge_y})">'
                f'<rect x="-80" y="-13" width="160" height="26" rx="13" fill="#0284c7" stroke="#ffffff" stroke-width="2.2" filter="url(#text-shadow)"/>'
                f'<text x="0" y="4" fill="#ffffff" font-size="11.5" font-weight="800" text-anchor="middle" filter="url(#text-shadow)">📍 {c_name.upper()} (SELECTED)</text>'
                f'</g>'
            )
            selected_marker_svg.append(f"""
            <g class="county-node active-node" data-name="{c_name}" data-dma="{dma}" data-spend="${spend:,.2f}" data-imp="{impressions:,}" data-tier="{tier}">
                {active_ring_svg}
                <circle class="node-main-circle" cx="{px}" cy="{py}" r="{node_r + 2}" fill="{color}" stroke="#38bdf8" stroke-width="4.5" filter="url(#selected-glow)" opacity="1">
                    <title>{c_name} County ({dma}) [SELECTED]&#10;Spend: ${spend:,.2f}&#10;Impressions: {impressions:,}&#10;Tier: {tier}</title>
                </circle>
                {label_svg}
                {badge_svg}
            </g>
            """)
        else:
            normal_markers_svg.append(f"""
            <g class="county-node" data-name="{c_name}" data-dma="{dma}" data-spend="${spend:,.2f}" data-imp="{impressions:,}" data-tier="{tier}">
                <circle class="node-main-circle" cx="{px}" cy="{py}" r="{node_r}" fill="{color}" stroke="#ffffff" stroke-width="2.2" opacity="0.96">
                    <title>{c_name} County ({dma})&#10;Spend: ${spend:,.2f}&#10;Impressions: {impressions:,}&#10;Tier: {tier}</title>
                </circle>
                {label_svg}
            </g>
            """)

    blooms_str = "\n".join(heat_blooms_svg)
    # Selected county marker is appended LAST so it renders at the absolute top layer
    nodes_str = "\n".join(normal_markers_svg + selected_marker_svg)

    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
* {{
    box-sizing: border-box;
}}
html, body {{
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    overflow: hidden; /* Fully non-scrollable */
    background: transparent;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #f8fafc;
}}
.map-card {{
    width: 100%;
    height: 100%;
    margin: 0;
    padding: 16px 20px;
    background: linear-gradient(145deg, #0b1120 0%, #0f172a 100%);
    border: 1px solid #334155;
    border-radius: 14px;
    box-shadow: 0 12px 30px -5px rgba(0,0,0,0.6);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    overflow: hidden; /* Zero scrollbars */
}}
.card-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    flex-shrink: 0;
}}
.map-viewport {{
    width: 100%;
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
}}
svg {{
    width: 100%;
    height: 100%;
    max-height: 100%;
    display: block;
    border-radius: 10px;
    background: #070d18;
}}
.county-node {{
    cursor: default;
    pointer-events: all;
    transition: transform 0.15s ease;
}}
.county-node * {{
    cursor: default;
    pointer-events: all;
}}
.county-node:hover .node-main-circle {{
    stroke: #38bdf8 !important;
    stroke-width: 4.5px !important;
    opacity: 1 !important;
    filter: url(#selected-glow) !important;
}}
.active-node .node-main-circle {{
    stroke: #38bdf8 !important;
    stroke-width: 4.5px !important;
}}
</style>
</head>
<body>
<div class="map-card">
    <div class="card-header">
        <div>
            <h4 style="margin:0; color:#f8fafc; font-size:18px; font-weight:700;">🗺️ North Carolina Regional Competitor Spend Heatmap (Enlarged Canvas)</h4>
            <p style="margin:3px 0 0 0; color:#94a3b8; font-size:12.5px;">
                Overlaying ad spend onto North Carolina (<strong>nc.jpg</strong>) • Select any county in the dropdown menu below to highlight & inspect analytics
            </p>
        </div>
        <div style="background: rgba(15, 23, 42, 0.85); border: 1.5px solid #38bdf8; border-radius: 8px; padding: 6px 14px; font-size: 13px; color: #38bdf8; font-weight:700;">
            📍 Highlighted: <strong>{selected_county} County</strong>
        </div>
    </div>

    <!-- Non-Scrollable Responsive Heatmap Viewport (1200x800 Canvas) -->
    <div class="map-viewport">
        <svg viewBox="0 0 1200 800" preserveAspectRatio="xMidYMid meet">
            <defs>
                <filter id="heat-blur" x="-50%" y="-50%" width="200%" height="200%">
                    <feGaussianBlur stdDeviation="22" />
                </filter>
                <filter id="text-shadow" x="-20%" y="-20%" width="140%" height="140%">
                    <feDropShadow dx="0" dy="1.5" stdDeviation="3" flood-color="#000000" flood-opacity="0.95"/>
                </filter>
                <filter id="selected-glow" x="-50%" y="-50%" width="200%" height="200%">
                    <feDropShadow dx="0" dy="0" stdDeviation="5" flood-color="#38bdf8" flood-opacity="1"/>
                    <feDropShadow dx="0" dy="0" stdDeviation="10" flood-color="#0284c7" flood-opacity="0.8"/>
                </filter>
                <linearGradient id="legend-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stop-color="#38bdf8" />
                    <stop offset="30%" stop-color="#22c55e" />
                    <stop offset="60%" stop-color="#eab308" />
                    <stop offset="85%" stop-color="#f97316" />
                    <stop offset="100%" stop-color="#ef4444" />
                </linearGradient>
            </defs>

            <!-- Base Map Image Layer (nc.jpg scaled to 1200x800 canvas) -->
            <image href="data:image/jpeg;base64,{nc_b64}" x="0" y="0" width="1200" height="800" 
                   preserveAspectRatio="none" 
                   style="filter: invert(0.88) hue-rotate(185deg) contrast(1.15); opacity: 0.88;" />

            <!-- Continuous Radiant Heatmap Layer -->
            <g id="heat-blooms-layer">
                {blooms_str}
            </g>

            <!-- County Nodes & High-Contrast Directional Labels Layer -->
            <g id="county-nodes-layer">
                {nodes_str}
            </g>

            <!-- Integrated Heatmap Intensity Legend -->
            <g transform="translate(30, 750)">
                <text x="0" y="14" fill="#94a3b8" font-size="12" font-weight="700">HEATMAP INTENSITY:</text>
                <rect x="155" y="2" width="260" height="14" rx="7" fill="url(#legend-gradient)" />
                <text x="155" y="30" fill="#64748b" font-size="11">Low (<$150k)</text>
                <text x="285" y="30" fill="#64748b" font-size="11" text-anchor="middle">Moderate</text>
                <text x="415" y="30" fill="#ef4444" font-size="11" font-weight="700" text-anchor="end">🔥 Saturation (>$1M)</text>

                <circle cx="485" cy="9" r="6" fill="#ef4444" stroke="#ffffff" stroke-width="1.8" />
                <text x="500" y="14" fill="#e2e8f0" font-size="12">Charlotte (Mecklenburg) & Raleigh (Wake)</text>

                <circle cx="770" cy="9" r="6" fill="#f97316" stroke="#ffffff" stroke-width="1.8" />
                <text x="785" y="14" fill="#e2e8f0" font-size="12">Piedmont Triad Epicenter</text>
            </g>
        </svg>
    </div>
</div>
</body>
</html>
"""
    return html_content


def create_county_campaign_spend_chart(
    df_geo: pd.DataFrame,
    county_name: str,
    dma: str,
    metric_label: str = "Total Spend ($ USD)",
    top_n: int = 8
) -> alt.Chart:
    """
    Renders a bar chart showing how much each competitor campaign and PAC
    has spent in the selected county's media market region.
    Guarantees scale headroom padding (max_val * 1.22) so data labels never clip.
    """
    cfg = METRIC_CONFIG.get(metric_label, METRIC_CONFIG["Total Spend ($ USD)"])
    col = cfg["col"] if cfg["col"] in df_geo.columns else "spend_usd"

    # Filter to this county's DMA if available
    if not df_geo.empty and "nc_dma" in df_geo.columns:
        filtered = df_geo[df_geo["nc_dma"] == dma]
        if filtered.empty:
            filtered = df_geo
    else:
        filtered = df_geo

    if filtered.empty or "advertiser_name" not in filtered.columns:
        return alt.Chart(pd.DataFrame({"msg": [f"No regional spending records for {county_name} County ({dma})"]})).mark_text(color="#94a3b8").encode(text="msg:N")

    agg = (
        filtered.groupby("advertiser_name", as_index=False)[col]
        .sum()
        .sort_values(by=col, ascending=False)
        .head(top_n)
    )

    if agg.empty:
        return alt.Chart(pd.DataFrame({"msg": [f"No campaign spending data for {county_name}"]})).mark_text(color="#94a3b8").encode(text="msg:N")

    max_val = agg[col].max() if not agg.empty else 1.0
    hover = alt.selection_point(on="mouseover", empty=True)

    chart = (
        alt.Chart(agg)
        .mark_bar(cornerRadiusEnd=5, color="#38bdf8", size=20)
        .encode(
            x=alt.X(
                f"{col}:Q",
                title=f"Regional Investment: {cfg['title']}",
                scale=alt.Scale(domainMax=max_val * 1.22 if max_val > 0 else 100),
                axis=alt.Axis(format=cfg["format"], grid=True, titlePadding=10, labelPadding=6)
            ),
            y=alt.Y(
                "advertiser_name:N",
                sort="-x",
                title="Competitor Campaign / PAC",
                axis=alt.Axis(labelLimit=220, labelPadding=6, titlePadding=10)
            ),
            opacity=alt.condition(hover, alt.value(1.0), alt.value(0.78)),
            tooltip=[
                alt.Tooltip("advertiser_name:N", title="Campaign / PAC"),
                alt.Tooltip(f"{col}:Q", title=metric_label, format=cfg["tooltip_format"])
            ]
        )
        .add_params(hover)
        .properties(
            title=alt.TitleParams(
                text=f"Campaign & PAC Spending in {county_name} Region ({dma})",
                subtitle=f"Rival organizations ranked by ad investment in this media market ({metric_label})",
                fontSize=14,
                subtitleFontSize=11,
                subtitleColor="#94a3b8"
            ),
            height=280
        )
    )

    text = (
        alt.Chart(agg)
        .mark_text(align="left", dx=6, color="#f8fafc", fontSize=10.5, fontWeight="bold")
        .encode(
            x=alt.X(f"{col}:Q"),
            y=alt.Y("advertiser_name:N", sort="-x"),
            text=alt.Text(f"{col}:Q", format=cfg["format"])
        )
    )

    return chart + text


def create_county_meta_age_cohort_chart(
    df_meta_demo: pd.DataFrame,
    county_name: str,
    dma: str,
    metric_label: str = "Estimated Impressions"
) -> alt.Chart:
    """
    Renders an Altair chart analyzing audience delivery by age cohort and gender
    from the Meta Ad Library API for the selected county's media market.
    Strictly filters against canonical VALID_AGE_COHORTS with ZERO empty gaps.
    Configures scale headroom padding to avoid text clipping.
    """
    if df_meta_demo.empty:
        return alt.Chart(pd.DataFrame({"msg": [f"No Meta demographic data available for {county_name}"]})).mark_text(color="#94a3b8").encode(text="msg:N")

    # Filter to this county's DMA if present, otherwise use calibrated state distribution
    filtered = df_meta_demo
    if "nc_dma" in df_meta_demo.columns:
        match_dma = df_meta_demo[df_meta_demo["nc_dma"] == dma]
        if not match_dma.empty:
            filtered = match_dma

    # Determine metric column
    if "Spend" in metric_label or "spend" in metric_label.lower():
        metric_col = "demographic_spend_usd" if "demographic_spend_usd" in filtered.columns else "spend_usd_est"
        fmt = "$,~s"
        t_fmt = "$,.2f"
        y_title = "Meta Ad Spend ($ USD)"
    else:
        metric_col = "demographic_impressions" if "demographic_impressions" in filtered.columns else "impressions_est"
        fmt = "~s"
        t_fmt = ","
        y_title = "Delivered Ad Impressions"

    valid_cohorts = ["18-24", "25-34", "35-44", "45-54", "55-64", "≥65"]
    has_gender = check_gender_data_exists(filtered, "gender")

    if has_gender:
        # Filter strictly to canonical cohorts and non-empty gender (zero empty gaps)
        clean_demo = filtered[
            filtered["age_group"].isin(valid_cohorts) &
            filtered["gender"].isin(["Female", "Male"]) &
            filtered[metric_col].notna() &
            (filtered[metric_col] > 0)
        ].copy()

        if clean_demo.empty:
            return alt.Chart(pd.DataFrame({"msg": [f"No demographic delivery records for {county_name} ({dma})"]})).mark_text(color="#94a3b8").encode(text="msg:N")

        agg = (
            clean_demo.groupby(["age_group", "gender"], as_index=False)[metric_col]
            .sum()
        )

        max_val = agg[metric_col].max() if not agg.empty else 1.0
        hover = alt.selection_point(on="mouseover", empty=True)

        chart = (
            alt.Chart(agg)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X(
                    "age_group:N",
                    sort=valid_cohorts,
                    title="Voter Age Cohort (Meta Ad Library)",
                    axis=alt.Axis(labelAngle=0, labelPadding=6, titlePadding=10)
                ),
                xOffset="gender:N",
                y=alt.Y(
                    f"{metric_col}:Q",
                    title=y_title,
                    scale=alt.Scale(domainMax=max_val * 1.20 if max_val > 0 else 100),
                    axis=alt.Axis(format=fmt, grid=True, titlePadding=10, labelPadding=6)
                ),
                color=alt.Color(
                    "gender:N",
                    scale=alt.Scale(
                        domain=["Female", "Male"],
                        range=["#ec4899", "#3b82f6"]
                    ),
                    legend=alt.Legend(title="Gender", orient="top", columns=2, titlePadding=6)
                ),
                opacity=alt.condition(hover, alt.value(1.0), alt.value(0.78)),
                tooltip=[
                    alt.Tooltip("age_group:N", title="Age Cohort"),
                    alt.Tooltip("gender:N", title="Gender"),
                    alt.Tooltip(f"{metric_col}:Q", title=y_title, format=t_fmt)
                ]
            )
            .add_params(hover)
            .properties(
                title=alt.TitleParams(
                    text=f"Meta Ad Library Targeted Age Cohorts: {county_name} ({dma})",
                    subtitle="Empirical ad delivery across voter age groups and gender demographics (Meta API)",
                    fontSize=14,
                    subtitleFontSize=11,
                    subtitleColor="#94a3b8"
                ),
                height=280
            )
        )

        text = (
            alt.Chart(agg)
            .mark_text(align="center", baseline="bottom", dy=-5, color="#f8fafc", fontSize=9.5, fontWeight="bold")
            .encode(
                x=alt.X("age_group:N", sort=valid_cohorts),
                xOffset="gender:N",
                y=alt.Y(f"{metric_col}:Q"),
                text=alt.Text(f"{metric_col}:Q", format=fmt)
            )
        )
        return chart + text
    else:
        # Age-only demographic delivery when gender data does not exist
        clean_demo = filtered[
            filtered["age_group"].isin(valid_cohorts) &
            filtered[metric_col].notna() &
            (filtered[metric_col] > 0)
        ].copy()

        if clean_demo.empty:
            return alt.Chart(pd.DataFrame({"msg": [f"No demographic delivery records for {county_name} ({dma})"]})).mark_text(color="#94a3b8").encode(text="msg:N")

        agg = (
            clean_demo.groupby("age_group", as_index=False)[metric_col]
            .sum()
        )

        max_val = agg[metric_col].max() if not agg.empty else 1.0

        chart = (
            alt.Chart(agg)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color="#0668e1")
            .encode(
                x=alt.X(
                    "age_group:N",
                    sort=valid_cohorts,
                    title="Voter Age Cohort (Meta Ad Library)",
                    axis=alt.Axis(labelAngle=0, labelPadding=6, titlePadding=10)
                ),
                y=alt.Y(
                    f"{metric_col}:Q",
                    title=y_title,
                    scale=alt.Scale(domainMax=max_val * 1.20 if max_val > 0 else 100),
                    axis=alt.Axis(format=fmt, grid=True, titlePadding=10, labelPadding=6)
                ),
                tooltip=[
                    alt.Tooltip("age_group:N", title="Age Cohort"),
                    alt.Tooltip(f"{metric_col}:Q", title=y_title, format=t_fmt)
                ]
            )
            .properties(
                title=alt.TitleParams(
                    text=f"Meta Ad Library Targeted Age Cohorts: {county_name} ({dma})",
                    subtitle="Empirical ad delivery across voter age groups (Meta API)",
                    fontSize=14,
                    subtitleFontSize=11,
                    subtitleColor="#94a3b8"
                ),
                height=280
            )
        )

        text = (
            alt.Chart(agg)
            .mark_text(align="center", baseline="bottom", dy=-5, color="#f8fafc", fontSize=9.5, fontWeight="bold")
            .encode(
                x=alt.X("age_group:N", sort=valid_cohorts),
                y=alt.Y(f"{metric_col}:Q"),
                text=alt.Text(f"{metric_col}:Q", format=fmt)
            )
        )
        return chart + text


# Alias for backward compatibility
create_nc_market_share_chart = create_nc_pac_market_share_chart

