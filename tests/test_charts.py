"""Chart factories return valid Vega-Lite; fidelity badges are mandatory (UI_Design.md §11.4)."""

import pandas as pd
import pytest

from campaign_intel.data.snapshot import has_table, read_table
from campaign_intel.ui.components import chart_card_header, kpi_card
from campaign_intel.viz.charts import (
    area_with_band,
    grouped_bar,
    outcome_histogram,
    stacked_weeks,
    tornado,
)
from campaign_intel.viz.maps import _features, _signed_area, choropleth


def test_area_with_band_spec():
    df = pd.DataFrame({"week_start": pd.to_datetime(["2026-09-06", "2026-09-13"]), "mid": [10, 15], "lo": [8, 12],
                       "hi": [12, 18], "side_group": ["Dem side", "Dem side"]})
    spec = area_with_band(df, "week_start", "mid", "lo", "hi", "side_group").to_dict()
    assert len(spec["layer"]) >= 2


def test_misc_specs():
    grouped_bar(pd.DataFrame({"g": ["a"], "v": [1.0], "s": ["x"]}), "g", "v", "s").to_dict()
    stacked_weeks(pd.DataFrame({"week": [1, 2], "channel": ["meta", "ctv"], "dollars": [1.0, 2.0]})).to_dict()
    tornado(pd.DataFrame({"parameter": ["p"], "low": [0.1], "high": [0.3], "base": [0.2]})).to_dict()
    outcome_histogram(pd.DataFrame({"bin_start": [-1, 0], "bin_end": [0, 1], "count": [3, 4],
                                    "series": ["With plan", "Baseline (no spend)"], "is_win": [False, True]})).to_dict()


def test_map_rings_wound_for_d3():
    for f in _features("cd"):
        g = f["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        for poly in polys:
            assert _signed_area(poly[0]) < 0  # exterior clockwise


@pytest.mark.skipif(not has_table("units_cd"), reason="snapshot not built")
def test_choropleth_spec():
    choropleth("cd", read_table("units_cd"), "dem_margin_pct", "Margin").to_dict()


def test_fidelity_badge_mandatory():
    with pytest.raises(TypeError):
        kpi_card(label="Test", value="100", fidelity=None)
    with pytest.raises(TypeError):
        chart_card_header(title="Test", fidelity=None)
