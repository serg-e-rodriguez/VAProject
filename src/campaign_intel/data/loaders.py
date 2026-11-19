"""
Cached, race-aware loaders for the pages. Everything is read from the local snapshot (data/cache);
pages only lay out what these return.

Conventions
-----------
- `race` is "senate" or "house" (config.RACES). Ad spend is filtered to ads attributed to that race
  (nominee committees, race-specific PACs / party committees, nominee named in the ad text, or
  Google district targeting). Party / issue / state-race money is reported separately as "other".
- Ad spend is NC-apportioned and limited to the analysis timeframe picked in the sidebar (default: the campaign
  window, Jul 1, 2026 to the snapshot date): `w_nc_spend_mid`. Every ad loader is cached per timeframe
  (`_tf_cached`), and spend / impressions are pro-rated by the share of each ad's delivery days inside it.
  The War Room keeps its own planning date and uses `load_ads_cycle` (the campaign window) instead.
- Region = county (Senate) or congressional district (House).
"""

from __future__ import annotations

import functools

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


# ----------------------------------------------------------------------------- analysis timeframe
TIMEFRAME_FLOOR = pd.Timestamp("2024-01-01")  # earliest date the sidebar offers (stored ads begin in 2025)


def default_timeframe() -> tuple[pd.Timestamp, pd.Timestamp]:
    return CYCLE_START, snapshot_date()


def timeframe() -> tuple[pd.Timestamp, pd.Timestamp]:
    """The analysis timeframe picked in the sidebar (inclusive days), or the campaign window."""
    tf = st.session_state.get("timeframe")
    if not tf or len(tf) != 2:
        return default_timeframe()
    s, e = pd.Timestamp(tf[0]), pd.Timestamp(tf[1])
    return (s, e) if s <= e else (e, s)


def timeframe_label(tf: tuple[pd.Timestamp, pd.Timestamp] | None = None) -> str:
    s, e = tf or timeframe()
    return f"{s:%b %-d, %Y} – {e:%b %-d, %Y}"


def _tf_key() -> tuple[str, str]:
    s, e = timeframe()
    return s.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d")


def _tf_cached(fn):
    """st.cache_data that also keys on the sidebar timeframe (the wrapped function reads it via timeframe())."""
    def inner(tf, *args, **kwargs):  # `tf` only feeds the cache key
        return fn(*args, **kwargs)

    inner.__qualname__ = f"{fn.__qualname__}__tf"  # one cache per wrapped function
    inner.__module__ = fn.__module__
    cached = st.cache_data(ttl=600, show_spinner=False)(inner)

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return cached(_tf_key(), *args, **kwargs)

    wrapper.clear = cached.clear
    return wrapper


