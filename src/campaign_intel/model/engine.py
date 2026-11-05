"""
War Room simulation engine (PROJECT_DESIGN.md §7.3, §7.5, §7.6). Pure NumPy, no Streamlit.

Per (unit u, audience a) the plan's impressions across all channels and weeks build an
"adstock" that decays week to week, and the adstock on Election Day feeds ONE saturating
reach curve (the standard adstock + saturation form used in media-mix models):

    S     = sum_{c,w} (dollars_{c,w} / CPM_c * 1000) * rho^(W - w)   (decayed impressions)
    R     = Universe * (1 - exp(-k * S / Universe))                  (effective reach)
    dV    = R * effect_a * 1/(1 + lambda * opp_share_u)
    effect_persuasion   = p
    effect_mobilization = t * (2 d - 1)

More money always helps, late money counts more (less decay) and every extra dollar in the
same unit/audience buys less (saturation). ΔV is attributed to lines by their share of S.

Monte Carlo: every uncertain parameter (CPM per channel, k, p, t, rho) is drawn from its
triangle per draw, plus a shared statewide error ~ N(0, sigma_state) and independent unit
errors ~ N(0, sigma_unit), in points of expected turnout. Baseline and plan use the same
draws (common random numbers), so "baseline -> plan" differences are not noise.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

import numpy as np
import pandas as pd

from campaign_intel.config import AUDIENCES, CHANNELS
from campaign_intel.model.assumptions import Assumptions

ALLOC_COLS = ["unit_id", "channel", "audience", "week", "dollars"]
CHAMBER_MAJORITY = {"cd": 8, "sd": 26, "hd": 61}
CHAMBER_SIZE = {"cd": 14, "sd": 50, "hd": 120}


@dataclass(frozen=True)
class RaceContext:
    scope: Literal["statewide", "district", "chamber"]
    unit_type: Literal["cd", "sd", "hd", "county"]
    target_unit: str | None
    weeks: int
    budget: float
    units: pd.DataFrame  # unit_id, name, baseline_margin_votes, expected_turnout,
    #                      persuasion_universe, mobilization_universe, [opp_share]

    @property
    def majority(self) -> int:
        return CHAMBER_MAJORITY.get(self.unit_type, len(self.units) // 2 + 1)


@dataclass(frozen=True)
class SimulationResult:
    scope: str
    win_prob: float
    baseline_win_prob: float
    win_prob_interval: tuple[float, float]     # 10th-90th pct of effect-size uncertainty
    outcome_label: str                         # "Statewide margin (votes)" / "Seats won"
    expected_outcome: float
    baseline_expected_outcome: float
    outcome_hist: pd.DataFrame                 # bin_start, bin_end, series, count
    delta_votes_by_unit: pd.DataFrame          # unit_id, name, delta_votes, delta_low, delta_high
    delta_votes_by_channel: pd.DataFrame       # channel, delta_votes
    delta_votes_by_week: pd.DataFrame          # week, delta_votes
    total_delta_votes: float                   # counted votes (scope-relevant), mean over draws
    total_delta_interval: tuple[float, float]
    cost_per_net_vote: float
    total_spent: float
    n_draws: int


# ----------------------------------------------------------------------------- helpers
def clean_allocation(allocation: pd.DataFrame | None, weeks: int) -> pd.DataFrame:
    if allocation is None or len(allocation) == 0:
        return pd.DataFrame(columns=ALLOC_COLS)
    df = allocation.copy()
    for c in ALLOC_COLS:
        if c not in df.columns:
            df[c] = np.nan
    df["dollars"] = pd.to_numeric(df["dollars"], errors="coerce").fillna(0.0).clip(lower=0)
    df["week"] = pd.to_numeric(df["week"], errors="coerce").fillna(weeks).clip(1, weeks).astype(int)
    df["channel"] = df["channel"].astype(str).str.lower()
    df["audience"] = df["audience"].astype(str).str.lower()
    df["unit_id"] = df["unit_id"].astype(str)
    df = df[df["channel"].isin(CHANNELS) & df["audience"].isin(AUDIENCES) & (df["dollars"] > 0)]
    return df


def _universe(units: pd.DataFrame) -> np.ndarray:
    """(U, A) universe sizes, floored at 1."""
    return np.maximum(units[["persuasion_universe", "mobilization_universe"]].to_numpy(float), 1.0)


def _tensor(alloc: pd.DataFrame, unit_index: dict[str, int], n_units: int, weeks: int) -> np.ndarray:
    """Dollars as a (U, C, A, W) array."""
    X = np.zeros((n_units, len(CHANNELS), len(AUDIENCES), weeks))
    if alloc.empty:
        return X
    ok = alloc["unit_id"].isin(unit_index)
    a = alloc[ok]
    np.add.at(
        X,
        (a["unit_id"].map(unit_index).to_numpy(), a["channel"].map(CHANNELS.index).to_numpy(),
         a["audience"].map(AUDIENCES.index).to_numpy(), a["week"].to_numpy() - 1),
        a["dollars"].to_numpy(float),
    )
    return X


def _draw_params(a: Assumptions, n: int, rng: np.random.Generator) -> dict[str, np.ndarray]:
    tri = lambda t: rng.triangular(t[0], t[1], t[2], size=n) if t[2] > t[0] else np.full(n, t[1])
    return {
        "cpm": np.column_stack([tri(a.cpm[c]) for c in CHANNELS]),  # (N, C)
        "k": tri(a.saturation_k),
        "p": tri(a.persuasion_p),
        "t": tri(a.turnout_t),
        "rho": tri(a.retention_rho),
    }


def _mode_params(a: Assumptions) -> dict[str, np.ndarray]:
    return {
        "cpm": np.array([[a.cpm[c][1] for c in CHANNELS]]),
        "k": np.array([a.saturation_k[1]]),
        "p": np.array([a.persuasion_p[1]]),
        "t": np.array([a.turnout_t[1]]),
        "rho": np.array([a.retention_rho[1]]),
    }


def _opp_factor(units: pd.DataFrame, a: Assumptions) -> np.ndarray:
    opp = units["opp_share"].to_numpy(float) if "opp_share" in units.columns else np.full(len(units), 0.5)
    return 1.0 / (1.0 + a.opp_lambda * opp)


def _vote_deltas(X: np.ndarray, univ: np.ndarray, prm: dict, a: Assumptions, opp: np.ndarray,
                 by: Literal["unit", "line"] = "unit"):
    """
    X: (U, C, A, W) dollars for the units that have spend; univ: (U, A); opp: (U,).
    Returns dV (N, U) — or with by="line" the (N, U, C, A, W) attribution of ΔV to each line.
    """
    W = X.shape[-1]
    decay = prm["rho"][:, None] ** (W - np.arange(1, W + 1))[None, :]          # (N, W)
    inv_cpm = 1000.0 / prm["cpm"]                                               # (N, C)
    d = a.dem_share_mobilized
    effect = np.stack([prm["p"], prm["t"] * (2 * d - 1)], axis=1)               # (N, A)
    if by == "line":
        stock_line = np.einsum("ucaw,nc,nw->nucaw", X, inv_cpm, decay)          # (N, U, C, A, W)
        S = stock_line.sum(axis=(2, 4))                                         # (N, U, A)
    else:
        S = np.einsum("ucaw,nc,nw->nua", X, inv_cpm, decay)
    R = univ[None] * (1.0 - np.exp(-prm["k"][:, None, None] * S / univ[None]))
    V = R * effect[:, None, :] * opp[None, :, None]                             # (N, U, A)
    if by == "line":
        share = np.divide(stock_line, S[:, :, None, :, None], out=np.zeros_like(stock_line),
                          where=S[:, :, None, :, None] > 0)
        return share * V[:, :, None, :, None]
    return V.sum(axis=2)


def _relevant_mask(ctx: RaceContext, unit_ids: np.ndarray) -> np.ndarray:
    if ctx.scope == "district" and ctx.target_unit is not None:
        m = unit_ids == ctx.target_unit
        return m if m.any() else np.ones(len(unit_ids), bool)
    return np.ones(len(unit_ids), bool)


def _outcome(margins: np.ndarray, ctx: RaceContext, relevant: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """margins (N, U) -> (outcome value per draw, win flag per draw)."""
    if ctx.scope == "chamber":
        seats = (margins > 0).sum(axis=1)
        return seats.astype(float), seats >= ctx.majority
    val = margins[:, relevant].sum(axis=1)
    return val, val > 0


def baseline_margins(ctx: RaceContext, a: Assumptions) -> tuple[np.ndarray, np.ndarray]:
    """Expected baseline margin (votes) and expected turnout per unit after the environment shift."""
    turn = ctx.units["expected_turnout"].to_numpy(float)
    base = ctx.units["baseline_margin_votes"].to_numpy(float) + a.env_shift_pts / 100.0 * turn
    return base, turn


# ----------------------------------------------------------------------------- public API
def expected_deltas(allocation: pd.DataFrame, ctx: RaceContext, a: Assumptions) -> pd.DataFrame:
    """Deterministic ΔV at mode parameters, per allocation line (unit, channel, audience, week)."""
    alloc = clean_allocation(allocation, ctx.weeks)
    units = ctx.units.reset_index(drop=True)
    idx = {u: i for i, u in enumerate(units["unit_id"])}
    X = _tensor(alloc, idx, len(units), ctx.weeks)
    if not X.any():
        return pd.DataFrame(columns=["unit_id", "channel", "audience", "week", "delta_votes"])
    active = np.where(X.sum(axis=(1, 2, 3)) > 0)[0]
    Xa = X[active]
    prm = _mode_params(a)
    by_line = _vote_deltas(Xa, _universe(units)[active], prm, a, _opp_factor(units, a)[active], by="line")[0]
    u_i, c_i, a_i, w_i = np.nonzero(Xa)
    return pd.DataFrame({
        "unit_id": units["unit_id"].to_numpy()[active][u_i],
        "channel": np.array(CHANNELS)[c_i],
        "audience": np.array(AUDIENCES)[a_i],
        "week": w_i + 1,
        "dollars": Xa[u_i, c_i, a_i, w_i],
        "delta_votes": by_line[u_i, c_i, a_i, w_i],
    })


def simulate(allocation: pd.DataFrame, ctx: RaceContext, a: Assumptions,
             n_draws: int = 4000, seed: int = 42) -> SimulationResult:
    rng = np.random.default_rng(seed)
    units = ctx.units.reset_index(drop=True)
    unit_ids = units["unit_id"].astype(str).to_numpy()
    alloc = clean_allocation(allocation, ctx.weeks)
    idx = {u: i for i, u in enumerate(unit_ids)}
    X = _tensor(alloc, idx, len(units), ctx.weeks)
    spent = float(alloc["dollars"].sum())

    base, turn = baseline_margins(ctx, a)
    err = (rng.normal(0, a.sigma_state, size=(n_draws, 1))
           + rng.normal(0, a.sigma_unit, size=(n_draws, len(units)))) / 100.0 * turn[None, :]
    base_m = base[None, :] + err                                       # (N, U)

    prm = _draw_params(a, n_draws, rng)
    dV = np.zeros((n_draws, len(units)))
    active = np.where(X.sum(axis=(1, 2, 3)) > 0)[0]
    if len(active):
        univ, opp = _universe(units)[active], _opp_factor(units, a)[active]
        for s in range(0, n_draws, 1000):  # chunk draws to bound memory
            sl = slice(s, s + 1000)
            sub = {k: v[sl] for k, v in prm.items()}
            dV[sl, active] = _vote_deltas(X[active], univ, sub, a, opp)
    plan_m = base_m + dV

    relevant = _relevant_mask(ctx, unit_ids)
    base_val, base_win = _outcome(base_m, ctx, relevant)
    plan_val, plan_win = _outcome(plan_m, ctx, relevant)

    # Effect-size uncertainty band: apply the 10th / 90th percentile draw's ΔV to every error draw
    tot = dV[:, relevant].sum(axis=1)
    lo_i = int(np.argmin(np.abs(tot - np.percentile(tot, 10))))
    hi_i = int(np.argmin(np.abs(tot - np.percentile(tot, 90))))
    wp = lambda dv: float(_outcome(base_m + dv[None, :], ctx, relevant)[1].mean())
    interval = (wp(dV[lo_i]), wp(dV[hi_i]))

    # Histogram of the outcome, baseline vs plan on common bins
    if ctx.scope == "chamber":
        edges = np.arange(min(base_val.min(), plan_val.min()) - 0.5, max(base_val.max(), plan_val.max()) + 1.5)
    else:
        lo, hi = np.percentile(np.concatenate([base_val, plan_val]), [0.5, 99.5])
        edges = np.linspace(lo, hi, 51)
    hb, _ = np.histogram(base_val, bins=edges)
    hp, _ = np.histogram(plan_val, bins=edges)
    hist = pd.concat([
        pd.DataFrame({"bin_start": edges[:-1], "bin_end": edges[1:], "count": hb, "series": "Baseline (no spend)"}),
        pd.DataFrame({"bin_start": edges[:-1], "bin_end": edges[1:], "count": hp, "series": "With plan"}),
    ], ignore_index=True)
    threshold = ctx.majority - 0.5 if ctx.scope == "chamber" else 0.0
    hist["is_win"] = (hist["bin_start"] + hist["bin_end"]) / 2 > threshold

    ed = expected_deltas(alloc, ctx, a)
    by_unit = pd.DataFrame({
        "unit_id": unit_ids, "name": units.get("name", pd.Series(unit_ids)).to_numpy(),
        "delta_votes": dV.mean(axis=0),
        "delta_low": np.percentile(dV, 10, axis=0), "delta_high": np.percentile(dV, 90, axis=0),
        "relevant": relevant,
    })
    by_channel = (ed.groupby("channel", as_index=False)["delta_votes"].sum()
                  .set_index("channel").reindex(CHANNELS, fill_value=0.0).reset_index())
    by_week = ed.groupby("week", as_index=False)["delta_votes"].sum() if not ed.empty else \
        pd.DataFrame(columns=["week", "delta_votes"])

    counted = float(tot.mean())
    label = f"Seats won (majority = {ctx.majority})" if ctx.scope == "chamber" else (
        "District margin (votes)" if ctx.scope == "district" else "Statewide margin (votes)")
    return SimulationResult(
        scope=ctx.scope,
        win_prob=float(plan_win.mean()),
        baseline_win_prob=float(base_win.mean()),
        win_prob_interval=interval,
        outcome_label=label,
        expected_outcome=float(plan_val.mean()),
        baseline_expected_outcome=float(base_val.mean()),
        outcome_hist=hist,
        delta_votes_by_unit=by_unit,
        delta_votes_by_channel=by_channel,
        delta_votes_by_week=by_week,
        total_delta_votes=counted,
        total_delta_interval=(float(np.percentile(tot, 10)), float(np.percentile(tot, 90))),
        cost_per_net_vote=spent / counted if counted > 0 else float("nan"),
        total_spent=spent,
        n_draws=n_draws,
    )


def response_curve(allocation: pd.DataFrame, ctx: RaceContext, a: Assumptions, unit_id: str,
                   audience: str, week: int, max_dollars: float = 600_000, n: int = 25) -> pd.DataFrame:
    """Expected ΔV in one unit as extra dollars go to each channel (rest of the plan held fixed)."""
    alloc = clean_allocation(allocation, ctx.weeks)
    rows = []
    base_total = expected_deltas(alloc, ctx, a)
    base_u = float(base_total.loc[base_total["unit_id"] == unit_id, "delta_votes"].sum()) if not base_total.empty else 0.0
    for ch in CHANNELS:
        for x in np.linspace(0, max_dollars, n):
            extra = pd.DataFrame([{"unit_id": unit_id, "channel": ch, "audience": audience, "week": week, "dollars": x}])
            e = expected_deltas(pd.concat([alloc, extra], ignore_index=True), ctx, a)
            rows.append({"channel": ch, "extra_dollars": x,
                         "delta_votes": float(e.loc[e["unit_id"] == unit_id, "delta_votes"].sum()) - base_u})
    return pd.DataFrame(rows)


def sensitivity(allocation: pd.DataFrame, ctx: RaceContext, a: Assumptions, n_draws: int = 1500) -> pd.DataFrame:
    """One-at-a-time: win probability with each parameter pinned to its low / high value."""
    def pin(t):
        return (t[0], t[0], t[0]), (t[2], t[2], t[2])

    base = simulate(allocation, ctx, a, n_draws=n_draws).win_prob
    cases = {
        "CPM (all channels)": (replace(a, cpm={c: pin(v)[1] for c, v in a.cpm.items()}),   # high CPM = worse
                               replace(a, cpm={c: pin(v)[0] for c, v in a.cpm.items()})),
        "Persuasion effect p": tuple(replace(a, persuasion_p=x) for x in pin(a.persuasion_p)),
        "Turnout lift t": tuple(replace(a, turnout_t=x) for x in pin(a.turnout_t)),
        "Saturation k": tuple(replace(a, saturation_k=x) for x in pin(a.saturation_k)),
        "Weekly retention ρ": tuple(replace(a, retention_rho=x) for x in pin(a.retention_rho)),
        "Environment ±3 pts": (replace(a, env_shift_pts=a.env_shift_pts - 3), replace(a, env_shift_pts=a.env_shift_pts + 3)),
    }
    rows = []
    for name, (lo_a, hi_a) in cases.items():
        rows.append({"parameter": name,
                     "low": simulate(allocation, ctx, lo_a, n_draws=n_draws).win_prob,
                     "high": simulate(allocation, ctx, hi_a, n_draws=n_draws).win_prob,
                     "base": base})
    df = pd.DataFrame(rows)
    df["swing"] = (df["high"] - df["low"]).abs()
    return df.sort_values("swing", ascending=False).reset_index(drop=True)
