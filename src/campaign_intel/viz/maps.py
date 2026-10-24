"""
Altair choropleth map factory using GeoJSON and mark_geoshape per §11.2 and §11.3.
Supports diverging margin scales, sequential intensity, swing outlines, and drill-down.
"""

import json

import altair as alt
import pandas as pd

from campaign_intel.config import GEO_DIR
from campaign_intel.ui.styles import get_tokens


def choropleth(
    unit_type: str,
    df_metrics: pd.DataFrame,
    metric_col: str,
    metric_label: str,
    is_diverging: bool = True,
    theme: str = "light",
) -> alt.Chart:
    """
    Renders Altair geoshape choropleth with metrics embedded into feature properties.
    """
    t = get_tokens(theme)
    geo_file = GEO_DIR / f"{unit_type}.geojson"

    if not geo_file.exists():
        # Fallback to county if specific district geojson not found
        geo_file = GEO_DIR / "county.geojson"

    with open(geo_file, "r") as f:
        geo_data = json.load(f)

    # Build metric lookup by unit_id
    metrics_map = {}
    if df_metrics is not None and not df_metrics.empty and "unit_id" in df_metrics.columns:
        for _, row in df_metrics.iterrows():
            metrics_map[str(row["unit_id"])] = {
                "val": float(row.get(metric_col, 0.0)),
                "name": str(row.get("name", row["unit_id"])),
                "is_swing": bool(abs(float(row.get("dem_margin_pct", 99.0))) <= 5.0) if "dem_margin_pct" in row else False
            }

    # Embed into features
    enriched_features = []
    for feat in geo_data.get("features", []):
        uid = str(feat.get("properties", {}).get("unit_id") or feat.get("id"))
        metric_info = metrics_map.get(uid, {"val": 0.0, "name": feat.get("properties", {}).get("name", uid), "is_swing": False})
        feat["properties"]["metric_val"] = metric_info["val"]
        feat["properties"]["unit_name"] = metric_info["name"]
        feat["properties"]["is_swing"] = metric_info["is_swing"]
        feat["properties"]["unit_id"] = uid
        enriched_features.append(feat)

    feature_collection = {"type": "FeatureCollection", "features": enriched_features}

    # Color scale definition
    if is_diverging:
        scale = alt.Scale(
            domain=[-25, 0, 25],
            range=[t["rep"], "#F7F7F7" if theme == "light" else "#2A2F3A", t["dem"]]
        )
    else:
        scale = alt.Scale(scheme="greens" if theme == "light" else "tealblues")

    # Base geoshape layer
    base = alt.Chart(alt.Data(values=feature_collection["features"])).mark_geoshape(
        stroke=t["surface"],
        strokeWidth=1.1
    ).encode(
        color=alt.Color(
            "properties.metric_val:Q",
            scale=scale,
            title=metric_label,
            legend=alt.Legend(orient="bottom", gradientLength=220)
        ),
        tooltip=[
            alt.Tooltip("properties.unit_name:N", title="Region"),
            alt.Tooltip("properties.unit_id:N", title="Unit ID"),
            alt.Tooltip("properties.metric_val:Q", title=metric_label, format="+.1f" if is_diverging else ",.0f"),
        ]
    ).project(type="identity", reflectY=True).properties(height=420)

    # Swing outline layer
    if is_diverging:
        swing_layer = alt.Chart(alt.Data(values=feature_collection["features"])).mark_geoshape(
            filled=False,
            stroke=t["swing"],
            strokeWidth=2.2
        ).transform_filter(
            "datum.properties.is_swing == true"
        ).project(type="identity", reflectY=True)
        return (base + swing_layer)

    return base
