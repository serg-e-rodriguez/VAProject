"""War Room model properties (PROJECT_DESIGN.md §12): monotone, saturating, reproducible, fast."""

import time

import numpy as np
import pandas as pd
import pytest

from campaign_intel.data.snapshot import has_table, read_table
from campaign_intel.model.assumptions import Assumptions, apply_preset, load_defaults
from campaign_intel.model.engine import RaceContext, expected_deltas, simulate
from campaign_intel.model.optimizer import optimize


def toy_units(n=4):
    return pd.DataFrame({
        "unit_id": [f"CD{i}" for i in range(1, n + 1)], "name": [f"D{i}" for i in range(1, n + 1)],
        "baseline_margin_votes": np.linspace(-20_000, 20_000, n), "expected_turnout": [250_000.0] * n,
        "persuasion_universe": [80_000.0] * n, "mobilization_universe": [40_000.0] * n, "opp_share": [0.5] * n,
        "dem_margin_pct": np.linspace(-8, 8, n),
    })


def line(unit="CD1", ch="meta", aud="persuasion", week=8, dollars=50_000.0):
    return pd.DataFrame([{"unit_id": unit, "channel": ch, "audience": aud, "week": week, "dollars": dollars}])


@pytest.fixture
def ctx():
    return RaceContext("statewide", "cd", None, 8, 2_000_000, toy_units())


@pytest.fixture
def a():
    return load_defaults(use_observed_cpm=False)


def test_zero_plan_equals_baseline(ctx, a):
    r = simulate(None, ctx, a, n_draws=2000)
    assert r.win_prob == r.baseline_win_prob
    assert r.total_delta_votes == 0


def test_more_money_more_votes_with_diminishing_returns(ctx, a):
    v = [expected_deltas(line(dollars=d), ctx, a)["delta_votes"].sum() for d in (25e3, 50e3, 100e3, 200e3)]
    assert all(x < y for x, y in zip(v, v[1:]))                       # monotone
    gains = np.diff([0, *v])
    assert all(g1 > g2 for g1, g2 in zip(gains[1:], gains[2:]))       # concave


def test_late_money_beats_early_money(ctx, a):
    early = expected_deltas(line(week=1), ctx, a)["delta_votes"].sum()
    late = expected_deltas(line(week=8), ctx, a)["delta_votes"].sum()
    assert late > early > 0


def test_plan_raises_win_probability_and_is_reproducible(ctx, a):
    plan = line(dollars=500_000)
    r1, r2 = simulate(plan, ctx, a, n_draws=3000, seed=7), simulate(plan, ctx, a, n_draws=3000, seed=7)
    assert r1.win_prob >= r1.baseline_win_prob
    assert r1.win_prob == r2.win_prob
    lo, hi = r1.win_prob_interval
    assert lo <= hi


def test_district_scope_counts_only_target(a):
    ctx = RaceContext("district", "cd", "CD2", 8, 2e6, toy_units())
    r = simulate(line(unit="CD1"), ctx, a, n_draws=1000)
    assert r.total_delta_votes == 0  # money outside the target district doesn't count


def test_optimizer_spends_budget_and_respects_locks(ctx, a):
    locked = line(unit="CD4", ch="ctv", dollars=100_000)
    rec, diff = optimize(locked, ctx, a, step=10_000, locks=locked, rebuild=True, cap_mult=50)
    assert rec["dollars"].sum() == pytest.approx(ctx.budget, abs=1)
    kept = rec[(rec.unit_id == "CD4") & (rec.channel == "ctv") & (rec.week == 8)]["dollars"].sum()
    assert kept >= 100_000
    assert (diff["marginal_votes"] > 0).all()


def test_optimizer_channel_filter(ctx, a):
    rec, _ = optimize(None, ctx, a, channels=["meta"])
    assert set(rec["channel"]) == {"meta"}


def test_presets_are_ordered(a):
    cons, opt = apply_preset(a, "conservative"), apply_preset(a, "optimistic")
    assert cons.persuasion_p[1] < a.persuasion_p[1] < opt.persuasion_p[1]
    assert Assumptions.from_dict(opt.to_dict()) == opt


@pytest.mark.skipif(not has_table("units_hd"), reason="snapshot not built")
def test_optimizer_fast_on_120_districts(a):
    u = read_table("units_hd").assign(opp_share=0.4)
    ctx = RaceContext("chamber", "hd", None, 8, 2_000_000, u)
    t = time.time()
    rec, _ = optimize(None, ctx, a)
    assert time.time() - t < 5
    assert rec["dollars"].sum() == pytest.approx(2_000_000, abs=1)
