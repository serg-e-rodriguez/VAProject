"""
Spend and impression band parsing, midpoint calculation, and interval aggregations per §6.1.
"""

from typing import Any

import numpy as np
import pandas as pd


def parse_band(
    low: float | None,
    high: float | None,
    open_ended_mult: float = 1.5
) -> dict[str, Any]:
    """
    Parses a lower/upper bound into low, mid, high, open_ended flag, and display string.
    """
    val_low = float(low) if low is not None and not np.isnan(low) else 0.0
    val_high = float(high) if high is not None and not np.isnan(high) and high > 0 else None

    if val_high is None or val_high < val_low:
        val_mid = val_low * open_ended_mult
        open_ended = True
        display = f"≥ ${val_low:,.0f}" if val_low >= 1000 else f"≥ ${val_low:.0f}"
    else:
        val_mid = (val_low + val_high) / 2.0
        open_ended = False
        display = f"${val_low:,.0f} – ${val_high:,.0f}"

    return {
        "low": val_low,
        "high": val_high if val_high is not None else val_mid * 1.33,
        "mid": val_mid,
        "open_ended": open_ended,
        "display": display
    }


def aggregate_bands(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    """
    Sums low, mid, and high bounds separately across groups.
    """
    agg = df.groupby(group_cols, as_index=False).agg({
        "spend_low": "sum",
        "spend_mid": "sum",
        "spend_high": "sum",
        "impressions_low": "sum",
        "impressions_mid": "sum",
        "impressions_high": "sum",
    })
    return agg
