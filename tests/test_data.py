"""
Data integrity tests: the snapshot must match official NCSBE totals and every geography must
reconcile (PROJECT_DESIGN.md §12). Requires a built snapshot (data/cache).
"""

import pandas as pd
import pytest

from campaign_intel.data.snapshot import has_table, read_table
from campaign_intel.processing.bands import parse_band
from campaign_intel.processing.crosswalk import get_county_baselines
from campaign_intel.processing.survey import compute_platform_use_by_age
from campaign_intel.processing.themes import classify_text, is_fundraising

needs_snapshot = pytest.mark.skipif(not has_table("units_cd"), reason="snapshot not built")
COUNTS = {"cd": 14, "sd": 50, "hd": 120, "county": 100}


@needs_snapshot
def test_official_2024_presidential_totals():
    sw = read_table("statewide").iloc[0]
    # NCSBE certified 2024 general: Harris 2,715,375; Trump 2,898,423
    assert sw["pres24_dem"] == 2_715_375
    assert sw["pres24_rep"] == 2_898_423


@needs_snapshot
@pytest.mark.parametrize("geo", list(COUNTS))
def test_geographies_reconcile(geo):
    u = read_table(f"units_{geo}")
    sw = read_table("statewide").iloc[0]
    assert len(u) == COUNTS[geo]
    assert u["unit_id"].is_unique
    assert abs(u["total_votes_2024"].sum() - sw["pres24_total"]) <= 5
    assert abs(u["registered_voters"].sum() - sw["registered_2024"]) <= 5
    assert abs(u["expected_turnout"].sum() - sw["voted22_total"]) <= 5
    assert abs(u["actual26_total"].sum() - sw["sen26_total"]) <= 5
    assert (u["persuasion_universe"] > 0).all() and (u["mobilization_universe"] > 0).all()
    assert (u["persuasion_universe"] <= u["registered_voters"]).all()


@needs_snapshot
def test_county_baseline_matches_medsl_2022_counts():
    # NCSBE 2022 ballots per county should be close to MEDSL 2022 Senate votes (undervotes differ slightly)
    medsl = get_county_baselines().set_index("unit_id")["total_votes"]
    u = read_table("units_county").set_index("unit_id")["expected_turnout"]
    ratio = (u / medsl).dropna()
    assert len(ratio) == 100
    assert ratio.between(0.97, 1.06).all()


@needs_snapshot
def test_ads_are_nc_apportioned():
    ads = read_table("ads_unified")
    assert (ads["nc_spend_mid"] <= ads["spend_mid"] + 1e-6).all()
    assert ads["side_group"].isin(["Dem side", "GOP side", "Nonpartisan / other", "Unclassified"]).all()


def test_band_parser():
    b = parse_band(1000, 5000)
    assert (b["low"], b["high"], b["mid"], b["open_ended"]) == (1000.0, 5000.0, 3000.0, False)
    b2 = parse_band(10000, None)
    assert b2["open_ended"] and b2["mid"] == 15000.0


def test_theme_classifier_uses_word_boundaries():
    assert classify_text("Prices are up at the office") == ["economy"]   # 'ice' must not match
    assert "immigration" in classify_text("ICE raids in Charlotte")
    assert "abortion" in classify_text("Protect abortion rights")
    assert is_fundraising("Chip in $5", "secure.actblue.com")


def test_cces_weighted_ci():
    df = compute_platform_use_by_age()
    assert not df.empty
    assert (df["ci_low"] <= df["pct"]).all() and (df["pct"] <= df["ci_high"]).all()
    assert (df["n_unweighted"] >= 30).all()
    assert isinstance(df, pd.DataFrame)
