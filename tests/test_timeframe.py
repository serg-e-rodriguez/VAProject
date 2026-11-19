"""Sidebar timeframe: ad data from Google (BigQuery) and Meta is limited to it, and empty timeframes are marked."""

import datetime as dt

import pandas as pd
import pytest

from campaign_intel.data import ad_links
from campaign_intel.data import loaders as L
from campaign_intel.data.snapshot import read_table

needs_snapshot = pytest.mark.skipif(not L.snapshot_ready(), reason="snapshot not built")
EMPTY = (pd.Timestamp("2024-01-01"), pd.Timestamp("2024-03-01"))


@pytest.fixture(autouse=True)
def _stub_links(monkeypatch):
    monkeypatch.setattr(ad_links, "check_ad_link", lambda *a, **k: ("https://example.org/ok", "checked"))


def _with_tf(monkeypatch, tf):
    import streamlit as st

    monkeypatch.setattr(st, "session_state", {"timeframe": tf} if tf else {})


@needs_snapshot
@pytest.mark.parametrize("race", ["senate", "house"])
def test_default_timeframe_matches_the_stored_snapshot(race, monkeypatch):
    _with_tf(monkeypatch, None)
    new = L.load_region_ad_spend(race)
    old = read_table("region_ad_spend")
    old = old[(old["unit_type"] == L.unit_type(race)) & (old["race"] == race)]
    assert new["spend"].sum() == pytest.approx(old["spend"].sum(), rel=1e-9)
    assert L.coverage(race)["any"]


@needs_snapshot
def test_spend_is_limited_to_the_timeframe(monkeypatch):
    _with_tf(monkeypatch, (pd.Timestamp("2026-09-01"), pd.Timestamp("2026-09-30")))
    a = L.load_ads("senate")
    assert len(a) and (a["start"] <= "2026-09-30").all() and (a["end"] >= "2026-09-01").all()
    assert (a["w_nc_spend_mid"] <= a["nc_spend_mid"] + 1e-9).all()
    w = L.weekly_by_side("senate")
    assert w["week_start"].min() >= pd.Timestamp("2026-08-30") and w["week_start"].max() <= pd.Timestamp("2026-09-30")
    # weekly spend = pro-rated ad spend (days inside the window), up to the trimmed partial last week
    assert w["spend"].sum() <= a[a["side_group"].isin(L.SIDES)]["w_nc_spend_mid"].sum() + 1


@needs_snapshot
@pytest.mark.parametrize("race", ["senate", "house"])
def test_empty_timeframe_is_marked_not_crashed(race, monkeypatch):
    _with_tf(monkeypatch, EMPTY)
    c = L.coverage(race)
    assert not c["any"] and not c["google"]["has_data"] and not c["meta"]["has_data"]
    assert c["google"]["stored_ads"] > 0  # the snapshot has data, just not in this timeframe
    assert L.load_ads(race).empty and L.weekly_by_side(race).empty and L.audience_by_side(race).empty
    s = L.spend_summary(race)
    assert s["partisan"] == 0 and L.went_dark(s) is None


@needs_snapshot
@pytest.mark.parametrize("page", ["overview", "opponent", "regions"])
def test_pages_mark_missing_data(page):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(f"../app_pages/{page}.py", default_timeout=240)
    at.session_state["race"], at.session_state["theme"] = "senate", "dark"
    at.session_state["region"] = "37119"
    at.session_state["timeframe"] = EMPTY
    at.run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "No data found" in text and "nan" not in text.replace("Financ", "")


@needs_snapshot
def test_sidebar_picker_sets_checks_and_resets():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("../app.py", default_timeout=240)
    at.session_state["race"], at.session_state["theme"] = "senate", "dark"
    at.run()
    assert not at.exception
    side = " ".join(m.value for m in at.sidebar.markdown)
    assert "Google ads · BigQuery" in side and "Meta Ad Library" in side and "No data found" not in side

    at.date_input(key="tf_pick").set_value((dt.date(2024, 1, 1), dt.date(2024, 3, 1))).run()
    assert not at.exception
    assert at.session_state["timeframe"] == EMPTY
    side = " ".join(m.value for m in at.sidebar.markdown)
    assert side.count("No data found in this timeframe") == 2

    at.button(key="tf_reset").click().run()
    assert at.session_state["timeframe"] == L.default_timeframe()
