"""
War Room glue between the page and the engine: "rewind, plan, reveal".

- Rewind: the planner picks an "as of" date before Election Day; weeks left follow from it.
- Plan: a plan is a *mix* — dollars per (region, platform, goal) — plus one timing preset that
  spreads every line over the weeks left. The engine sees the spread allocation.
- Value of a dollar: one metric everywhere, "win-chance gain per $100K", from the engine's vote
  response at mode parameters and the normal approximation of the margin error.
- Reveal: what the model projected for each region vs. the actual 2026 result.

Pure pandas / NumPy, no Streamlit.
"""

from __future__ import annotations

from dataclasses import replace
from math import erf, exp, pi, sqrt

import numpy as np
import pandas as pd

from campaign_intel.config import AUDIENCES, CHANNELS
from campaign_intel.model.assumptions import Assumptions
from campaign_intel.model.engine import RaceContext, _opp_factor, _universe, baseline_margins

ELECTION_DAY = pd.Timestamp("2026-11-03")
WR_CHANNELS = ["meta", "youtube", "search", "display"]  # no CTV: neither ad library reports it
PLATFORM_LABELS = {"meta": "Facebook / Instagram", "youtube": "YouTube", "search": "Google Search",
                   "display": "Google Display"}
GOAL_LABELS = {"mobilization": "Turn out Democrats", "persuasion": "Persuade unaffiliated",
               "both": "Persuade + turn out"}
PLATFORM_SHORT = {"meta": "FB/IG", "youtube": "YouTube", "search": "Search", "display": "Display"}
GOAL_SHORT = {"mobilization": "turn out", "persuasion": "persuade", "both": "both"}
TIMINGS = {
    "late": "Build to Election Day",
    "even": "Even every week",
    "early": "Front-load",
}
MIX_COLS = ["unit_id", "channel", "audience", "dollars"]
STEP_VALUE = 100_000.0


# ----------------------------------------------------------------------------- time
def weeks_left(asof: pd.Timestamp) -> int:
    return max(1, int(np.ceil((ELECTION_DAY - pd.Timestamp(asof)).days / 7)))


def week_starts(asof: pd.Timestamp, weeks: int) -> list[pd.Timestamp]:
    return [pd.Timestamp(asof) + pd.Timedelta(days=7 * i) for i in range(weeks)]


def timing_weights(timing: str, weeks: int) -> np.ndarray:
    w = np.arange(1, weeks + 1, dtype=float)
    if timing == "late":
        x = w
    elif timing == "early":
        x = w[::-1].copy()
    else:
        x = np.ones(weeks)
    return x / x.sum()


# ----------------------------------------------------------------------------- context
def build_context(units: pd.DataFrame, race: str, weeks: int, budget: float, house_mode: str = "seats",
                  target: str | None = None, opp_share: float = 0.5, a: Assumptions | None = None) -> RaceContext:
    """units: one row per region with the engine's columns (load_regions output)."""
    u = units[["unit_id", "label", "baseline_margin_votes", "expected_turnout", "persuasion_universe",
               "mobilization_universe"]].rename(columns={"label": "name"}).copy()
    u["opp_share"] = opp_share
    if race == "senate":
        return RaceContext("statewide", "county", None, weeks, budget, u)
    if house_mode == "focus" and target:
        return RaceContext("district", "cd", target, weeks, budget, u)
    base = u["baseline_margin_votes"].to_numpy(float) + (a.env_shift_pts / 100 * u["expected_turnout"] if a else 0)
    start = int((np.asarray(base) > 0).sum())
    return RaceContext("chamber", "cd", None, weeks, budget, u, seats_needed=min(start + 1, len(u)))


def seats_at_start(ctx: RaceContext, a: Assumptions) -> int:
    base, _ = baseline_margins(ctx, a)
    return int((base > 0).sum())


# ----------------------------------------------------------------------------- plan <-> allocation
def empty_mix() -> pd.DataFrame:
    return pd.DataFrame({"unit_id": pd.Series(dtype=str), "channel": pd.Series(dtype=str),
                         "audience": pd.Series(dtype=str), "dollars": pd.Series(dtype=float)})


def spread(mix: pd.DataFrame, timing: str, weeks: int) -> pd.DataFrame:
    """Mix (unit, channel, audience, dollars) -> engine allocation with a week per line."""
    if mix is None or mix.empty:
        return pd.DataFrame(columns=MIX_COLS[:3] + ["week", "dollars"])
    w = timing_weights(timing, weeks)
    out = mix.loc[mix.index.repeat(weeks)].copy()
    out["week"] = np.tile(np.arange(1, weeks + 1), len(mix))
    out["dollars"] = out["dollars"].to_numpy() * np.tile(w, len(mix))
    return out.reset_index(drop=True)


