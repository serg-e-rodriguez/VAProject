"""
Cached, race-aware loaders for the pages. Everything is read from the local snapshot (data/cache);
pages only lay out what these return.

Conventions
-----------
- `race` is "senate" or "house" (config.RACES). Ad spend is filtered to ads attributed to that race
  (nominee committees, race-specific PACs / party committees, nominee named in the ad text, or
  Google district targeting). Party / issue / state-race money is reported separately as "other".
- Ad spend is NC-apportioned and limited to the cycle window (since 2026-07-01): `w_nc_spend_mid`.
- Region = county (Senate) or congressional district (House).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from campaign_intel.config import RACES
from campaign_intel.data.snapshot import has_table, manifest, read_table
from campaign_intel.processing.themes import theme_labels

CYCLE_START = pd.Timestamp("2026-07-01")
SIDES = ["Dem side", "GOP side"]
PARTY_ORDER = ["Dem", "Rep", "Unaffiliated", "Other party"]
DIM_ORDER = {
    "age": ["18–25", "26–40", "41–65", "66+"],
    "race": ["White", "Black", "Hispanic / Latino", "Asian", "American Indian", "Other / multiracial", "Undesignated"],
    "gender": ["Women", "Men", "Undesignated"],
}
CHANNEL_LABELS = {"meta": "Facebook / Instagram", "youtube": "YouTube", "search": "Google Search",
                  "display": "Google Display"}


# ----------------------------------------------------------------------------- basics
@st.cache_data(ttl=600)
def load_manifest() -> dict:
    return manifest()


def snapshot_ready() -> bool:
    return all(has_table(t) for t in ("units_cd", "ads_unified", "demographics", "house_races"))


def snapshot_date() -> pd.Timestamp:
    return pd.Timestamp(load_manifest().get("built_at", pd.Timestamp.today().isoformat())[:10])


def unit_type(race: str) -> str:
    return RACES[race]["unit_type"]


@st.cache_data(ttl=600)
def load_statewide() -> dict:
    return read_table("statewide").iloc[0].to_dict()


@st.cache_data(ttl=600)
def load_candidates() -> pd.DataFrame:
    return read_table("candidates")


@st.cache_data(ttl=600)
def senate_nominees() -> dict:
    c = load_candidates()
    c = c[(c["race"] == "senate")].sort_values("votes", ascending=False)
    dem = c[c["party"] == "DEM"]["name"]
    rep = c[c["party"] == "REP"]["name"]
    return {"dem": dem.iloc[0] if len(dem) else "Democratic nominee", "rep": rep.iloc[0] if len(rep) else "Republican nominee"}


# ----------------------------------------------------------------------------- regions
@st.cache_data(ttl=600)
def load_regions(race: str) -> pd.DataFrame:
    """One row per region (county or CD) with baseline, registration, turnout and (House) race info."""
    ut = unit_type(race)
    u = read_table(f"units_{ut}")
    u["dem_share_reg"] = u["reg_dem"] / u["registered_voters"]
    u["rep_share_reg"] = u["reg_rep"] / u["registered_voters"]
    u["una_share_reg"] = u["reg_una"] / u["registered_voters"]
    d = read_table("demographics")
    d = d[(d["unit_type"] == ut) & (d["dim"] == "age")]
    by = d.groupby(["unit_id", "party"])[["reg22", "voted22"]].sum().unstack("party").fillna(0)
    for p, key in [("Dem", "dem"), ("Rep", "rep"), ("Unaffiliated", "una")]:
        u[f"turnout22_{key}"] = u["unit_id"].map(by[("voted22", p)] / by[("reg22", p)].replace(0, np.nan))
    tot = by["voted22"].sum(axis=1) / by["reg22"].sum(axis=1).replace(0, np.nan)
    u["turnout22"] = u["unit_id"].map(tot)
    u["dems_skipped22"] = u["mobilization_universe"]
    if ut == "cd":
        h = read_table("house_races")
        u = u.merge(h.drop(columns=["district_num"]), on="unit_id", how="left")
        u["result26_margin_pct"] = u["house26_margin_pct"]
        u["label"] = "CD-" + u["district_num"].astype(str)
    else:
        u["result26_margin_pct"] = u["actual26_margin_pct"]
        u["label"] = u["name"]
    u["lean"] = u["dem_margin_pct"].map(lean_label)
    ads = load_region_ad_spend(race)
    piv = ads.groupby(["unit_id", "side_group"])["spend"].sum().unstack().reindex(columns=SIDES).fillna(0)
    u["ad_dem"] = u["unit_id"].map(piv["Dem side"]).fillna(0.0)
    u["ad_gop"] = u["unit_id"].map(piv["GOP side"]).fillna(0.0)
    u["ad_net_dem"] = u["ad_dem"] - u["ad_gop"]
    return u


def lean_label(m: float) -> str:
    if pd.isna(m):
        return "—"
    a = abs(m)
    side = "D" if m > 0 else "R"
    if a < 3:
        return "Toss-up"
    if a < 8:
        return f"Lean {side}"
    if a < 15:
        return f"Likely {side}"
    return f"Safe {side}"


def fmt_margin(m: float) -> str:
    if pd.isna(m):
        return "—"
    return f"{'D' if m >= 0 else 'R'} +{abs(m):.1f}"


@st.cache_data(ttl=600)
def load_demographics(unit_type_: str, unit_id: str, dim: str) -> pd.DataFrame:
    """Rows per group x party for one region (unit_type 'state' / unit_id 'NC' for statewide)."""
    d = read_table("demographics")
    d = d[(d["unit_type"] == unit_type_) & (d["unit_id"] == unit_id) & (d["dim"] == dim)].copy()
    d["turnout22"] = d["voted22"] / d["reg22"].replace(0, np.nan)
    d["skipped22"] = (d["reg22"] - d["voted22"]).clip(lower=0)
    return d


@st.cache_data(ttl=600)
def party_totals(unit_type_: str, unit_id: str) -> pd.DataFrame:
    """Registered (2024), registered (2022), voted (2022) and turnout by party for one region."""
    d = load_demographics(unit_type_, unit_id, "age")
    g = d.groupby("party", as_index=False)[["reg24", "reg22", "voted22"]].sum()
    g["turnout22"] = g["voted22"] / g["reg22"].replace(0, np.nan)
    g["party"] = pd.Categorical(g["party"], PARTY_ORDER, ordered=True)
    return g.sort_values("party").reset_index(drop=True)


def path_to_win(margin_pct: float, expected_turnout: float, pt: pd.DataFrame) -> dict:
    """
    Net votes we are behind (or ahead) at the 2024 presidential margin in a midterm-sized electorate,
    and what closing it takes: share of non-voting Dems to turn out, or extra net margin among
    unaffiliated voters who usually vote.
    """
    gap = -margin_pct / 100 * expected_turnout  # >0 = votes we need
    dem = pt[pt["party"] == "Dem"].iloc[0] if (pt["party"] == "Dem").any() else None
    una = pt[pt["party"] == "Unaffiliated"].iloc[0] if (pt["party"] == "Unaffiliated").any() else None
    skipped = float(dem["reg24"] * (1 - dem["turnout22"])) if dem is not None else np.nan
    una_voters = float(una["reg24"] * una["turnout22"]) if una is not None else np.nan
    return {
        "gap": gap,
        "dems_skipped": skipped,
        "una_voters": una_voters,
        "mobilize_share": gap / skipped if gap > 0 and skipped else 0.0,
        "una_points": gap / una_voters * 100 if gap > 0 and una_voters else 0.0,
    }


# ----------------------------------------------------------------------------- ads
@st.cache_data(ttl=600)
def load_ads(race: str | None = None) -> pd.DataFrame:
    a = read_table("ads_unified")
    a = a[a["window_frac"] > 0]
    return a[a["race"] == race] if race else a


@st.cache_data(ttl=600)
def spend_summary(race: str) -> dict:
    a = load_ads(race)
    by = a.groupby("side_group")["w_nc_spend_mid"].sum()
    dem, gop = float(by.get("Dem side", 0)), float(by.get("GOP side", 0))
    w = weekly_by_side(race)
    p = w.pivot_table(index="week_start", columns="side_group", values="spend", aggfunc="sum").reindex(columns=SIDES).fillna(0)
    last4, prev4 = p.tail(4).sum(), p.iloc[-8:-4].sum()
    share = lambda s: s["Dem side"] / (s.sum() or 1)  # noqa: E731
    other = load_ads()
    other = other[other["race"] == "other"]["w_nc_spend_mid"].sum()
    return {
        "dem": dem, "gop": gop, "partisan": dem + gop,
        "unclassified": float(by.get("Unclassified", 0) + by.get("Nonpartisan / other", 0)),
        "dem_share": dem / (dem + gop) if dem + gop else np.nan,
        "dem_share_4w": share(last4), "dem_share_prev4w": share(prev4),
        "gop_4w": float(last4["GOP side"]), "gop_prev4w": float(prev4["GOP side"]),
        "dem_4w": float(last4["Dem side"]),
        "other_races": float(other),
        "gop_last": _last_end(a, "GOP side"), "dem_last": _last_end(a, "Dem side"),
        "n_ads": int(a["ad_id"].nunique()),
    }


def _last_end(a: pd.DataFrame, side: str) -> pd.Timestamp | None:
    """Last delivery day of any meaningful ad (≥ $1K NC spend) on one side."""
    x = a[(a["side_group"] == side) & (a["w_nc_spend_mid"] >= 1000)]
    return x["end"].max() if len(x) else None


def went_dark(s: dict, side: str = "gop", days: int = 14) -> str | None:
    """'Oct 03' if that side has run no meaningful ads for `days`+ days before the snapshot."""
    last = s.get(f"{side}_last")
    if last is not None and pd.notna(last) and last < snapshot_date() - pd.Timedelta(days=days):
        return f"{last:%b %d}"
    return None


@st.cache_data(ttl=600)
def weekly_by_side(race: str) -> pd.DataFrame:
    w = read_table("weekly_spend_by_side")
    w = w[(w["race"] == race) & w["side_group"].isin(SIDES)]
    w = w.groupby(["week_start", "side_group", "platform"], as_index=False)["nc_spend_mid"].sum()
    w = w.rename(columns={"nc_spend_mid": "spend"})
    last_full = (snapshot_date() - pd.Timedelta(days=6)).to_period("W-SAT").start_time
    return w[(w["week_start"] >= CYCLE_START) & (w["week_start"] <= last_full)]


@st.cache_data(ttl=600)
def weekly_by_channel(race: str, side: str) -> pd.DataFrame:
    """Spend per week x channel for one side (each ad's spend spread over its delivery days)."""
    a = load_ads(race)
    a = a[(a["side_group"] == side) & (a["w_nc_spend_mid"] > 0)].copy()
    if a.empty:
        return pd.DataFrame(columns=["week_start", "channel", "spend"])
    start = a["start"].clip(lower=CYCLE_START)
    days = ((a["end"] - start).dt.days + 1).clip(lower=1)
    a = a.assign(start=start, days=days, per_day=a["w_nc_spend_mid"] / days).reset_index(drop=True)
    a = a.loc[a.index.repeat(a["days"].astype(int))]
    a["day"] = a["start"] + pd.to_timedelta(a.groupby(level=0).cumcount(), unit="D")
    a["week_start"] = a["day"].dt.to_period("W-SAT").dt.start_time
    out = a.groupby(["week_start", "channel"], as_index=False)["per_day"].sum().rename(columns={"per_day": "spend"})
    out["channel"] = out["channel"].map(CHANNEL_LABELS).fillna(out["channel"])
    last_full = (snapshot_date() - pd.Timedelta(days=6)).to_period("W-SAT").start_time
    return out[out["week_start"] <= last_full]


@st.cache_data(ttl=600)
def top_advertisers(race: str, side: str | None = None, n: int = 10) -> pd.DataFrame:
    a = load_ads(race)
    a = a[a["side_group"].isin([side] if side else SIDES)].copy()
    snap = snapshot_date()
    # Google and Meta spell the same committee differently ("COOPER FOR NORTH CAROLINA" vs
    # "Cooper for North Carolina"): merge on a case/space-folded key, show the biggest spender's spelling.
    key = a["advertiser"].str.casefold().str.split().str.join(" ")
    name = (a.assign(_k=key).groupby(["_k", "advertiser"])["w_nc_spend_mid"].sum()
            .sort_values(ascending=False).reset_index().drop_duplicates("_k").set_index("_k")["advertiser"])
    a["advertiser"] = key.map(name)
    g = a.groupby(["advertiser", "side_group"], as_index=False).agg(
        spend=("w_nc_spend_mid", "sum"), ads=("ad_id", "nunique"),
        platforms=("platform", lambda s: " + ".join(sorted(set(s)))),
        active_7d=("end", lambda s: int((s >= snap - pd.Timedelta(days=7)).sum())),
        last_seen=("end", "max"))
    return g.sort_values("spend", ascending=False).head(n).reset_index(drop=True)


@st.cache_data(ttl=600)
def channel_by_side(race: str) -> pd.DataFrame:
    a = load_ads(race)
    a = a[a["side_group"].isin(SIDES)]
    g = a.groupby(["channel", "side_group"], as_index=False)["w_nc_spend_mid"].sum().rename(columns={"w_nc_spend_mid": "spend"})
    g["channel"] = g["channel"].map(CHANNEL_LABELS).fillna(g["channel"])
    g["share"] = g["spend"] / g.groupby("side_group")["spend"].transform("sum")
    return g


@st.cache_data(ttl=600)
def themes_by_side(race: str) -> pd.DataFrame:
    """Share of each side's (Meta, text-classified) spend that carries each message theme."""
    a = load_ads(race)
    a = a[a["side_group"].isin(SIDES) & (a["platform"] == "Meta")]
    labels = theme_labels()
    tot = a.groupby("side_group")["w_nc_spend_mid"].sum()
    x = a[["side_group", "w_nc_spend_mid", "message_themes"]].explode("message_themes").dropna(subset=["message_themes"])
    g = x.groupby(["side_group", "message_themes"], as_index=False)["w_nc_spend_mid"].sum()
    g["share"] = g["w_nc_spend_mid"] / g["side_group"].map(tot)
    g["theme"] = g["message_themes"].map(lambda t: labels.get(t, t))
    return g.rename(columns={"w_nc_spend_mid": "spend"})[["side_group", "theme", "spend", "share"]]


@st.cache_data(ttl=600)
def audience_by_side(race: str) -> pd.DataFrame:
    """Share of each side's Meta impressions in NC by age x gender (who their ads actually reached)."""
    d = read_table("delivery_by_demo")
    d = d[(d["race"] == race) & d["side_group"].isin(SIDES) & d["gender"].isin(["female", "male"])
          & (d["age"] != "13-17")]
    d["gender"] = d["gender"].map({"female": "Women", "male": "Men"})
    d["share"] = d["impressions"] / d.groupby("side_group")["impressions"].transform("sum")
    return d


@st.cache_data(ttl=600)
def load_creatives(race: str, side: str = "GOP side") -> pd.DataFrame:
    a = load_ads(race)
    a = a[a["side_group"] == side].copy()
    a["has_text"] = a["body"].str.len() > 0
    a = a.sort_values(["start", "nc_spend_mid"], ascending=[False, False])
    if has_table("meta_demographics"):
        d = read_table("meta_demographics")
        d = d[d["ad_id"].isin(a["ad_id"]) & d["gender"].isin(["female", "male"])]
        d = d.sort_values("pct", ascending=False).drop_duplicates("ad_id")
        top = d.set_index("ad_id").apply(lambda r: f"{'Women' if r.gender == 'female' else 'Men'} {r.age}", axis=1)
        a["top_audience"] = a["ad_id"].map(top)
    else:
        a["top_audience"] = None
    return a


@st.cache_data(ttl=600)
def new_activity(race: str, side: str = "GOP side", days: int = 7) -> pd.DataFrame:
    """Advertisers on one side that launched ads in the last `days` days of the snapshot."""
    a = load_ads(race)
    a = a[(a["side_group"] == side) & (a["start"] >= snapshot_date() - pd.Timedelta(days=days))]
    g = a.groupby("advertiser", as_index=False).agg(new_ads=("ad_id", "nunique"), spend=("nc_spend_mid", "sum"),
                                                    platforms=("platform", lambda s: " + ".join(sorted(set(s)))))
    return g.sort_values("spend", ascending=False).reset_index(drop=True)


# ----------------------------------------------------------------------------- region ad spend
@st.cache_data(ttl=600)
def load_region_ad_spend(race: str) -> pd.DataFrame:
    r = read_table("region_ad_spend")
    return r[(r["unit_type"] == unit_type(race)) & (r["race"] == race)]


@st.cache_data(ttl=600)
def region_advertisers(race: str, unit_id: str, n: int = 6) -> pd.DataFrame:
    r = load_region_ad_spend(race)
    r = r[(r["unit_id"] == unit_id) & r["side_group"].isin(SIDES)]
    g = r.groupby(["advertiser", "side_group"], as_index=False)["spend"].sum()
    return g.sort_values("spend", ascending=False).head(n)


@st.cache_data(ttl=600)
def statewide_untargeted(race: str) -> dict:
    """Spend that is not geo-targeted below state level (Meta, and Google ads aimed at all of NC)."""
    a = load_ads(race)
    a = a[a["side_group"].isin(SIDES)]
    geo_ids = set(read_table("google_ad_counties")["ad_id"])
    un = a[~a["ad_id"].isin(geo_ids)]
    return un.groupby("side_group")["w_nc_spend_mid"].sum().reindex(SIDES).fillna(0).to_dict()


@st.cache_data(ttl=600)
def google_cd_reported(unit_id: str) -> float | None:
    """Google's own reported political-ad spend for a congressional district (2026 map, all advertisers)."""
    if not has_table("google_cd_spend_units"):
        return None
    g = read_table("google_cd_spend_units")
    g = g[(g["map_vintage"] == "2026") & (g["unit_id"] == unit_id)]
    return float(g["spend_usd"].sum()) if len(g) else None


# ----------------------------------------------------------------------------- formatting
def fmt_money(x: float) -> str:
    x = float(x or 0)
    if abs(x) >= 1e6:
        return f"${x / 1e6:.1f}M"
    if abs(x) >= 1e3:
        return f"${x / 1e3:.0f}K"
    return f"${x:,.0f}"


def fmt_num(x: float) -> str:
    x = float(x or 0)
    if abs(x) >= 1e6:
        return f"{x / 1e6:.2f}M"
    if abs(x) >= 1e4:
        return f"{x / 1e3:.0f}K"
    return f"{x:,.0f}"
