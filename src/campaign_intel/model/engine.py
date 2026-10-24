"""
War Room Simulation Engine (Pure Python / NumPy) per §7.3, §7.6, and §7.9.
Runs vectorized Monte Carlo simulations to project margins and win probabilities.
"""

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from campaign_intel.model.assumptions import Assumptions


@dataclass(frozen=True)
class RaceContext:
    scope: Literal["statewide", "district"]
    unit_type: Literal["cd", "sd", "hd", "county"]
    target_unit: str | None
    weeks: int
    budget: float
    units: pd.DataFrame  # unit_id, name, baseline_margin_votes, total_votes, persuasion_universe, mobilization_universe, d_u, opp_share


@dataclass(frozen=True)
class SimulationResult:
    win_prob: float
    win_prob_interval: tuple[float, float]
    baseline_win_prob: float
    margin_hist: pd.DataFrame  # bin_start, bin_end, count, is_win
    delta_votes_by_unit: pd.DataFrame
    delta_votes_by_channel: pd.DataFrame
    total_delta_votes: float
    cost_per_net_vote: float


def compute_expected_marginal_votes(
    allocation: pd.DataFrame,
    ctx: RaceContext,
    a: Assumptions,
) -> tuple[dict[str, float], dict[str, float], float]:
    """
    Computes deterministic expected ΔV for each unit and channel using point estimates (modes).
    Returns (delta_by_unit, delta_by_channel, total_delta).
    """
    units_df = ctx.units.set_index("unit_id")
    delta_by_unit = {uid: 0.0 for uid in units_df.index}
    delta_by_channel = {c: 0.0 for c in ["meta", "youtube", "search", "display", "ctv"]}
    total_delta = 0.0

    if allocation is None or allocation.empty:
        return delta_by_unit, delta_by_channel, total_delta

    # Group allocation by unit, channel, audience, week
    alloc_clean = allocation.copy()
    alloc_clean["dollars"] = pd.to_numeric(alloc_clean["dollars"], errors="coerce").fillna(0.0)
    alloc_clean["week"] = pd.to_numeric(alloc_clean["week"], errors="coerce").fillna(1).astype(int)

    # Track impressions prior to compute saturation curve over combined spend
    # Group by (unit, audience)
    for (uid, aud), group in alloc_clean.groupby(["unit_id", "audience"]):
        if uid not in units_df.index:
            continue
        u_info = units_df.loc[uid]
        universe = float(u_info["persuasion_universe"] if aud == "persuasion" else u_info["mobilization_universe"])
        if universe <= 0:
            continue

        opp_share = float(u_info.get("opp_share", 0.5))
        d_u = float(u_info.get("d_u", 0.85))
        opp_factor = 1.0 / (1.0 + a.opp_lambda * opp_share)

        # Iterate over line items
        prior_impressions = 0.0
        for _, row in group.sort_values("week").iterrows():
            dollars = float(row["dollars"])
            if dollars <= 0:
                continue
            channel = str(row["channel"]).lower()
            week = int(row["week"])
            cpm_mode = a.cpm.get(channel, (8.0, 14.0, 20.0))[1]

            item_impressions = (dollars / max(1.0, cpm_mode)) * 1000.0

            # Frequency with prior impressions
            f_prev = prior_impressions / universe
            f_new = (prior_impressions + item_impressions) / universe
            k_mode = a.saturation_k[1]

            r_prev = universe * (1.0 - np.exp(-k_mode * f_prev))
            r_new = universe * (1.0 - np.exp(-k_mode * f_new))
            marginal_reach = max(0.0, r_new - r_prev)
            prior_impressions += item_impressions

            # Decay factor: weight = rho^(W - w)
            decay = (a.retention_rho[1]) ** max(0, ctx.weeks - week)

            if aud == "persuasion":
                dv = marginal_reach * a.persuasion_p[1] * decay * opp_factor
            else:  # mobilization
                dv = marginal_reach * a.turnout_t[1] * (2.0 * d_u - 1.0) * decay * opp_factor

            delta_by_unit[uid] += dv
            delta_by_channel[channel] += dv
            total_delta += dv

    return delta_by_unit, delta_by_channel, total_delta