def to_mix(allocation: pd.DataFrame) -> pd.DataFrame:
    if allocation is None or allocation.empty:
        return empty_mix()
    m = allocation.groupby(MIX_COLS[:3], as_index=False)["dollars"].sum()
    return m[m["dollars"] >= 1].reset_index(drop=True)


def region_lines(unit_id: str, budget: float, goal: str, channels: list[str]) -> pd.DataFrame:
    chans = [c for c in channels if c in WR_CHANNELS] or ["youtube"]
    auds = {"persuasion": [("persuasion", 1.0)], "mobilization": [("mobilization", 1.0)]}.get(
        goal, [("persuasion", 0.5), ("mobilization", 0.5)])
    rows = [{"unit_id": unit_id, "channel": c, "audience": aud, "dollars": budget * share / len(chans)}
            for c in chans for aud, share in auds]
    return pd.DataFrame(rows, columns=MIX_COLS)


def plan_rows(mix: pd.DataFrame) -> pd.DataFrame:
    """One row per region: budget, goal, platforms (as the planner sees the plan)."""
    if mix.empty:
        return pd.DataFrame(columns=["unit_id", "budget", "goal", "channels"])
    rows = []
    for uid, g in mix.groupby("unit_id", sort=False):
        tot = g["dollars"].sum()
        pers = g.loc[g["audience"] == "persuasion", "dollars"].sum() / tot if tot else 0
        goal = "persuasion" if pers >= 0.75 else ("mobilization" if pers <= 0.25 else "both")
        ch = g.groupby("channel")["dollars"].sum() / tot
        chans = [c for c in WR_CHANNELS if ch.get(c, 0) >= 0.10] or [ch.idxmax()]
        rows.append({"unit_id": uid, "budget": float(tot), "goal": goal, "channels": chans})
    return pd.DataFrame(rows).sort_values("budget", ascending=False).reset_index(drop=True)


def apply_rows(mix: pd.DataFrame, rows: pd.DataFrame) -> pd.DataFrame:
    """
    Rebuild the mix from edited plan rows. A row whose goal and platforms are unchanged keeps its
    exact mix and is only rescaled to the new budget; otherwise its lines are regenerated.
    """
    current = plan_rows(mix).set_index("unit_id") if not mix.empty else None
    parts = []
    for r in rows.itertuples(index=False):
        if not r.unit_id or not (r.budget and r.budget > 0):
            continue
        same = (current is not None and r.unit_id in current.index
                and current.loc[r.unit_id, "goal"] == r.goal
                and sorted(current.loc[r.unit_id, "channels"]) == sorted(r.channels))
        if same:
            g = mix[mix["unit_id"] == r.unit_id].copy()
            g["dollars"] *= r.budget / g["dollars"].sum()
            parts.append(g)
        else:
            parts.append(region_lines(r.unit_id, float(r.budget), r.goal, list(r.channels)))
    if not parts:
        return empty_mix()
    out = pd.concat(parts, ignore_index=True)
    return out.groupby(MIX_COLS[:3], as_index=False, sort=False)["dollars"].sum()


# ----------------------------------------------------------------------------- value of a dollar
def _phi(z: float) -> float:
    return exp(-0.5 * z * z) / sqrt(2 * pi)


def _Phi(z: float) -> float:
    return 0.5 * (1 + erf(z / sqrt(2)))


