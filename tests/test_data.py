"""
Data and Processing Tests per PROJECT_DESIGN.md §12.
"""

from campaign_intel.processing.bands import parse_band
from campaign_intel.processing.crosswalk import get_county_baselines, get_district_baselines
from campaign_intel.processing.survey import compute_platform_use_by_age
from campaign_intel.processing.themes import classify_text, is_fundraising


def test_county_baselines_integrity():
    df_county = get_county_baselines()
    assert len(df_county) == 100, "NC must have exactly 100 counties"
    assert (df_county["dem_votes"] >= 0).all()
    assert (df_county["rep_votes"] >= 0).all()
    assert (df_county["total_votes"] > 0).all()
    assert (df_county["margin_votes"] == (df_county["dem_votes"] - df_county["rep_votes"])).all()


def test_district_baselines_totals():
    df_cd = get_district_baselines("cd")
    df_county = get_county_baselines()

    assert len(df_cd) == 14, "NC has 14 Congressional Districts"
    # Total votes should match statewide sum within rounding
    assert abs(df_cd["total_votes"].sum() - df_county["total_votes"].sum()) < 100


def test_band_parser():
    b1 = parse_band(1000, 5000)
    assert b1["low"] == 1000.0
    assert b1["high"] == 5000.0
    assert b1["mid"] == 3000.0
    assert not b1["open_ended"]

    b2 = parse_band(10000, None)
    assert b2["low"] == 10000.0
    assert b2["mid"] == 15000.0  # 1.5x
    assert b2["open_ended"]


def test_theme_classification():
    text = "We need to lower grocery prices and gas inflation to protect hardworking families."
    themes = classify_text(text)
    assert "economy" in themes

    donate_text = "Please chip in $5 to our ActBlue donation page before the midnight deadline!"
    assert is_fundraising(donate_text)


def test_cces_weighted_benchmarks():
    df_plat = compute_platform_use_by_age()
    if not df_plat.empty:
        assert "pct" in df_plat.columns
        assert "ci_low" in df_plat.columns
        assert "ci_high" in df_plat.columns
        assert (df_plat["pct"] >= 0).all()
        assert (df_plat["pct"] <= 100).all()
