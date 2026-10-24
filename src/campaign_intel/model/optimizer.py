"""
Greedy Marginal Budget Optimizer per §7.7 and §7.9.
Allocates budget in discrete increments ($10,000) to maximize net votes.
"""

from typing import Literal

import pandas as pd

from campaign_intel.model.assumptions import Assumptions
from campaign_intel.model.engine import RaceContext, compute_expected_marginal_votes


def optimize(
    current: pd.DataFrame,
    ctx: RaceContext,
    a: Assumptions,
    step: float = 10_000.0,
    objective: Literal["votes", "win_prob"] = "votes",
    locks: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Greedy marginal allocation in increments of step (default $10,000).
    Evaluates expected net vote return across eligible (unit, channel, audience, week).
    Returns (recommended_allocation, diff_df).
    """
    # Start from current or locked allocation
    if locks is not None and not locks.empty:
        working_alloc = locks.copy()
    elif current is not None and not current.empty:
        working_alloc = current.copy()
    else:
        working_alloc = pd.DataFrame(columns=["unit_id", "channel", "audience", "week", "dollars"])

    working_alloc["dollars"] = pd.to_numeric(working_alloc["dollars"], errors="coerce").fillna(0.0)
    current_spent = float(working_alloc["dollars"].sum())
    remaining_budget = max(0.0, ctx.budget - current_spent)

    if remaining_budget < step:
        return working_alloc, pd.DataFrame(columns=["unit_id", "channel", "audience", "week", "delta_dollars", "marginal_votes"])

    # Determine candidate units
    # For statewide: consider swing/competitive units first, then others
    units_df = ctx.units.copy()
    if ctx.scope == "district" and ctx.target_unit:
        candidate_units = [ctx.target_unit]
    else:
        # Prioritize top competitive units (margin within +-15%) to speed up greedy steps
        if "dem_margin_pct" in units_df.columns:
            comp_mask = units_df["dem_margin_pct"].abs() <= 18.0
            candidate_units = units_df[comp_mask]["unit_id"].tolist()
            if len(candidate_units) < 3:
                candidate_units = units_df["unit_id"].tolist()
        else:
            candidate_units = units_df["unit_id"].tolist()

    channels = ["meta", "youtube", "search"]
    audiences = ["persuasion", "mobilization"]
    # Later weeks count more due to decay rho^(W - w), test last 3 weeks
    weeks = [max(1, ctx.weeks - 2), max(1, ctx.weeks - 1), ctx.weeks]

    diff_records = []
    # Build indexed map of allocations
    alloc_map = {}
    for _, row in working_alloc.iterrows():
        key = (str(row["unit_id"]), str(row["channel"]), str(row["audience"]), int(row["week"]))
        alloc_map[key] = alloc_map.get(key, 0.0) + float(row["dollars"])

    # Base vote calculation
    _, _, current_base_votes = compute_expected_marginal_votes(working_alloc, ctx, a)

    # Greedy allocation loop
    while remaining_budget >= step:
        best_cand = None
        best_marginal_gain = -1.0

        for uid in candidate_units:
            for ch in channels:
                for aud in audiences:
                    for wk in weeks:
                        cand_key = (uid, ch, aud, wk)
                        # Check cap (no single line item > 250,000)
                        if alloc_map.get(cand_key, 0.0) >= 250_000.0:
                            continue

                        # Test adding step
                        alloc_map[cand_key] = alloc_map.get(cand_key, 0.0) + step

                        # Build temp DataFrame
                        temp_rows = [
                            {"unit_id": k[0], "channel": k[1], "audience": k[2], "week": k[3], "dollars": v}
                            for k, v in alloc_map.items() if v > 0
                        ]
                        df_temp = pd.DataFrame(temp_rows)
                        _, _, new_votes = compute_expected_marginal_votes(df_temp, ctx, a)
                        marginal_gain = new_votes - current_base_votes

                        if marginal_gain > best_marginal_gain:
                            best_marginal_gain = marginal_gain
                            best_cand = cand_key

                        # Revert test step
                        alloc_map[cand_key] -= step

        if best_cand is None or best_marginal_gain <= 0.0:
            break

        # Apply winning step
        alloc_map[best_cand] = alloc_map.get(best_cand, 0.0) + step
        remaining_budget -= step
        current_base_votes += best_marginal_gain

        diff_records.append({
            "unit_id": best_cand[0],
            "channel": best_cand[1],
            "audience": best_cand[2],
            "week": best_cand[3],
            "delta_dollars": step,
            "marginal_votes": round(best_marginal_gain, 1)
        })

    # Assemble recommended allocation DataFrame
    rec_rows = [
        {"unit_id": k[0], "channel": k[1], "audience": k[2], "week": k[3], "dollars": v}
        for k, v in alloc_map.items() if v > 0
    ]
    recommended_df = pd.DataFrame(rec_rows)
    if recommended_df.empty:
        recommended_df = pd.DataFrame(columns=["unit_id", "channel", "audience", "week", "dollars"])

    diff_df = pd.DataFrame(diff_records)
    if not diff_df.empty:
        # Group identical incremental steps for clean UI display
        diff_df = diff_df.groupby(["unit_id", "channel", "audience", "week"], as_index=False).agg({
            "delta_dollars": "sum",
            "marginal_votes": "sum"
        }).sort_values("marginal_votes", ascending=False)

    return recommended_df, diff_df