def window_ads(a: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Pro-rate each ad's NC spend / impressions by the share of its delivery days inside [start, end]."""
    a = a.copy()
    s0, e0 = a["start"], a["end"].fillna(a["start"])
    days = ((e0 - s0).dt.days + 1).clip(lower=1)
    inside = ((e0.clip(upper=end) - s0.clip(lower=start)).dt.days + 1).clip(lower=0)
    a["window_frac"] = (inside / days).clip(0, 1).fillna(0.0)
    for c in ["nc_spend_low", "nc_spend_mid", "nc_spend_high", "nc_impressions_mid"]:
        a[f"w_{c}"] = a[c].fillna(0) * a["window_frac"]
    return a


@st.cache_data(ttl=600, show_spinner=False)
def stored_coverage() -> dict:
    """What the stored snapshot holds per source: first / last delivery day and ad count."""
    a = read_table("ads_unified")
    out = {}
    for plat, src in (("Google", "google"), ("Meta", "meta")):
        x = a[a["platform"] == plat]
        out[src] = {"first": x["start"].min() if len(x) else None, "last": x["end"].max() if len(x) else None,
                    "ads": len(x)}
    return out


@_tf_cached
def coverage(race: str) -> dict:
    """Per source, what falls inside the timeframe for this race: ads, NC spend, and whether there is any data.
    NCSBE / survey files are fixed vintages and are not date-filtered."""
    s, e = timeframe()
    a = load_ads(race)
    store = stored_coverage()
    out = {}
    for plat, src in (("Google", "google"), ("Meta", "meta")):
        x = a[a["platform"] == plat]
        out[src] = {"ads": int(x["ad_id"].nunique()), "spend": float(x["w_nc_spend_mid"].sum()),
                    "has_data": bool(len(x)), **{f"stored_{k}": v for k, v in store[src].items()}}
    out["any"] = out["google"]["has_data"] or out["meta"]["has_data"]
    out["start"], out["end"] = s, e
    out["after_snapshot"] = e > snapshot_date()
    return out


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
@_tf_cached
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
def _all_ads() -> pd.DataFrame:
    return read_table("ads_unified")


@_tf_cached
def load_ads(race: str | None = None) -> pd.DataFrame:
    """Ads delivered inside the sidebar timeframe (spend pro-rated to it), optionally for one race."""
    a = _all_ads()
    a = a[a["race"] == race] if race else a
    a = window_ads(a, *timeframe())
    return a[a["window_frac"] > 0].reset_index(drop=True)


@st.cache_data(ttl=600)
def load_ads_cycle(race: str | None = None) -> pd.DataFrame:
    """Ads in the campaign window (Jul 1, 2026 to the snapshot), independent of the sidebar timeframe.
    The War Room uses this: it works from its own planning date."""
    a = _all_ads()
    a = a[a["race"] == race] if race else a
    a = window_ads(a, CYCLE_START, snapshot_date())
    return a[a["window_frac"] > 0].reset_index(drop=True)


def _days(a: pd.DataFrame, s: pd.Timestamp | None = None, e: pd.Timestamp | None = None) -> pd.DataFrame:
    """One row per ad x delivery day inside [s, e] (default: the timeframe), with that day's share of its NC spend."""
    if s is None or e is None:
        s, e = timeframe()
    a = a[a["nc_spend_mid"].fillna(0) > 0].dropna(subset=["start"]).copy()
    if a.empty:
        return a.assign(day=pd.Series(dtype="datetime64[ns]"), per_day=pd.Series(dtype=float))
    total = ((a["end"] - a["start"]).dt.days + 1).clip(lower=1)
    a["per_day"] = a["nc_spend_mid"] / total
    a["start"] = a["start"].clip(lower=s)
    a["end"] = a["end"].clip(upper=e)
    a = a[a["end"] >= a["start"]].reset_index(drop=True)
    n = ((a["end"] - a["start"]).dt.days + 1).astype(int)
    a = a.loc[a.index.repeat(n)]
    a["day"] = a["start"] + pd.to_timedelta(a.groupby(level=0).cumcount(), unit="D")
    return a


def _last_full_week() -> pd.Timestamp:
    end = min(timeframe()[1], snapshot_date())
    return (end - pd.Timedelta(days=6)).to_period("W-SAT").start_time


@_tf_cached
def spend_summary(race: str) -> dict:
    a = load_ads(race)
    by = a.groupby("side_group")["w_nc_spend_mid"].sum()
    dem, gop = float(by.get("Dem side", 0)), float(by.get("GOP side", 0))
    w = weekly_by_side(race)
    p = w.pivot_table(index="week_start", columns="side_group", values="spend", aggfunc="sum").reindex(columns=SIDES).fillna(0)
    last4, prev4 = p.tail(4).sum(), p.iloc[-8:-4].sum()
    last4, prev4 = last4.reindex(SIDES).fillna(0), prev4.reindex(SIDES).fillna(0)

    def share(x):
        return x["Dem side"] / x.sum() if x.sum() else np.nan

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
        "weeks": len(p),
    }


def _last_end(a: pd.DataFrame, side: str) -> pd.Timestamp | None:
    """Last delivery day inside the timeframe of any meaningful ad (≥ $1K NC spend in it) on one side."""
    x = a[(a["side_group"] == side) & (a["w_nc_spend_mid"] >= 1000)]
    return min(x["end"].max(), timeframe()[1]) if len(x) else None


def went_dark(s: dict, side: str = "gop", days: int = 14) -> str | None:
    """'Oct 03' if that side ran no meaningful ads in the last `days`+ days of the timeframe."""
    last = s.get(f"{side}_last")
    end = min(timeframe()[1], snapshot_date())
    if last is not None and pd.notna(last) and last < end - pd.Timedelta(days=days):
        return f"{last:%b %d}"
    return None


@_tf_cached
def weekly_by_side(race: str) -> pd.DataFrame:
    """Spend per week x side x platform inside the timeframe (each ad's spend spread over its delivery days)."""
    d = _days(load_ads(race))
    d = d[d["side_group"].isin(SIDES)]
    if d.empty:
        return pd.DataFrame(columns=["week_start", "side_group", "platform", "spend"])
    d["week_start"] = d["day"].dt.to_period("W-SAT").dt.start_time
    w = d.groupby(["week_start", "side_group", "platform"], as_index=False)["per_day"].sum()
    w = w.rename(columns={"per_day": "spend"})
    return w[w["week_start"] <= _last_full_week()].reset_index(drop=True)


