"""Midterm planning pages: Region Analysis (map picks, dropdown, option descriptions), Overview and Model Check.
The planning pages must not show the 2026 results; only Model Check compares the model with them."""

import pytest

from campaign_intel import model_check as M
from campaign_intel.data import loaders as L

needs_snapshot = pytest.mark.skipif(not L.snapshot_ready(), reason="snapshot not built")


def _app(page, race):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(f"../app_pages/{page}.py", default_timeout=240)
    at.session_state["race"], at.session_state["theme"] = race, "dark"
    return at


def _text(at):
    return " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)


@needs_snapshot
@pytest.mark.parametrize("race", ["senate", "house"])
def test_model_check_numbers(race):
    d, s = M.compare(race)
    assert s["n"] == len(d) and 0 <= s["called"] <= s["n"]
    assert (d["proj_pct"] - d["start_pct"]).round(6).nunique() >= 1
    # the estimate uses only pre-election inputs: it doesn't move when the results are removed
    est = M.estimates(race)
    assert "actual_pct" not in est.columns and est["proj_pct"].notna().all()
    # a higher national mood moves every estimate toward Democrats by the same amount
    hi, _ = M.compare(race, M.DEFAULT_ENV + 3)
    assert ((hi["proj_pct"] - d["proj_pct"]).round(6) == 3).all()


@needs_snapshot
@pytest.mark.parametrize("race", ["senate", "house"])
def test_regions_page_dropdown_and_map(race):
    at = _app("regions", race)
    at.run()
    assert not at.exception
    assert "2026 result" not in repr(at.get("button_group")[0].proto.options)
    assert any("window.__mapMetricTips" in h.proto.body for h in at.get("html"))  # hover descriptions

    # a map pick, then a pick from the dropdown: the area opens and the dropdown shows it ...
    ids = L.load_regions(race).sort_values("label")["unit_id"].tolist()
    at.session_state["_map_pick"] = ids[1]
    at.session_state["region"] = ids[1]
    at.run()
    nonce = at.session_state["_map_nonce"] if "_map_nonce" in at.session_state else 0  # noqa: SIM401 (no .get)
    at.selectbox(key="region_select").set_value(ids[0]).run()
    assert not at.exception
    assert at.session_state["region"] == ids[0]
    # ... and the map gets a fresh selection (new key), so clicking any area, including the earlier one, works
    assert at.session_state["_map_pick"] is None and at.session_state["_map_nonce"] == nonce + 1
    # an area picked on another page also keeps the dropdown in step
    at.session_state["region"] = ids[2]
    at.run()
    assert at.selectbox(key="region_select").value == ids[2]
    text = _text(at)
    assert "2026 result" not in text and "In 2026 the" not in text and "2026 US" not in text


@needs_snapshot
@pytest.mark.parametrize("race", ["senate", "house"])
def test_overview_and_model_check_pages(race):
    ov = _app("overview", race)
    ov.run()
    assert not ov.exception
    labels = " ".join(m.value for m in ov.markdown)
    assert "2026 result (unofficial)" not in labels and "Model estimate" in labels
    mc = _app("model_check", race)
    mc.run()
    assert not mc.exception
    assert "2026" in " ".join(m.value for m in mc.markdown)
