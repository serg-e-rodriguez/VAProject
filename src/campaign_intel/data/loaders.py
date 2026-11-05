"""
Cached loaders for the Streamlit pages (PROJECT_DESIGN.md §4.1). Everything comes from the
local snapshot (data/cache), which is real data frozen at build time — no sample fallbacks.
Pages call these and lay out the UI; the maths lives in campaign_intel.processing / .model.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from campaign_intel.data.snapshot import has_table, manifest, read_table
from campaign_intel.processing.crosswalk import get_vote_method_splits
from campaign_intel.processing.survey import (
    compute_issue_priorities_by_demo,
    compute_platform_use_by_age,
)
from campaign_intel.processing.themes import theme_labels

CYCLE_START = pd.Timestamp("2026-07-01")


@st.cache_data(ttl=600)
def load_manifest() -> dict:
    return manifest()


def snapshot_ready() -> bool:
    return has_table("units_cd") and has_table("ads_unified")


@st.cache_data(ttl=600)
def dem_share_of_voice() -> float:
    m = manifest().get("dem_share_of_voice")
    return float(m) if m is not None else 0.5


@st.cache_data(ttl=600)
def load_units(unit_type: str = "cd", geo_mode: str = "district") -> pd.DataFrame:
    """Baseline + electorate table for the active geography (one row per unit)."""
    key = "county" if geo_mode == "county" else unit_type
    u = read_table(f"units_{key}")
    # Opponent share of voice: observed statewide GOP share of partisan NC ad spend (Meta+Google).
    # Ad libraries don't report spend by district, so every unit gets the statewide value.
    u["opp_share"] = 1.0 - dem_share_of_voice()
    u["swing_pts"] = u.get("actual26_margin_pct", np.nan) - u["dem_margin_pct"]
    if key == "cd" and has_table("google_cd_spend_units"):
        g = read_table("google_cd_spend_units")
        g = g[g["map_vintage"] == "2026"].groupby("unit_id")["spend_usd"].sum()
        u["google_spend_2026_map"] = u["unit_id"].map(g).fillna(0.0)
    return u


@st.cache_data(ttl=600)
def load_ads() -> pd.DataFrame:
    return read_table("ads_unified")


@st.cache_data(ttl=600)
def load_weekly_by_side(platform: str | None = None) -> pd.DataFrame:
    w = read_table("weekly_spend_by_side")
    if platform:
        w = w[w["platform"] == platform]
    w = w.groupby(["week_start", "side_group"], as_index=False)[["nc_spend_low", "nc_spend_mid", "nc_spend_high"]].sum()
    snap = pd.Timestamp(manifest().get("built_at", pd.Timestamp.today().isoformat())[:10])
    # Drop the trailing partial week (it would look like a collapse in spending)
    last_full = (snap - pd.Timedelta(days=6)).to_period("W-SAT").start_time
    return w[(w["week_start"] >= CYCLE_START - pd.Timedelta(days=28)) & (w["week_start"] <= last_full)]


@st.cache_data(ttl=600)
def load_sov_weekly() -> pd.DataFrame:
    w = load_weekly_by_side()
    p = w.pivot_table(index="week_start", columns="side_group", values="nc_spend_mid", aggfunc="sum").fillna(0)
    p = p.rename(columns={"Dem side": "dem", "GOP side": "gop"})
    for c in ["dem", "gop"]:
        if c not in p.columns:
            p[c] = 0.0
    p["dem_share"] = p["dem"] / (p["dem"] + p["gop"]).replace(0, np.nan)
    return p.reset_index()


@st.cache_data(ttl=600)
def load_overview_kpis() -> dict:
    ads = load_ads()
    w = load_weekly_by_side()
    snap = pd.Timestamp(manifest().get("built_at", pd.Timestamp.today().isoformat())[:10])
    cyc = w[w["week_start"] >= CYCLE_START]
    tot = cyc[["nc_spend_low", "nc_spend_mid", "nc_spend_high"]].sum()
    sov = load_sov_weekly()
    last4, prev4 = sov.tail(4), sov.iloc[-8:-4]
    dem4 = last4["dem"].sum() / max(1.0, (last4["dem"] + last4["gop"]).sum())
    demp = prev4["dem"].sum() / max(1.0, (prev4["dem"] + prev4["gop"]).sum())
    gop = sov["gop"].tolist()
    d7, d14 = snap - pd.Timedelta(days=7), snap - pd.Timedelta(days=14)
    active = ads[ads["end"] >= d7]
    act = active.groupby("side_group")["ad_id"].nunique()
    new_dem = ads[(ads["start"] >= d7) & (ads["side_group"] == "Dem side")]["ad_id"].nunique()
    new_gop = ads[(ads["start"] >= d7) & (ads["side_group"] == "GOP side")]["ad_id"].nunique()
    new_gop_prev = ads[(ads["start"] >= d14) & (ads["start"] < d7) & (ads["side_group"] == "GOP side")]["ad_id"].nunique()
    return {
        "total_mid": float(tot["nc_spend_mid"]), "total_low": float(tot["nc_spend_low"]),
        "total_high": float(tot["nc_spend_high"]),
        "weekly_total": (w.groupby("week_start")["nc_spend_mid"].sum().tail(8)).tolist(),
        "dem_sov_4w": dem4, "dem_sov_prev4w": demp, "sov_series": sov["dem_share"].fillna(0.5).tail(8).tolist(),
        "gop_last_week": float(gop[-1]) if gop else 0.0, "gop_prev_week": float(gop[-2]) if len(gop) > 1 else 0.0,
        "gop_series": gop[-8:],
        "active_dem": int(act.get("Dem side", 0)), "active_gop": int(act.get("GOP side", 0)),
        "new_dem_7d": int(new_dem), "new_gop_7d": int(new_gop), "new_gop_prev_7d": int(new_gop_prev),
        "last_week": str(sov["week_start"].max().date()) if len(sov) else "",
    }


@st.cache_data(ttl=600)
def load_platform_mix() -> pd.DataFrame:
    return read_table("platform_mix")


@st.cache_data(ttl=600)
def load_advertisers() -> pd.DataFrame:
    return read_table("advertisers")


@st.cache_data(ttl=600)
def load_alerts() -> pd.DataFrame:
    return read_table("alerts") if has_table("alerts") else pd.DataFrame(columns=["severity", "type", "advertiser", "text", "date", "alert_id"])


@st.cache_data(ttl=600)
def load_theme_by_age(view: str = "Us") -> pd.DataFrame:
    """Share of each age group's Meta NC impressions carrying each theme. view: Us | Opponent | Gap."""
    t = read_table("theme_by_age")
    labels = theme_labels()
    t["theme"] = t["theme"].map(lambda x: labels.get(x, x))
    p = t.pivot_table(index=["theme", "age"], columns="side_group", values="pct", aggfunc="sum").fillna(0.0)
    for c in ["Dem side", "GOP side"]:
        if c not in p.columns:
            p[c] = 0.0
    if view == "Us":
        p["pct"] = p["Dem side"]
    elif view == "Opponent":
        p["pct"] = p["GOP side"]
    else:
        p["pct"] = p["Dem side"] - p["GOP side"]
    return p.reset_index()[["theme", "age", "pct", "Dem side", "GOP side"]].rename(columns={"age": "age_cohort"})