@_tf_cached
def weekly_by_channel(race: str, side: str) -> pd.DataFrame:
    """Spend per week x channel for one side (each ad's spend spread over its delivery days)."""
    a = load_ads(race)
    d = _days(a[a["side_group"] == side])
    if d.empty:
        return pd.DataFrame(columns=["week_start", "channel", "spend"])
    d["week_start"] = d["day"].dt.to_period("W-SAT").dt.start_time
    out = d.groupby(["week_start", "channel"], as_index=False)["per_day"].sum().rename(columns={"per_day": "spend"})
    out["channel"] = out["channel"].map(CHANNEL_LABELS).fillna(out["channel"])
    return out[out["week_start"] <= _last_full_week()].reset_index(drop=True)


@_tf_cached
def top_advertisers(race: str, side: str | None = None, n: int = 10) -> pd.DataFrame:
    a = load_ads(race)
    a = a[a["side_group"].isin([side] if side else SIDES)].copy()
    cols = ["advertiser", "side_group", "spend", "ads", "platforms", "active_7d", "last_seen"]
    if a.empty:
        return pd.DataFrame(columns=cols)
    end = min(timeframe()[1], snapshot_date())
    # Google and Meta spell the same committee differently ("COOPER FOR NORTH CAROLINA" vs
    # "Cooper for North Carolina"): merge on a case/space-folded key, show the biggest spender's spelling.
    key = a["advertiser"].str.casefold().str.split().str.join(" ")
    name = (a.assign(_k=key).groupby(["_k", "advertiser"])["w_nc_spend_mid"].sum()
            .sort_values(ascending=False).reset_index().drop_duplicates("_k").set_index("_k")["advertiser"])
    a["advertiser"] = key.map(name)
    g = a.groupby(["advertiser", "side_group"], as_index=False).agg(
        spend=("w_nc_spend_mid", "sum"), ads=("ad_id", "nunique"),
        platforms=("platform", lambda s: " + ".join(sorted(set(s)))),
        active_7d=("end", lambda s: int((s >= end - pd.Timedelta(days=7)).sum())),
        last_seen=("end", lambda s: min(s.max(), end)))
    return g.sort_values("spend", ascending=False).head(n).reset_index(drop=True)


@_tf_cached
def channel_by_side(race: str) -> pd.DataFrame:
    a = load_ads(race)
    a = a[a["side_group"].isin(SIDES)]
    g = a.groupby(["channel", "side_group"], as_index=False)["w_nc_spend_mid"].sum().rename(columns={"w_nc_spend_mid": "spend"})
    g["channel"] = g["channel"].map(CHANNEL_LABELS).fillna(g["channel"])
    g["share"] = g["spend"] / g.groupby("side_group")["spend"].transform("sum")
    return g


@_tf_cached
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


@_tf_cached
def audience_by_side(race: str) -> pd.DataFrame:
    """Share of each side's Meta impressions in NC by age x gender (who their ads actually reached),
    from each ad's delivery shares x its impressions inside the timeframe."""
    cols = ["side_group", "race", "age", "gender", "impressions", "share"]
    a = load_ads(race)
    a = a[(a["platform"] == "Meta") & a["side_group"].isin(SIDES)][["ad_id", "side_group", "race",
                                                                      "w_nc_impressions_mid"]]
    if a.empty or not has_table("meta_demographics"):
        return pd.DataFrame(columns=cols)
    d = read_table("meta_demographics")
    d = d[d["gender"].isin(["female", "male"]) & (d["age"] != "13-17")]
    x = a.merge(d, on="ad_id")
    x["impressions"] = x["w_nc_impressions_mid"] * x["pct"]
    g = x.groupby(["side_group", "race", "age", "gender"], as_index=False)["impressions"].sum()
    g["gender"] = g["gender"].map({"female": "Women", "male": "Men"})
    g["share"] = g["impressions"] / g.groupby("side_group")["impressions"].transform("sum")
    return g[cols]


@_tf_cached
def load_creatives(race: str, side: str = "GOP side") -> pd.DataFrame:
    a = load_ads(race)
    a = a[a["side_group"] == side].copy()
    a["has_text"] = a["body"].str.len() > 0
    a = a.sort_values(["start", "nc_spend_mid"], ascending=[False, False])
    if has_table("meta_demographics") and len(a):
        d = read_table("meta_demographics")
        d = d[d["ad_id"].isin(a["ad_id"]) & d["gender"].isin(["female", "male"])]
        d = d.sort_values("pct", ascending=False).drop_duplicates("ad_id")
        top = d.set_index("ad_id").apply(lambda r: f"{'Women' if r.gender == 'female' else 'Men'} {r.age}", axis=1) \
            if len(d) else pd.Series(dtype=object)
        a["top_audience"] = a["ad_id"].map(top)
    else:
        a["top_audience"] = None
    return a


