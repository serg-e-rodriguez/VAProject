"""
War Room model assumptions and presets (PROJECT_DESIGN.md §7.4, §7.9).

Every uncertain parameter is a (low, mode, high) triangle used by the Monte Carlo.
CPM modes come from the data snapshot when available (median NC CPM by channel).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Literal

import yaml

from campaign_intel.config import CHANNELS, SEEDS_DIR

Tri = tuple[float, float, float]


@dataclass(frozen=True)
class Assumptions:
    cpm: dict[str, Tri]          # channel -> (low, mode, high) $ per 1,000 impressions
    saturation_k: Tri            # reach curve steepness
    persuasion_p: Tri            # net margin votes per reached persuadable voter
    turnout_t: Tri               # turnout lift per reached mobilization target
    retention_rho: Tri           # weekly retention of ad effects
    opp_lambda: float            # opponent share-of-voice dampening
    sigma_state: float           # statewide baseline error (pts)
    sigma_unit: float            # extra per-unit error (pts)
    env_shift_pts: float         # national environment vs. 2024 baseline (pts, + = Dem)
    dem_share_mobilized: float = 0.85  # d_u: share of mobilized Dem registrants voting Dem

    def to_dict(self) -> dict:
        d = asdict(self)
        d["cpm"] = {k: list(v) for k, v in self.cpm.items()}
        return d

    @staticmethod
    def from_dict(d: dict) -> Assumptions:
        d = dict(d)
        d["cpm"] = {k: tuple(v) for k, v in d["cpm"].items()}
        for k in ["saturation_k", "persuasion_p", "turnout_t", "retention_rho"]:
            d[k] = tuple(d[k])
        return Assumptions(**d)


def _tri(v) -> Tri:
    lo, mode, hi = (float(x) for x in v)
    return (min(lo, mode), mode, max(hi, mode))


def _read_yaml(path: Path | None = None) -> dict:
    p = path or (SEEDS_DIR / "assumptions_default.yaml")
    with open(p) as f:
        return yaml.safe_load(f)


def observed_cpm() -> dict[str, float]:
    """Median NC CPM by channel from the snapshot (empty dict if no snapshot)."""
    try:
        from campaign_intel.data.snapshot import read_table

        df = read_table("cpm_observed")
        return {r.channel: float(r.cpm_median) for r in df.itertuples() if r.cpm_median > 0}
    except Exception:
        return {}


def load_defaults(path: Path | None = None, use_observed_cpm: bool = True) -> Assumptions:
    data = _read_yaml(path)
    cpm = {k: _tri(v) for k, v in data["cpm"].items()}
    if use_observed_cpm:
        spread = float(data.get("cpm_observed_spread", 0.4))
        for ch, mode in observed_cpm().items():
            if ch in cpm:
                cpm[ch] = (round(mode * (1 - spread), 2), round(mode, 2), round(mode * (1 + spread), 2))
    return Assumptions(
        cpm={c: cpm[c] for c in CHANNELS},
        saturation_k=_tri(data["saturation_k"]),
        persuasion_p=_tri(data["persuasion_p"]),
        turnout_t=_tri(data["turnout_t"]),
        retention_rho=_tri(data["retention_rho"]),
        opp_lambda=float(data.get("opp_lambda", 0.0)),
        sigma_state=float(data.get("sigma_state", 3.5)),
        sigma_unit=float(data.get("sigma_unit", 2.5)),
        env_shift_pts=float(data.get("env_shift_pts", 0.0)),
        dem_share_mobilized=float(data.get("dem_share_mobilized", 0.85)),
    )


def apply_preset(a: Assumptions, name: Literal["default", "conservative", "optimistic"]) -> Assumptions:
    """Effect-size / cost presets. Environment, error and d_u are kept from `a`."""
    base = load_defaults()
    if name == "default":
        return replace(base, env_shift_pts=a.env_shift_pts, sigma_state=a.sigma_state,
                       sigma_unit=a.sigma_unit, dem_share_mobilized=a.dem_share_mobilized)
    p = _read_yaml()["presets"][name]
    cpm_mult = float(p.get("cpm_multiplier", 1.0))
    return replace(
        a,
        cpm={c: tuple(round(x * cpm_mult, 2) for x in base.cpm[c]) for c in CHANNELS},
        saturation_k=_tri(p["saturation_k"]),
        persuasion_p=_tri(p["persuasion_p"]),
        turnout_t=_tri(p["turnout_t"]),
        retention_rho=_tri(p["retention_rho"]),
        opp_lambda=float(p.get("opp_lambda", a.opp_lambda)),
    )