def region_value(mix: pd.DataFrame, ctx: RaceContext, a: Assumptions, timing: str,
                 channels: list[str] | None = None, step: float = STEP_VALUE) -> pd.DataFrame:
    """
    Per region, on top of the current plan: the best (platform, goal) for the next `step` dollars,
    the net votes it buys (mode parameters), and what that does to our chance of winning:
    the statewide race (Senate), the seat (House), or nothing outside the focus district.
    """
    units = ctx.units.reset_index(drop=True)
    ids = units["unit_id"].astype(str).to_numpy()
    W = ctx.weeks
    chans = [c for c in (channels or WR_CHANNELS) if c in WR_CHANNELS]
    cpm = np.array([a.cpm[c][1] for c in CHANNELS])
    k, rho = a.saturation_k[1], a.retention_rho[1]
    effect = np.array([a.persuasion_p[1], a.turnout_t[1] * (2 * a.dem_share_mobilized - 1)])
    decay = rho ** (W - np.arange(1, W + 1))
    univ = _universe(units)                                                   # (U, A)
    opp = _opp_factor(units, a)
    w = timing_weights(timing, W)

    S = np.zeros((len(units), len(AUDIENCES)))
    if mix is not None and not mix.empty:
        idx = {u: i for i, u in enumerate(ids)}
        m = mix[mix["unit_id"].isin(idx)]
        stock = m["dollars"].to_numpy() * 1000.0 / m["channel"].map(dict(zip(CHANNELS, cpm))).to_numpy() * (w @ decay)
        np.add.at(S, (m["unit_id"].map(idx).to_numpy(), m["audience"].map(AUDIENCES.index).to_numpy()), stock)

    dS = step * 1000.0 / cpm * (w @ decay)                                    # (C,)
    scale = univ * effect[None, :] * opp[:, None]                             # (U, A)
    gain = scale[:, None, :] * np.exp(-k * S / univ)[:, None, :] * (1 - np.exp(-k * dS[None, :, None] / univ[:, None, :]))
    allowed = np.array([c in chans for c in CHANNELS])
    gain = np.where(allowed[None, :, None], gain, -np.inf)                    # (U, C, A)
    flat = gain.reshape(len(units), -1).argmax(axis=1)
    c_i, a_i = np.unravel_index(flat, (len(CHANNELS), len(AUDIENCES)))
    votes = gain[np.arange(len(units)), c_i, a_i]

    base, turn = baseline_margins(ctx, a)
    sd_u = sqrt(a.sigma_state ** 2 + a.sigma_unit ** 2) / 100 * np.maximum(turn, 1.0)
    if ctx.scope == "statewide":
        sd = sqrt((a.sigma_state / 100 * turn.sum()) ** 2 + ((a.sigma_unit / 100 * turn) ** 2).sum())
        d_win = _phi(base.sum() / sd) / sd * votes
        p_now = np.full(len(units), _Phi(base.sum() / sd))
    else:
        d_win = np.array([_phi(b / s) / s for b, s in zip(base, sd_u)]) * votes
        p_now = np.array([_Phi(b / s) for b, s in zip(base, sd_u)])
        if ctx.scope == "district":
            d_win = np.where(ids == ctx.target_unit, d_win, 0.0)
    return pd.DataFrame({
        "unit_id": ids, "best_channel": np.array(CHANNELS)[c_i], "best_goal": np.array(AUDIENCES)[a_i],
        "votes_per_step": votes, "win_gain": d_win, "win_now": p_now,
    })


# ----------------------------------------------------------------------------- explain a suggestion
def diff_sentences(old: pd.DataFrame, new: pd.DataFrame, labels: dict[str, str]) -> list[dict]:
    """Region-level changes between two mixes, biggest first, in plain language."""
    o = plan_rows(old).set_index("unit_id") if not old.empty else pd.DataFrame(columns=["budget"])
    n = plan_rows(new).set_index("unit_id") if not new.empty else pd.DataFrame(columns=["budget"])
    out = []
    for uid in dict.fromkeys(list(n.index) + list(o.index)):
        before = float(o["budget"].get(uid, 0.0))
        after = float(n["budget"].get(uid, 0.0))
        if abs(after - before) < 1000:
            continue
        r = n.loc[uid] if uid in n.index else o.loc[uid]
        plats = " + ".join(PLATFORM_LABELS[c] for c in r["channels"])
        out.append({"unit_id": uid, "label": labels.get(uid, uid), "change": after - before, "after": after,
                    "goal": GOAL_LABELS[r["goal"]], "platforms": plats})
    return sorted(out, key=lambda d: -abs(d["change"]))


# ----------------------------------------------------------------------------- reveal
def projection(ctx: RaceContext, a: Assumptions, delta_votes: pd.Series | None = None) -> pd.DataFrame:
    """Projected margin per region (baseline + expected plan effect), in votes and points."""
    base, turn = baseline_margins(ctx, a)
    u = ctx.units.reset_index(drop=True)
    dv = (delta_votes.reindex(u["unit_id"]).fillna(0).to_numpy() if delta_votes is not None
          else np.zeros(len(u)))
    return pd.DataFrame({"unit_id": u["unit_id"], "turnout": turn, "base_votes": base, "plan_votes": dv,
                         "proj_votes": base + dv, "proj_pct": (base + dv) / np.maximum(turn, 1) * 100})


def with_env(a: Assumptions, pts: float) -> Assumptions:
    return replace(a, env_shift_pts=float(pts))
