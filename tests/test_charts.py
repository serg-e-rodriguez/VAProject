"""
Altair Chart Spec Tests per PROJECT_DESIGN.md §12.
"""

import pandas as pd
import pytest

from campaign_intel.ui.components import chart_card_header, kpi_card
from campaign_intel.viz.charts import area_with_band, grouped_bar


def test_area_with_band_spec():
    df = pd.DataFrame({
        "week_start": ["2026-09-01", "2026-09-08"],
        "spend_mid": [10000, 15000],
        "spend_low": [8000, 12000],
        "spend_high": [12000, 18000],
        "side": ["Dem", "Dem"]
    })
    chart = area_with_band(df, "week_start", "spend_mid", "spend_low", "spend_high", "side")
    spec = chart.to_dict()
    assert "layer" in spec
    assert len(spec["layer"]) >= 2


def test_grouped_bar_spec():
    df = pd.DataFrame({
        "cohort": ["18-24", "25-34"],
        "share": [40.5, 55.2],
        "platform": ["Meta", "Meta"]
    })
    chart = grouped_bar(df, "cohort", "share", "platform")
    spec = chart.to_dict()
    assert spec["mark"]["type"] == "bar"


def test_fidelity_badge_mandatory():
    # Calling kpi_card or chart_card_header without fidelity must raise TypeError per §11.4
    with pytest.raises(TypeError):
        kpi_card(label="Test", value="100", fidelity=None)

    with pytest.raises(TypeError):
        chart_card_header(title="Test", fidelity=None)
