"""
War Room Model Assumptions and Presets per §7.4 and §7.9.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from campaign_intel.config import SEEDS_DIR


@dataclass(frozen=True)
class Assumptions:
    cpm: dict[str, tuple[float, float, float]]  # channel -> (low, mode, high)
    saturation_k: tuple[float, float, float]
    persuasion_p: tuple[float, float, float]
    turnout_t: tuple[float, float, float]
    retention_rho: tuple[float, float, float]
    opp_lambda: float
    sigma_state: float
    sigma_unit: float
    env_shift_pts: float


def load_defaults(path: Path | None = None) -> Assumptions:
    yaml_path = path or (SEEDS_DIR / "assumptions_default.yaml")
    if yaml_path.exists():
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)
        cpm_dict = {k: tuple(v) for k, v in data.get("cpm", {}).items()}
        return Assumptions(
            cpm=cpm_dict,
            saturation_k=tuple(data.get("saturation_k", [0.5, 0.8, 1.2])),
            persuasion_p=tuple(data.get("persuasion_p", [0.0, 0.002, 0.006])),
            turnout_t=tuple(data.get("turnout_t", [0.0, 0.003, 0.010])),
            retention_rho=tuple(data.get("retention_rho", [0.4, 0.6, 0.8])),
            opp_lambda=float(data.get("opp_lambda", 0.0)),
            sigma_state=float(data.get("sigma_state", 3.5)),
            sigma_unit=float(data.get("sigma_unit", 2.5)),
            env_shift_pts=float(data.get("env_shift_pts", 0.0)),
        )

    # Hardcoded fallbacks if YAML missing
    return Assumptions(
        cpm={
            "meta": (8.0, 14.0, 20.0),
            "youtube": (11.0, 18.0, 25.0),
            "search": (15.0, 24.0, 35.0),
            "display": (4.0, 6.5, 9.0),
            "ctv": (25.0, 35.0, 50.0),
        },
        saturation_k=(0.5, 0.8, 1.2),
        persuasion_p=(0.0, 0.002, 0.006),
        turnout_t=(0.0, 0.003, 0.010),
        retention_rho=(0.4, 0.6, 0.8),
        opp_lambda=0.0,
        sigma_state=3.5,
        sigma_unit=2.5,
        env_shift_pts=0.0,
    )


def apply_preset(a: Assumptions, name: Literal["conservative", "optimistic"]) -> Assumptions:
    """
    Applies preset configurations from seeds/assumptions_default.yaml.
    """
    yaml_path = SEEDS_DIR / "assumptions_default.yaml"
    if yaml_path.exists():
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)
        preset_data = data.get("presets", {}).get(name)
        if preset_data:
            cpm_dict = {k: tuple(v) for k, v in preset_data.get("cpm", {}).items()}
            return Assumptions(
                cpm=cpm_dict,
                saturation_k=tuple(preset_data.get("saturation_k", a.saturation_k)),
                persuasion_p=tuple(preset_data.get("persuasion_p", a.persuasion_p)),
                turnout_t=tuple(preset_data.get("turnout_t", a.turnout_t)),
                retention_rho=tuple(preset_data.get("retention_rho", a.retention_rho)),
                opp_lambda=float(preset_data.get("opp_lambda", a.opp_lambda)),
                sigma_state=a.sigma_state,
                sigma_unit=a.sigma_unit,
                env_shift_pts=a.env_shift_pts,
            )

    if name == "conservative":
        return Assumptions(
            cpm={k: (v[0] * 1.2, v[1] * 1.2, v[2] * 1.2) for k, v in a.cpm.items()},
            saturation_k=(0.4, 0.6, 0.9),
            persuasion_p=(0.0, 0.001, 0.003),
            turnout_t=(0.0, 0.0015, 0.005),
            retention_rho=(0.3, 0.5, 0.7),
            opp_lambda=0.5,
            sigma_state=a.sigma_state,
            sigma_unit=a.sigma_unit,
            env_shift_pts=a.env_shift_pts,
        )
    else:  # optimistic
        return Assumptions(
            cpm={k: (v[0] * 0.8, v[1] * 0.8, v[2] * 0.8) for k, v in a.cpm.items()},
            saturation_k=(0.7, 1.0, 1.4),
            persuasion_p=(0.001, 0.0035, 0.008),
            turnout_t=(0.001, 0.005, 0.014),
            retention_rho=(0.5, 0.7, 0.85),
            opp_lambda=0.0,
            sigma_state=a.sigma_state,
            sigma_unit=a.sigma_unit,
            env_shift_pts=a.env_shift_pts,
        )