def simulate(
    allocation: pd.DataFrame,
    ctx: RaceContext,
    a: Assumptions,
    n_draws: int = 5000,
    seed: int = 42,
) -> SimulationResult:
    """
    Simulates the election outcome with and without the allocation over N Monte Carlo draws.
    Vectorized using NumPy.
    """
    rng = np.random.default_rng(seed)

    # 1. Deterministic expected deltas
    delta_by_unit, delta_by_channel, total_delta = compute_expected_marginal_votes(allocation, ctx, a)

    # 2. Extract baseline unit information
    units = ctx.units.copy()
    unit_ids = units["unit_id"].values
    margin_col = "baseline_margin_votes" if "baseline_margin_votes" in units.columns else "margin_votes"
    baseline_margins = units[margin_col].astype(float).values
    turnout_col = "total_votes" if "total_votes" in units.columns else "turnout_2022"
    turnouts = units[turnout_col].astype(float).values

    # Target unit mask if scope is district race
    if ctx.scope == "district" and ctx.target_unit:
        is_target = (unit_ids == ctx.target_unit)
        if not np.any(is_target):
            is_target = np.ones(len(unit_ids), dtype=bool)
    else:
        is_target = np.ones(len(unit_ids), dtype=bool)

    # Environment shift added to baseline margin
    # env_shift_pts represents statewide swing in percentage points
    env_shift_votes = (a.env_shift_pts / 100.0) * turnouts

    # Vectorized draws
    # Parameter sampling: triangular distributions
    # Scaling factor for effect size in each draw
    p_draws = rng.triangular(a.persuasion_p[0], a.persuasion_p[1], a.persuasion_p[2], size=n_draws)
    p_scale = p_draws / max(1e-6, a.persuasion_p[1])

    # Shared statewide polling error (percentage points ~ Normal(0, sigma_state))
    statewide_err_pct = rng.normal(0, a.sigma_state, size=n_draws)  # shape: (n_draws,)

    # Independent unit polling errors (percentage points ~ Normal(0, sigma_unit))
    unit_err_pct = rng.normal(0, a.sigma_unit, size=(n_draws, len(unit_ids)))  # shape: (n_draws, n_units)

    # Total vote shift per unit per draw from polling error:
    # Error votes = (statewide_err + unit_err) / 100 * turnout
    total_err_pct = statewide_err_pct[:, None] + unit_err_pct  # shape: (n_draws, n_units)
    err_votes = (total_err_pct / 100.0) * turnouts[None, :]  # shape: (n_draws, n_units)

    # Baseline margins per draw
    base_unit_margins = baseline_margins[None, :] + env_shift_votes[None, :] + err_votes  # (n_draws, n_units)

    # Allocated vote deltas per draw scaled by parameter variation
    # delta_by_unit array matching unit_ids order
    dv_array = np.array([delta_by_unit.get(uid, 0.0) for uid in unit_ids])  # (n_units,)
    plan_unit_deltas = dv_array[None, :] * p_scale[:, None]  # (n_draws, n_units)

    # Projected margins per draw
    plan_unit_margins = base_unit_margins + plan_unit_deltas  # (n_draws, n_units)

    # Evaluate outcome based on scope
    # If statewide: sum over all units
    # If district: sum over target unit(s)
    base_outcomes = np.sum(base_unit_margins[:, is_target], axis=1)  # (n_draws,)
    plan_outcomes = np.sum(plan_unit_margins[:, is_target], axis=1)  # (n_draws,)

    # Win probabilities (margin > 0)
    baseline_win_prob = float(np.mean(base_outcomes > 0))
    plan_win_prob = float(np.mean(plan_outcomes > 0))

    # Bootstrap 80% interval for win probability (subsample 1000 subsets)
    sub_draws = 400
    n_boot = 500
    boot_indices = rng.integers(0, n_draws, size=(n_boot, sub_draws))
    boot_probs = np.mean(plan_outcomes[boot_indices] > 0, axis=1)
    ci_low = float(np.percentile(boot_probs, 10))
    ci_high = float(np.percentile(boot_probs, 90))

    # Pre-bin margin histogram to ~50 bins for Altair (§7.6)
    counts, bin_edges = np.histogram(plan_outcomes, bins=50)
    hist_records = []
    for i in range(len(counts)):
        b_start = bin_edges[i]
        b_end = bin_edges[i + 1]
        hist_records.append({
            "bin_start": round(float(b_start)),
            "bin_end": round(float(b_end)),
            "count": int(counts[i]),
            "is_win": bool((b_start + b_end) / 2.0 > 0)
        })
    df_hist = pd.DataFrame(hist_records)

    # Summary dataframes
    df_delta_unit = pd.DataFrame([
        {"unit_id": uid, "delta_votes": round(delta_by_unit[uid], 1)}
        for uid in unit_ids
    ]).sort_values("delta_votes", ascending=False)

    df_delta_channel = pd.DataFrame([
        {"channel": c, "delta_votes": round(delta_by_channel[c], 1)}
        for c in ["meta", "youtube", "search", "display", "ctv"]
    ])

    total_spent = float(pd.to_numeric(allocation["dollars"], errors="coerce").fillna(0.0).sum()) if allocation is not None and not allocation.empty else 0.0
    cost_per_vote = round(total_spent / max(1.0, total_delta), 2) if total_delta > 0 else 0.0

    return SimulationResult(
        win_prob=round(plan_win_prob, 3),
        win_prob_interval=(round(ci_low, 3), round(ci_high, 3)),
        baseline_win_prob=round(baseline_win_prob, 3),
        margin_hist=df_hist,
        delta_votes_by_unit=df_delta_unit,
        delta_votes_by_channel=df_delta_channel,
        total_delta_votes=round(total_delta, 1),
        cost_per_net_vote=cost_per_vote,
    )
