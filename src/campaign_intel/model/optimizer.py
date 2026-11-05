"""
Greedy marginal optimizer (PROJECT_DESIGN.md §7.7), fully vectorized.

Each step evaluates the expected (mode-parameter) gain of adding one `step` of dollars to
EVERY feasible (unit, channel, audience, week) at once, picks the best, and repeats.

Objective weights per unit turn votes into what the race needs:
- statewide : every unit's votes count equally (weight 1)
- district  : only the target unit counts
- chamber   : weight = probability density of the unit being on the knife's edge
              (d P(win_u) / d votes), so votes go where they can flip seats.
The reported "marginal_votes" are always raw expected net votes.

Model: same adstock + saturation form as the engine, at mode parameters. Adding $x to line
(u, c, a, w) adds x/CPM_c*1000*rho^(W-w) to the (u, a) adstock S, and the gain is
U*effect*opp*(exp(-kS/U) - exp(-k(S+dS)/U)). Lines are compared on gain per dollar.

Caps: a line item can't buy more than `cap_mult` impressions per universe member in a week
(default 5). Increments are min(step, room under the cap), so small districts still get money.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from campaign_intel.config import AUDIENCES, CHANNELS
from campaign_intel.model.assumptions import Assumptions
from campaign_intel.model.engine import (
    ALLOC_COLS,
    RaceContext,
    _opp_factor,
    _relevant_mask,
    _tensor,
    _universe,
    baseline_margins,
    clean_allocation,
)


def unit_weights(ctx: RaceContext, a: Assumptions) -> np.ndarray:
    ids = ctx.units["unit_id"].astype(str).to_numpy()
    if ctx.scope == "chamber":
        base, turn = baseline_margins(ctx, a)
        sd = np.sqrt(a.sigma_state**2 + a.sigma_unit**2) / 100.0 * np.maximum(turn, 1.0)
        z = base / sd
        w = np.exp(-0.5 * z**2) / sd
        return w / w.max() if w.max() > 0 else np.ones(len(ids))
    return _relevant_mask(ctx, ids).astype(float)


def optimize(
    current: pd.DataFrame | None,
    ctx: RaceContext,
    a: Assumptions,
    step: float = 10_000.0,
    channels: list[str] | None = None,
    locks: pd.DataFrame | None = None,
    rebuild: bool = False,
    cap_mult: float = 5.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (recommended_allocation, diff). With rebuild=True the plan restarts from the
    locked rows only; otherwise the remaining budget is added on top of `current`.
    """
    units = ctx.units.reset_index(drop=True)
    ids = units["unit_id"].astype(str).to_numpy()
    idx = {u: i for i, u in enumerate(ids)}
    W = ctx.weeks
    start = clean_allocation(locks if rebuild else current, W)
    X = _tensor(start, idx, len(units), W)                      # (U, C, A, W)
    remaining = float(ctx.budget - X.sum())

    allowed_c = np.array([c in (channels or CHANNELS) for c in CHANNELS])
    weights = unit_weights(ctx, a)
    cand_units = np.where(weights > 1e-6)[0]
    empty_diff = pd.DataFrame(columns=["unit_id", "channel", "audience", "week", "delta_dollars", "marginal_votes"])
    if remaining < 500 or len(cand_units) == 0:
        return _to_frame(X, ids), empty_diff

    Xs = X[cand_units]
    univ = _universe(units)[cand_units]                         # (U, A)
    opp = _opp_factor(units, a)[cand_units]
    wts = weights[cand_units]
    cpm = np.array([a.cpm[c][1] for c in CHANNELS])
    k, rho = a.saturation_k[1], a.retention_rho[1]
    effect = np.array([a.persuasion_p[1], a.turnout_t[1] * (2 * a.dem_share_mobilized - 1)])
    decay = rho ** (W - np.arange(1, W + 1))                    # (W,)
    scale = univ * effect[None, :] * opp[:, None]               # (U, A) votes at full reach
    cap = cap_mult * univ[:, None, :, None] * cpm[None, :, None, None] / 1000.0  # (U, C, A, 1) $
    stock_per_dollar = (1000.0 / cpm)[None, :, None, None] * decay[None, None, None, :]  # (1, C, 1, W)
    min_inc = min(step, 500.0)

    diff_rows = []
    while remaining >= min_inc:
        S = np.einsum("ucaw,cw->ua", Xs, (1000.0 / cpm)[:, None] * decay[None, :])      # (U, A)
        inc = np.minimum(np.minimum(step, cap - Xs), remaining)                         # (U, C, A, W)
        dS = inc * stock_per_dollar
        gain = scale[:, None, :, None] * np.exp(-k * S / univ)[:, None, :, None] * \
            (1.0 - np.exp(-k * dS / univ[:, None, :, None]))
        feasible = (inc >= min_inc) & allowed_c[None, :, None, None]
        score = np.where(feasible, gain * wts[:, None, None, None] / np.maximum(inc, 1.0), -np.inf)
        best = np.unravel_index(np.argmax(score), score.shape)
        if not np.isfinite(score[best]) or score[best] <= 0:
            break
        Xs[best] += inc[best]
        remaining -= inc[best]
        u, c, aa, w = best
        diff_rows.append({"unit_id": ids[cand_units[u]], "channel": CHANNELS[c], "audience": AUDIENCES[aa],
                          "week": int(w) + 1, "delta_dollars": float(inc[best]), "marginal_votes": float(gain[best])})

    X[cand_units] = Xs
    rec = _to_frame(X, ids)
    if not diff_rows:
        return rec, empty_diff
    diff = (pd.DataFrame(diff_rows).groupby(["unit_id", "channel", "audience", "week"], as_index=False)
            .agg(delta_dollars=("delta_dollars", "sum"), marginal_votes=("marginal_votes", "sum"))
            .sort_values("delta_dollars", ascending=False).reset_index(drop=True))
    return rec, diff


def _to_frame(X: np.ndarray, ids: np.ndarray) -> pd.DataFrame:
    u, c, a, w = np.nonzero(X)
    if len(u) == 0:
        return pd.DataFrame(columns=ALLOC_COLS)
    return pd.DataFrame({
        "unit_id": ids[u], "channel": np.array(CHANNELS)[c], "audience": np.array(AUDIENCES)[a],
        "week": w + 1, "dollars": X[u, c, a, w],
    }).sort_values(["unit_id", "week", "channel"]).reset_index(drop=True)
