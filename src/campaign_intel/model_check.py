"""
Model check: the model's pre-election estimate vs. the 2026 results.

The planning pages (Overview, Region Analysis, Opponent Tracker, War Room) are built for running a midterm and
never use the 2026 results. This module is the one place they are read: it compares the engine's baseline
estimate for each area (the 2024 margin on a midterm-sized electorate, shifted by the national-mood assumption,
before any new ad spending) with what happened, so the model's accuracy can be judged.

House areas are compared with the 2026 US House result in each district; Senate areas (counties) with the
2026 US Senate result. Results are NCSBE's unofficial election-week file.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from campaign_intel import war_room_service as S
from campaign_intel.config import DEFAULT_BUDGET
from campaign_intel.data.loaders import load_regions
from campaign_intel.model import warroom as WR

DEFAULT_ENV = S.DEFAULT_ENV


def _settings(race: str, env: float) -> S.PlanSettings:
    asof = (WR.ELECTION_DAY - pd.Timedelta(weeks=1)).strftime("%Y-%m-%d")
    return S.PlanSettings(race=race, asof=asof, budget=DEFAULT_BUDGET, env=float(env))


@st.cache_data(show_spinner=False, max_entries=16)
def estimates(race: str, env: float = DEFAULT_ENV) -> pd.DataFrame:
    """The model's baseline estimate per area: unit_id, label, start_pct (2024), proj_pct, proj_votes, proj_turnout.
    Uses no 2026 results, so the planning pages can show it."""
    ps = _settings(race, env)
    regions = load_regions(race)
    ctx = WR.build_context(regions, race, ps.weeks, ps.budget, ps.house_mode, ps.target, a=S.assumptions(ps))
    p = WR.projection(ctx, S.assumptions(ps))
    out = regions[["unit_id", "label", "dem_margin_pct"]].rename(columns={"dem_margin_pct": "start_pct"})
    return out.merge(p[["unit_id", "proj_pct", "proj_votes", "turnout"]].rename(columns={"turnout": "proj_turnout"}),
                     on="unit_id", how="left")


def baseline_win_prob(race: str, env: float = DEFAULT_ENV) -> float:
    """The model's chance (before any new ad spending) of its race goal: Senate = win statewide;
    House = win one more seat than the 2024 lines favour us in."""
    return float(S.predict(_settings(race, env), "").baseline_win_prob)


@st.cache_data(show_spinner=False, max_entries=16)
def compare(race: str, env: float = DEFAULT_ENV) -> tuple[pd.DataFrame, dict]:
    """Per area: the model's estimate next to the 2026 result, and summary accuracy figures."""
    r = load_regions(race)
    pre = "house26_" if race == "house" else "actual26_"
    act = r[["unit_id", f"{pre}dem", f"{pre}rep", f"{pre}total"]].set_axis(
        ["unit_id", "act_dem", "act_rep", "act_total"], axis=1)
    d = estimates(race, env).merge(act, on="unit_id", how="left")
    d = d[d["act_total"] > 0].copy()
    d["actual_votes"] = d["act_dem"] - d["act_rep"]
    d["actual_pct"] = d["actual_votes"] / d["act_total"] * 100
    d["miss_pct"] = d["actual_pct"] - d["proj_pct"]
    d["called"] = np.sign(d["actual_pct"]) == np.sign(d["proj_pct"])

    w = d["proj_turnout"] / d["proj_turnout"].sum()
    s = {
        "n": len(d),
        "called": int(d["called"].sum()),
        "avg_miss": float(d["miss_pct"].abs().mean()),           # points, each area counted once
        "bias": float((w * d["miss_pct"]).sum()),                # +: Democrats did better than estimated
        "env": float(env),
        "implied_env": float(env + (w * d["miss_pct"]).sum()),   # the mood that removes the average bias
        "proj_turnout": float(d["proj_turnout"].sum()),
        "actual_turnout": float(d["act_total"].sum()),
        "results_note": "NCSBE unofficial election-week results",
    }
    if race == "senate":
        s["proj_total_pct"] = float(d["proj_votes"].sum() / d["proj_turnout"].sum() * 100)
        s["actual_total_pct"] = float(d["actual_votes"].sum() / d["act_total"].sum() * 100)
    else:
        s["proj_seats"] = int((d["proj_pct"] > 0).sum())
        s["actual_seats"] = int((d["actual_pct"] > 0).sum())
    return d.reset_index(drop=True), s
