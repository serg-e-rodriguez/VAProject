"""
War Room Model Tests per PROJECT_DESIGN.md §12.
"""

import pandas as pd

from campaign_intel.model.assumptions import load_defaults
from campaign_intel.model.engine import RaceContext, simulate
from campaign_intel.model.optimizer import optimize
from campaign_intel.processing.crosswalk import get_district_baselines


def test_zero_spend_equals_baseline():
    ctx = RaceContext(
        scope="statewide",
        unit_type="cd",
        target_unit=None,
        weeks=8,
        budget=2_000_000.0,
        units=get_district_baselines("cd")
    )
    a = load_defaults()
    empty_alloc = pd.DataFrame(columns=["unit_id", "channel", "audience", "week", "dollars"])
    res = simulate(empty_alloc, ctx, a, n_draws=2000, seed=42)

    assert res.total_delta_votes == 0.0
    assert abs(res.win_prob - res.baseline_win_prob) < 0.001


def test_diminishing_marginal_returns():
    ctx = RaceContext(
        scope="statewide",
        unit_type="cd",
        target_unit=None,
        weeks=8,
        budget=2_000_000.0,
        units=get_district_baselines("cd")
    )
    a = load_defaults()

    alloc_10k = pd.DataFrame([{"unit_id": "CD13", "channel": "meta", "audience": "persuasion", "week": 8, "dollars": 10_000.0}])
    alloc_20k = pd.DataFrame([{"unit_id": "CD13", "channel": "meta", "audience": "persuasion", "week": 8, "dollars": 20_000.0}])

    res_1 = simulate(alloc_10k, ctx, a, n_draws=1000, seed=42)
    res_2 = simulate(alloc_20k, ctx, a, n_draws=1000, seed=42)

    # First $10k adds more than the second $10k
    first_10k_gain = res_1.total_delta_votes
    second_10k_gain = res_2.total_delta_votes - res_1.total_delta_votes

    assert first_10k_gain > 0
    assert second_10k_gain > 0
    assert first_10k_gain > second_10k_gain, "Saturation curve must exhibit diminishing marginal returns"


def test_simulation_determinism():
    ctx = RaceContext(
        scope="statewide",
        unit_type="cd",
        target_unit=None,
        weeks=8,
        budget=2_000_000.0,
        units=get_district_baselines("cd")
    )
    a = load_defaults()
    alloc = pd.DataFrame([{"unit_id": "CD1", "channel": "youtube", "audience": "persuasion", "week": 7, "dollars": 50_000.0}])

    res1 = simulate(alloc, ctx, a, n_draws=1000, seed=123)
    res2 = simulate(alloc, ctx, a, n_draws=1000, seed=123)

    assert res1.win_prob == res2.win_prob
    assert res1.total_delta_votes == res2.total_delta_votes


def test_optimizer_respects_budget():
    ctx = RaceContext(
        scope="statewide",
        unit_type="cd",
        target_unit=None,
        weeks=8,
        budget=50_000.0,
        units=get_district_baselines("cd")
    )
    a = load_defaults()
    empty = pd.DataFrame(columns=["unit_id", "channel", "audience", "week", "dollars"])

    rec_alloc, diff_df = optimize(empty, ctx, a, step=10_000.0)

    total_allocated = rec_alloc["dollars"].sum()
    assert total_allocated <= ctx.budget
    assert len(diff_df) > 0