@_tf_cached
def new_activity(race: str, side: str = "GOP side", days: int = 7) -> pd.DataFrame:
    """Advertisers on one side that launched ads in the last `days` days of the timeframe."""
    a = load_ads(race)
    end = min(timeframe()[1], snapshot_date())
    a = a[(a["side_group"] == side) & (a["start"] >= end - pd.Timedelta(days=days))]
    g = a.groupby("advertiser", as_index=False).agg(new_ads=("ad_id", "nunique"), spend=("nc_spend_mid", "sum"),
                                                    platforms=("platform", lambda s: " + ".join(sorted(set(s)))))
    return g.sort_values("spend", ascending=False).reset_index(drop=True)


# ----------------------------------------------------------------------------- region ad spend
@_tf_cached
def load_region_ad_spend(race: str) -> pd.DataFrame:
    """Geo-targeted (Google) spend inside the timeframe per region x advertiser x side x channel."""
    from campaign_intel.processing.ads import region_ad_spend

    cols = ["unit_type", "unit_id", "advertiser", "side_group", "race", "channel", "spend"]
    a = load_ads(race)
    if a.empty or not has_table("google_ad_counties"):
        return pd.DataFrame(columns=cols)
    r = region_ad_spend(a, read_table("google_ad_counties"), read_table("county_district_crosswalk"))
    return r[(r["unit_type"] == unit_type(race)) & (r["race"] == race)].reset_index(drop=True)


@_tf_cached
def region_advertisers(race: str, unit_id: str, n: int = 6) -> pd.DataFrame:
    r = load_region_ad_spend(race)
    r = r[(r["unit_id"] == unit_id) & r["side_group"].isin(SIDES)]
    g = r.groupby(["advertiser", "side_group"], as_index=False)["spend"].sum()
    return g.sort_values("spend", ascending=False).head(n)


@_tf_cached
def statewide_untargeted(race: str) -> dict:
    """Spend that is not geo-targeted below state level (Meta, and Google ads aimed at all of NC)."""
    a = load_ads(race)
    a = a[a["side_group"].isin(SIDES)]
    geo_ids = set(read_table("google_ad_counties")["ad_id"])
    un = a[~a["ad_id"].isin(geo_ids)]
    return un.groupby("side_group")["w_nc_spend_mid"].sum().reindex(SIDES).fillna(0).to_dict()


@st.cache_data(ttl=600)
def google_cd_reported(unit_id: str) -> float | None:
    """Google's own reported political-ad spend for a congressional district (2026 map, all advertisers).
    A cycle total from Google's report: it is not limited to the timeframe."""
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


# ----------------------------------------------------------------------------- war room (rewind)
@st.cache_data(ttl=600)
def spend_as_of(race: str, asof: str) -> dict:
    """Race ad spend by side before `asof` (what a planner knew then), the 4-week pace, and after it.
    War Room input: the campaign window, independent of the sidebar timeframe."""
    d = _days(load_ads_cycle(race), CYCLE_START, snapshot_date())
    d = d[d["side_group"].isin(SIDES)]
    d["week_start"] = d["day"].dt.to_period("W-SAT").dt.start_time
    w = d.groupby(["week_start", "side_group"], as_index=False)["per_day"].sum().rename(columns={"per_day": "spend"})
    w = w[w["week_start"] <= (snapshot_date() - pd.Timedelta(days=6)).to_period("W-SAT").start_time]
    p = w.pivot_table(index="week_start", columns="side_group", values="spend", aggfunc="sum").reindex(columns=SIDES).fillna(0)
    cut = pd.Timestamp(asof)
    before, after = p[p.index < cut], p[p.index >= cut]
    last4 = before.tail(4)
    tot = before.sum()
    return {
        "dem": float(tot["Dem side"]), "gop": float(tot["GOP side"]),
        "dem_4w": float(last4["Dem side"].sum()), "gop_4w": float(last4["GOP side"].sum()),
        "gop_share": float(tot["GOP side"] / tot.sum()) if tot.sum() else 0.5,
        "dem_after": float(after["Dem side"].sum()), "gop_after": float(after["GOP side"].sum()),
    }
