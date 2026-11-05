"""
Altair choropleths (mark_geoshape) over the committed simplified GeoJSON (UI_Design.md §11.2).
Shapes: TIGER 2024 congressional (119th Congress) and 2024 state legislative maps, which are the
lines the 2024 precinct results — and therefore every district number in the app — were cast on.
"""

from __future__ import annotations

import copy
import json
from functools import lru_cache

import altair as alt
import pandas as pd

from campaign_intel.config import GEO_DIR
from campaign_intel.ui.styles import get_tokens


def _signed_area(ring) -> float:
    return sum(x1 * y2 - x2 * y1 for (x1, y1, *_), (x2, y2, *_) in zip(ring, ring[1:] + ring[:1])) / 2


def _rewind(geom: dict) -> dict:
    """d3-geo (Vega) wants exterior rings CLOCKWISE and holes counter-clockwise — the reverse of
    RFC 7946. Wrong winding makes a polygon cover the whole globe (a grey box)."""
    def fix(poly):
        out = []
        for i, ring in enumerate(poly):
            cw = _signed_area(ring) < 0
            want_cw = i == 0
            out.append(ring if cw == want_cw else ring[::-1])
        return out
    if geom["type"] == "Polygon":
        return {"type": "Polygon", "coordinates": fix(geom["coordinates"])}
    if geom["type"] == "MultiPolygon":
        return {"type": "MultiPolygon", "coordinates": [fix(p) for p in geom["coordinates"]]}
    return geom


@lru_cache(maxsize=8)
def _features(unit_type: str) -> tuple:
    geo = json.loads((GEO_DIR / f"{unit_type}.geojson").read_text())
    return tuple({**f, "geometry": _rewind(f["geometry"])} for f in geo["features"])


def choropleth(unit_type: str, df_metrics: pd.DataFrame, metric_col: str, metric_label: str,
               scale: str = "diverging", theme: str = "light", fmt: str = ",.0f",
               extra_tooltips: list[tuple[str, str, str]] | None = None, highlight: str | None = None,
               swing_pts: float | None = 5.0, height: int = 420, selectable: bool = True,
               domain_max: float | None = None) -> alt.Chart:
    """
    scale: 'diverging' (Dem blue / GOP red around 0) or 'sequential' (one hue, light->dark).
    extra_tooltips: [(column, title, d3-format)] added to the tooltip.
    """
    t = get_tokens(theme)
    cols = ["unit_id", "name", metric_col] + [c for c, _, _ in (extra_tooltips or [])]
    if "dem_margin_pct" in df_metrics.columns and "dem_margin_pct" not in cols:
        cols.append("dem_margin_pct")
    lookup = df_metrics[[c for c in dict.fromkeys(cols) if c in df_metrics.columns]].set_index("unit_id").to_dict("index")

    feats = []
    for f in _features(unit_type):
        f = copy.copy(f)
        uid = str(f["properties"]["unit_id"])
        row = lookup.get(uid, {})
        props = {"unit_id": uid, "unit_name": row.get("name", f["properties"].get("name", uid)),
                 "metric": row.get(metric_col), "is_swing": bool(swing_pts is not None and
                                                               abs(row.get("dem_margin_pct", 99) or 99) <= swing_pts),
                 "is_highlight": uid == highlight}
        for c, _, _ in extra_tooltips or []:
            props[c] = row.get(c)
        f["properties"] = props
        f["unit_id"] = uid  # top-level copy so click selections return a plain field
        feats.append(f)

    if scale == "diverging":
        m = domain_max or max(5.0, float(df_metrics[metric_col].abs().quantile(0.95)))
        color_scale = alt.Scale(domain=[-m, 0, m], range=[t["rep"], t["border"], t["dem"]], clamp=True)
    else:
        lo = "#E8EEFC" if theme == "light" else "#232B3D"
        color_scale = alt.Scale(range=[lo, t["dem"]], zero=False, nice=False)

    tips = [alt.Tooltip("properties.unit_name:N", title="Area"), alt.Tooltip("properties.unit_id:N", title="ID"),
            alt.Tooltip("properties.metric:Q", title=metric_label, format=fmt)]
    tips += [alt.Tooltip(f"properties.{c}:Q", title=title, format=f) for c, title, f in (extra_tooltips or [])]

    sel = alt.selection_point(fields=["unit_id"], name="unit_pick", on="click")
    data = alt.Data(values=feats)
    base = alt.Chart(data).mark_geoshape(stroke=t["surface"], strokeWidth=0.8).encode(
        color=alt.Color("properties.metric:Q", scale=color_scale, title=metric_label,
                        legend=alt.Legend(orient="bottom", gradientLength=240, format=fmt.replace(",.0f", "~s"))),
        tooltip=tips,
    ).project(type="mercator")
    if selectable:
        base = base.add_params(sel).encode(opacity=alt.condition(sel, alt.value(1.0), alt.value(0.55)))
    layers = [base]
    if swing_pts is not None:
        layers.append(alt.Chart(data).mark_geoshape(filled=False, stroke=t["swing"], strokeWidth=2)
                      .transform_filter("datum.properties.is_swing").project(type="mercator"))
    if highlight:
        layers.append(alt.Chart(data).mark_geoshape(filled=False, stroke=t["text_primary"], strokeWidth=2.5)
                      .transform_filter("datum.properties.is_highlight").project(type="mercator"))
    return alt.layer(*layers).properties(height=height)
