"""War Room glue (rewind, plan rows, value of a dollar, reveal) and its charts."""

import numpy as np
import pandas as pd
import pytest

from campaign_intel.data import loaders as L
from campaign_intel.model import warroom as WR
from campaign_intel.model.assumptions import load_defaults
from campaign_intel.model.engine import simulate
from campaign_intel.model.optimizer import optimize
from campaign_intel.viz import charts as C

needs_snapshot = pytest.mark.skipif(not L.snapshot_ready(), reason="snapshot not built")


@pytest.fixture
def a():
    return WR.with_env(load_defaults(), 5.0)


def test_weeks_left_and_timing():
    assert WR.weeks_left(WR.ELECTION_DAY - pd.Timedelta(weeks=8)) == 8
    assert WR.weeks_left(WR.ELECTION_DAY - pd.Timedelta(days=3)) == 1
    for t in WR.TIMINGS:
        w = WR.timing_weights(t, 6)
        assert w.sum() == pytest.approx(1) and (w > 0).all()
    assert WR.timing_weights("late", 6)[-1] > WR.timing_weights("late", 6)[0]
    assert WR.timing_weights("early", 6)[0] > WR.timing_weights("early", 6)[-1]


def test_spread_keeps_dollars():
    mix = WR.region_lines("CD1", 100_000, "both", ["meta", "youtube"])
    alloc = WR.spread(mix, "late", 5)
    assert alloc["dollars"].sum() == pytest.approx(100_000)
    assert set(alloc["week"]) == set(range(1, 6))
    assert WR.to_mix(alloc)["dollars"].sum() == pytest.approx(100_000)


def test_plan_rows_round_trip():
    mix = pd.concat([WR.region_lines("CD1", 200_000, "mobilization", ["youtube"]),
                     WR.region_lines("CD9", 50_000, "both", ["meta", "display"])], ignore_index=True)
    rows = WR.plan_rows(mix).set_index("unit_id")
    assert rows.loc["CD1", "goal"] == "mobilization" and rows.loc["CD1", "channels"] == ["youtube"]
    assert rows.loc["CD9", "goal"] == "both" and sorted(rows.loc["CD9", "channels"]) == ["display", "meta"]
    # budget-only edit rescales the exact mix; goal edit regenerates; dropped row disappears
    edited = pd.DataFrame([{"unit_id": "CD1", "budget": 400_000.0, "goal": "persuasion", "channels": ["youtube"]}])
    out = WR.apply_rows(mix, edited)
    assert out["dollars"].sum() == pytest.approx(400_000)
    assert set(out["audience"]) == {"persuasion"} and set(out["unit_id"]) == {"CD1"}
    same = WR.plan_rows(mix).assign(budget=lambda d: d["budget"] * 2)
    assert WR.apply_rows(mix, same)["dollars"].sum() == pytest.approx(500_000)


def test_diff_sentences():
    old = WR.region_lines("CD1", 100_000, "both", ["meta"])
    new = pd.concat([WR.region_lines("CD1", 150_000, "both", ["meta"]),
                     WR.region_lines("CD9", 80_000, "mobilization", ["youtube"])], ignore_index=True)
    d = WR.diff_sentences(old, new, {"CD1": "CD-1", "CD9": "CD-9"})
    assert [x["label"] for x in d] == ["CD-9", "CD-1"]
    assert d[0]["change"] == pytest.approx(80_000) and d[0]["goal"] == "Turn out Democrats"


@needs_snapshot
@pytest.mark.parametrize("race,mode", [("senate", "seats"), ("house", "seats"), ("house", "focus")])
def test_value_and_plan_raise_win_chance(race, mode, a):
    u = L.load_regions(race)
    ctx = WR.build_context(u, race, 8, 2e6, mode, target="CD1", a=a)
    v = WR.region_value(WR.empty_mix(), ctx, a, "late")
    assert len(v) == len(u) and (v["votes_per_step"] > 0).all() and (v["win_gain"] >= 0).all()
    if mode == "focus":
        assert (v.loc[v["unit_id"] != "CD1", "win_gain"] == 0).all()
    rec, _ = optimize(None, ctx, a, step=20_000, channels=WR.WR_CHANNELS)
    mix = WR.to_mix(rec)
    assert mix["dollars"].sum() == pytest.approx(2e6, rel=0.01)
    assert set(mix["channel"]) <= set(WR.WR_CHANNELS)
    r = simulate(WR.spread(mix, "late", 8), ctx, a, n_draws=1500)
    assert r.win_prob >= r.baseline_win_prob and r.total_delta_votes > 0
    # money already in a region lowers the value of the next $100K there (saturation)
    top = mix.groupby("unit_id")["dollars"].sum().idxmax()
    v2 = WR.region_value(mix, ctx, a, "late").set_index("unit_id")
    assert v2.loc[top, "votes_per_step"] < v.set_index("unit_id").loc[top, "votes_per_step"]
    for th in ("light", "dark"):
        C.win_chance_bar(r.baseline_win_prob, r.win_prob, *r.win_prob_interval, th).to_dict()
        C.outcome_dist(r.outcome_hist, th, ctx.majority - .5 if ctx.scope == "chamber" else 0, "x",
                       seats=ctx.scope == "chamber").to_dict()


@needs_snapshot
def test_house_seat_target_is_one_more_than_start(a):
    ctx = WR.build_context(L.load_regions("house"), "house", 8, 2e6, "seats", a=a)
    assert ctx.majority == WR.seats_at_start(ctx, a) + 1


@needs_snapshot
def test_projection_and_spend_as_of(a):
    u = L.load_regions("senate")
    ctx = WR.build_context(u, "senate", 8, 2e6, a=a)
    pj = WR.projection(ctx, a)
    assert np.allclose(pj["proj_votes"], pj["base_votes"])
    early, late = L.spend_as_of("senate", "2026-08-01"), L.spend_as_of("senate", "2026-10-01")
    assert late["dem"] + late["gop"] >= early["dem"] + early["gop"]
    assert early["dem"] + early["dem_after"] == pytest.approx(late["dem"] + late["dem_after"])