@st.cache_data(ttl=600)
def load_delivery_by_demo() -> pd.DataFrame:
    return read_table("delivery_by_demo")


@st.cache_data(ttl=600)
def load_survey_platform_benchmarks() -> pd.DataFrame:
    return compute_platform_use_by_age()


@st.cache_data(ttl=600)
def load_survey_issue_benchmarks() -> pd.DataFrame:
    return compute_issue_priorities_by_demo()


@st.cache_data(ttl=600)
def load_vote_methods() -> pd.DataFrame:
    return get_vote_method_splits()


@st.cache_data(ttl=600)
def load_statewide() -> dict:
    return read_table("statewide").iloc[0].to_dict()


@st.cache_data(ttl=600)
def load_creatives(side_group: str = "GOP side", limit: int = 400) -> pd.DataFrame:
    """Inspectable creatives with text (Meta) plus Google ads (link to the Transparency Report)."""
    ads = load_ads()
    a = ads[ads["side_group"] == side_group].copy()
    a["has_text"] = a["body"].str.len() > 0
    a = a.sort_values(["has_text", "start"], ascending=[False, False]).head(limit)
    if has_table("meta_demographics"):
        d = read_table("meta_demographics")
        d = d[d["ad_id"].isin(a["ad_id"])].sort_values("pct", ascending=False).drop_duplicates("ad_id")
        top = d.set_index("ad_id").apply(lambda r: f"{str(r.gender).title()} {r.age} ({r.pct:.0%})", axis=1)
        a["top_demo"] = a["ad_id"].map(top).fillna("—")
    else:
        a["top_demo"] = "—"
    return a


def fmt_money(x: float) -> str:
    x = float(x or 0)
    if abs(x) >= 1e6:
        return f"${x / 1e6:.2f}M"
    if abs(x) >= 1e3:
        return f"${x / 1e3:.0f}k"
    return f"${x:,.0f}"


def esc(text: str) -> str:
    """Escape $ so Streamlit markdown doesn't render money as LaTeX."""
    return text.replace("$", "\\$")
