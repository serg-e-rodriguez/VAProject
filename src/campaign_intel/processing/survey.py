"""
Weighted CCES 2024 survey processing with confidence intervals per §5.5 and §6.4.
Calculates platform adoption curves by age and demographic issue priorities.
"""

import math
from pathlib import Path

import numpy as np
import pandas as pd

from campaign_intel.config import DATA_DIR


def get_age_cohort(birthyr: float) -> str:
    if pd.isna(birthyr):
        return "Unknown"
    age = 2024 - birthyr
    if age < 25:
        return "18-24"
    elif age < 35:
        return "25-34"
    elif age < 45:
        return "35-44"
    elif age < 55:
        return "45-54"
    elif age < 65:
        return "55-64"
    else:
        return "65+"


PLATFORM_MAP = {
    "CC24_300b_1": "Facebook",
    "CC24_300b_2": "YouTube",
    "CC24_300b_3": "Instagram",
    "CC24_300b_4": "X (Twitter)",
    "CC24_300b_5": "TikTok",
    "CC24_300b_6": "Reddit",
}


def compute_weighted_proportion_with_ci(
    df: pd.DataFrame,
    condition_col: str,
    weight_col: str = "teamweight",
    condition_val: str = "selected"
) -> dict:
    """
    Computes weighted proportion and 95% confidence interval using effective sample size.
    """
    valid = df.dropna(subset=[condition_col, weight_col])
    valid = valid[valid[condition_col] != "not asked"]
    n_unweighted = len(valid)

    if n_unweighted < 30:
        return {
            "prop": np.nan,
            "ci_low": np.nan,
            "ci_high": np.nan,
            "n_unweighted": n_unweighted,
            "suppressed": True
        }

    weights = valid[weight_col].values
    is_selected = (valid[condition_col] == condition_val).astype(float).values

    weighted_sum = np.sum(weights)
    if weighted_sum == 0:
        return {"prop": 0.0, "ci_low": 0.0, "ci_high": 0.0, "n_unweighted": 0, "suppressed": True}

    p = np.sum(is_selected * weights) / weighted_sum
    # Effective sample size Kish formula: (sum w)^2 / sum(w^2)
    n_eff = (weighted_sum ** 2) / np.sum(weights ** 2)
    se = math.sqrt(max(0.0, (p * (1.0 - p)) / max(1.0, n_eff)))
    ci_low = max(0.0, p - 1.96 * se)
    ci_high = min(1.0, p + 1.96 * se)

    return {
        "prop": round(p, 4),
        "ci_low": round(ci_low, 4),
        "ci_high": round(ci_high, 4),
        "n_unweighted": n_unweighted,
        "suppressed": False
    }


def compute_platform_use_by_age(csv_path: Path | None = None) -> pd.DataFrame:
    """
    Computes weighted platform use by age cohort with 95% CIs.
    """
    path = csv_path or (DATA_DIR / "CCES24_UNC_OUTPUT.csv")
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path, low_memory=False)
    df["age_cohort"] = df["birthyr"].apply(get_age_cohort)

    records = []
    age_cohorts = ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]

    for cohort in age_cohorts:
        sub = df[df["age_cohort"] == cohort]
        for col, platform_name in PLATFORM_MAP.items():
            if col in sub.columns:
                res = compute_weighted_proportion_with_ci(sub, col)
                if not res["suppressed"]:
                    records.append({
                        "age_cohort": cohort,
                        "platform": platform_name,
                        "share": res["prop"],
                        "pct": res["prop"] * 100,
                        "ci_low": res["ci_low"] * 100,
                        "ci_high": res["ci_high"] * 100,
                        "n_unweighted": res["n_unweighted"]
                    })

    return pd.DataFrame(records)


def compute_issue_priorities_by_demo(csv_path: Path | None = None) -> pd.DataFrame:
    """
    Computes weighted issue concern shares by demographic cohort.
    """
    path = csv_path or (DATA_DIR / "CCES24_UNC_OUTPUT.csv")
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path, low_memory=False)
    df["age_cohort"] = df["birthyr"].apply(get_age_cohort)

    age_cohorts = ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]
    issues = [
        {"theme": "Economy & Inflation", "col": "CC24_303", "cond": "Increased a lot"},
        {"theme": "National Economy Worse", "col": "CC24_301", "cond": "Gotten much worse"},
    ]

    records = []
    for cohort in age_cohorts:
        sub = df[df["age_cohort"] == cohort]
        for iss in issues:
            col = iss["col"]
            if col in sub.columns:
                res = compute_weighted_proportion_with_ci(sub, col, condition_val=iss["cond"])
                if not res["suppressed"]:
                    records.append({
                        "age_cohort": cohort,
                        "theme": iss["theme"],
                        "pct": res["prop"] * 100,
                        "ci_low": res["ci_low"] * 100,
                        "ci_high": res["ci_high"] * 100,
                        "n_unweighted": res["n_unweighted"]
                    })

    return pd.DataFrame(records)
