"""Chart factories return valid Vega-Lite, and the race-aware loaders behind the pages are consistent."""

import pandas as pd
import pytest

from campaign_intel.data import loaders as L
from campaign_intel.data.snapshot import has_table, read_table
from campaign_intel.viz import charts as C
from campaign_intel.viz.maps import _features, _signed_area, choropleth

needs_snapshot = pytest.mark.skipif(not L.snapshot_ready(), reason="snapshot not built")
THEMES = ["light", "dark"]


# ----------------------------------------------------------------------------- pure chart specs
@pytest.mark.parametrize("theme", THEMES)
def test_spending_chart_specs(theme):
    wk = pd.DataFrame({"week_start": pd.to_datetime(["2026-09-06", "2026-09-06", "2026-09-13"]),
                       "side_group": ["Dem side", "GOP side", "Dem side"], "spend": [10.0, 8.0, 15.0]})
    assert "layer" in C.weekly_sides(wk, theme).to_dict()
    C.ranked_bars(pd.DataFrame({"advertiser": ["A", "B"], "spend": [5.0, 3.0], "side_group": ["Dem side", "GOP side"]}),
                  "advertiser", "spend", theme).to_dict()
    C.side_pair_bars(pd.DataFrame({"channel": ["YouTube"] * 2, "share": [0.4, 0.6],
                                   "side_group": ["Dem side", "GOP side"]}), "channel", "share", theme).to_dict()
    C.channel_weeks(pd.DataFrame({"week_start": pd.to_datetime(["2026-09-06"] * 2),
                                  "channel": ["YouTube", "Google Search"], "spend": [1.0, 2.0]}), theme).to_dict()


def test_side_colours_follow_party():
    """Democrats are always the Dem token and Republicans the Rep token, in both themes."""
    from campaign_intel.ui.styles import get_tokens
    for theme in THEMES:
        s = C.side_scale(theme).to_dict()
        t = get_tokens(theme)
        assert dict(zip(s["domain"], s["range"])) == {"Democrats": t["dem"], "Republicans": t["rep"]}


def test_district_board_spec():
    df = pd.DataFrame({"label": ["CD-1", "CD-13"], "dem_candidate": ["A", "B"], "rep_candidate": ["C", "D"],
                       "dem_margin_pct": [-2.0, -6.0], "result26_margin_pct": [1.5, -3.0], "holder_2024": ["D", "R"]})
    assert len(C.district_board(df, "light").to_dict()["layer"]) == 5


def test_map_rings_wound_for_d3():
    for ut in ("cd", "county"):
        for f in _features(ut):
            g = f["geometry"]
            polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
            for poly in polys:
                assert _signed_area(poly[0]) < 0  # exterior clockwise


# ----------------------------------------------------------------------------- loader helpers
def test_lean_and_margin_labels():
    assert L.lean_label(1.0) == "Toss-up"
    assert L.lean_label(-5.0) == "Lean R"
    assert L.lean_label(10.0) == "Likely D"
    assert L.lean_label(-20.0) == "Safe R"
    assert L.fmt_margin(-3.24) == "R +3.2"
    assert L.fmt_margin(0.5) == "D +0.5"
    assert L.fmt_money(2_500_000) == "$2.5M" and L.fmt_money(12_000) == "$12K"


def test_path_to_win_math():
    pt = pd.DataFrame({"party": ["Dem", "Rep", "Unaffiliated"], "reg24": [1000.0, 1000.0, 1000.0],
                       "turnout22": [0.5, 0.6, 0.4]})
    p = L.path_to_win(-2.0, 1500, pt)  # 2 points behind in a 1,500-voter race -> 30 votes short
    assert p["gap"] == pytest.approx(30)
    assert p["dems_skipped"] == pytest.approx(500)
    assert p["mobilize_share"] == pytest.approx(30 / 500)
    assert p["una_points"] == pytest.approx(30 / 400 * 100)
    ahead = L.path_to_win(4.0, 1500, pt)
    assert ahead["gap"] < 0 and ahead["mobilize_share"] == 0.0


# ----------------------------------------------------------------------------- snapshot-backed
@needs_snapshot
@pytest.mark.parametrize("race,n", [("senate", 100), ("house", 14)])
def test_regions_and_choropleth(race, n):
    u = L.load_regions(race)
    assert len(u) == n and u["unit_id"].is_unique
    assert u["dem_margin_pct"].between(-100, 100).all()
    for theme in THEMES:
        choropleth(L.unit_type(race), u, "dem_margin_pct", "Margin", theme=theme, highlight=u["unit_id"].iloc[0]).to_dict()


@needs_snapshot
def test_every_ad_is_attributed_to_one_race():
    a = L.load_ads()
    assert set(a["race"].unique()) <= {"senate", "house", "other"}


@needs_snapshot
@pytest.mark.parametrize("race", ["senate", "house"])
def test_spend_summary_consistent(race):
    s = L.spend_summary(race)
    assert s["partisan"] == pytest.approx(s["dem"] + s["gop"])
    assert 0 <= s["dem_share"] <= 1
    tops = L.top_advertisers(race, n=1000)
    assert tops["spend"].sum() == pytest.approx(s["partisan"], rel=1e-6)
    ch = L.channel_by_side(race)
    assert ch.groupby("side_group")["share"].sum().round(6).eq(1).all()


@needs_snapshot
def test_region_ad_spend_never_exceeds_race_total():
    for race in ("senate", "house"):
        r = L.load_region_ad_spend(race)
        r = r[r["side_group"].isin(L.SIDES)]
        assert r["spend"].sum() <= L.spend_summary(race)["partisan"] * 1.0001


@needs_snapshot
@pytest.mark.parametrize("dim", ["age", "race", "gender"])
def test_statewide_demographics_reconcile(dim):
    """Every breakdown sums to the same statewide registration."""
    d = L.load_demographics("state", "NC", dim)
    base = L.load_demographics("state", "NC", "age")["reg24"].sum()
    assert d["reg24"].sum() == pytest.approx(base)
    assert (d["voted22"] <= d["reg22"] + 1).all()


@needs_snapshot
@pytest.mark.skipif(not has_table("house_races"), reason="snapshot not built")
def test_house_races_cover_all_districts():
    h = read_table("house_races")
    assert sorted(h["district_num"].astype(int)) == list(range(1, 15))
