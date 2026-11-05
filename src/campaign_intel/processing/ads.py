"""
Derived ad-landscape tables built from the Google + Meta snapshot (no Streamlit).

- unified ad table (both platforms, NC-apportioned spend bands, side, themes)
- weekly NC spend by side (each ad's NC spend spread evenly over its delivery days: Modeled)
- observed CPM per channel, platform mix, theme x age delivery, alerts
"""

from __future__ import annotations

import re

import pandas as pd

from campaign_intel.config import SEEDS_DIR
from campaign_intel.processing.themes import (
    NON_MESSAGE_THEMES,
    classify_text,
    is_fundraising,
    is_gotv,
)

GOOGLE_CHANNEL = {"VIDEO": "youtube", "TEXT": "search", "IMAGE": "display"}
SIDE_GROUP = {"us": "Dem side", "ally_us": "Dem side", "opponent": "GOP side", "ally_opp": "GOP side",
              "neutral": "Nonpartisan / other", "unclassified": "Unclassified"}
AGE_ORDER = ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]


def load_side_rules() -> list[tuple[re.Pattern, str, str]]:
    df = pd.read_csv(SEEDS_DIR / "advertiser_sides.csv", comment="#", dtype=str)
    return [(re.compile(r.pattern, re.IGNORECASE), r.side, r.label) for r in df.itertuples()]


def classify_side(names: list[str | None], rules) -> tuple[str, str]:
    for pat, side, label in rules:
        for n in names:
            if n and pat.search(str(n).strip()):
                return side, label
    return "unclassified", ""


def unified_ads(google: pd.DataFrame, meta: pd.DataFrame, snapshot_date: pd.Timestamp) -> pd.DataFrame:
    g = pd.DataFrame({
        "platform": "Google", "ad_id": google["ad_id"].astype(str), "advertiser": google["advertiser_name"],
        "advertiser_id": google["advertiser_id"], "byline": None,
        "start": google["date_range_start"], "end": google["date_range_end"],
        "format": google["ad_type"], "channel": google["ad_type"].map(GOOGLE_CHANNEL).fillna("display"),
        "body": "", "url": google["ad_url"], "nc_share": google["nc_share"], "nc_only": google["nc_only"],
        "open_ended": google["open_ended"],
        "spend_low": google["spend_low"], "spend_mid": google["spend_mid"], "spend_high": google["spend_high"],
        "impressions_low": google["impressions_low"], "impressions_mid": google["impressions_mid"],
        "nc_spend_low": google["nc_spend_low"], "nc_spend_mid": google["nc_spend_mid"],
        "nc_spend_high": google["nc_spend_high"], "nc_impressions_mid": google["nc_impressions_mid"],
        "targeting": google["nc_targets"], "age_targeting": google["age_targeting"],
        "gender_targeting": google["gender_targeting"],
    })
    stop = meta["stop"].fillna(snapshot_date)
    m = pd.DataFrame({
        "platform": "Meta", "ad_id": meta["ad_id"].astype(str), "advertiser": meta["page_name"],
        "advertiser_id": meta["page_id"].astype(str), "byline": meta["bylines"],
        "start": meta["start"], "end": stop, "format": "SOCIAL", "channel": "meta",
        "body": meta["body"].fillna(""), "url": meta["snapshot_url"], "nc_share": meta["nc_share"],
        "nc_only": meta["nc_share"] >= 0.9, "open_ended": meta["open_ended"],
        "spend_low": meta["spend_low"], "spend_mid": meta["spend_mid"], "spend_high": meta["spend_high"],
        "impressions_low": meta["impressions_low"], "impressions_mid": meta["impressions_mid"],
        "nc_spend_low": meta["nc_spend_low"], "nc_spend_mid": meta["nc_spend_mid"],
        "nc_spend_high": meta["nc_spend_high"], "nc_impressions_mid": meta["nc_impressions_mid"],
        "targeting": "", "age_targeting": "", "gender_targeting": "",
        "link_caption": meta["link_caption"],
    })
    ads = pd.concat([g, m], ignore_index=True)
    ads["link_caption"] = ads["link_caption"].fillna("")

    rules = load_side_rules()
    keys = ads[["advertiser", "byline"]].drop_duplicates()
    res = [classify_side([r.advertiser, r.byline], rules) for r in keys.itertuples()]
    keys["side"], keys["side_label"] = [x[0] for x in res], [x[1] for x in res]
    ads = ads.merge(keys, on=["advertiser", "byline"], how="left")
    ads["side_group"] = ads["side"].map(SIDE_GROUP)

    ads["themes"] = ads["body"].map(lambda t: classify_text(t) if t else [])
    ads["is_fundraising"] = [is_fundraising(b, c) or ("fundraising" in th)
                             for b, c, th in zip(ads["body"], ads["link_caption"], ads["themes"])]
    ads["is_gotv"] = [is_gotv(b) or ("gotv" in th) for b, th in zip(ads["body"], ads["themes"])]
    ads["message_themes"] = ads["themes"].map(lambda th: [t for t in th if t not in NON_MESSAGE_THEMES])
    ads["start"] = pd.to_datetime(ads["start"]).dt.tz_localize(None)
    ads["end"] = pd.to_datetime(ads["end"]).dt.tz_localize(None).fillna(snapshot_date)
    ads.loc[ads["end"] < ads["start"], "end"] = ads["start"]
    return ads


def weekly_by_side(ads: pd.DataFrame, since: str) -> pd.DataFrame:
    """Spread each ad's NC spend evenly across its delivery days, then sum by week x side group."""
    a = ads[(ads["end"] >= since) & (ads["nc_spend_mid"] > 0)].dropna(subset=["start", "end"]).copy()
    a = a.reset_index(drop=True)
    a["start"] = a["start"].clip(lower=pd.Timestamp(since))
    days = ((a["end"] - a["start"]).dt.days + 1).clip(lower=1).astype(int)
    a = a.loc[a.index.repeat(days)]
    a["day"] = a["start"] + pd.to_timedelta(a.groupby(level=0).cumcount(), unit="D")
    n = days.reindex(a.index).clip(lower=1)
    for c in ["nc_spend_low", "nc_spend_mid", "nc_spend_high"]:
        a[c] = a[c] / n
    a["week_start"] = a["day"].dt.to_period("W-SAT").dt.start_time
    out = a.groupby(["week_start", "side_group", "platform"], as_index=False)[
        ["nc_spend_low", "nc_spend_mid", "nc_spend_high"]].sum()
    return out


def add_window_fraction(ads: pd.DataFrame, since: str) -> pd.DataFrame:
    """Share of each ad's delivery days that fall on/after `since` (spend is prorated by it)."""
    a = ads.copy()
    start, end = a["start"], a["end"]
    total = ((end - start).dt.days + 1).clip(lower=1)
    inside = ((end - start.clip(lower=pd.Timestamp(since))).dt.days + 1).clip(lower=0)
    a["window_frac"] = (inside / total).clip(0, 1).fillna(0.0)
    for c in ["nc_spend_low", "nc_spend_mid", "nc_spend_high"]:
        a[f"w_{c}"] = a[c] * a["window_frac"]
    return a


def observed_cpm(ads: pd.DataFrame) -> pd.DataFrame:
    """Median CPM per channel from ads whose impression range has a real lower bound (>= 10k)."""
    a = ads[(ads["impressions_low"] >= 10_000) & (ads["spend_mid"] > 0)].copy() if "impressions_low" in ads else \
        ads[(ads["impressions_mid"] >= 10_000) & (ads["spend_mid"] > 0)].copy()
    a["cpm"] = a["spend_mid"] / a["impressions_mid"] * 1000
    out = a.groupby("channel").agg(cpm_median=("cpm", "median"), cpm_p25=("cpm", lambda s: s.quantile(.25)),
                                   cpm_p75=("cpm", lambda s: s.quantile(.75)), n_ads=("cpm", "size"))
    return out.reset_index()


def theme_by_age(ads: pd.DataFrame, demo: pd.DataFrame) -> pd.DataFrame:
    """
    Share of each age group's NC impressions (Meta) that carried each message theme, by side group.
    Impressions per (ad, age) = NC impressions mid x the ad's age share.
    """
    m = ads[(ads["platform"] == "Meta") & ads["message_themes"].map(len).gt(0)]
    if m.empty or demo.empty:
        return pd.DataFrame(columns=["side_group", "age", "theme", "pct", "impressions"])
    d = demo[demo["age"].isin(AGE_ORDER)].groupby(["ad_id", "age"], as_index=False)["pct"].sum()
    x = m[["ad_id", "side_group", "nc_impressions_mid", "message_themes"]].merge(d, on="ad_id")
    x["imps"] = x["nc_impressions_mid"] * x["pct"]
    tot = x.groupby(["side_group", "age"])["imps"].sum().rename("tot")
    x = x.explode("message_themes").rename(columns={"message_themes": "theme"})
    g = x.groupby(["side_group", "age", "theme"], as_index=False)["imps"].sum().merge(
        tot.reset_index(), on=["side_group", "age"])
    g["pct"] = g["imps"] / g["tot"] * 100
    return g.rename(columns={"imps": "impressions"})[["side_group", "age", "theme", "pct", "impressions"]]


def delivery_by_demo(ads: pd.DataFrame, demo: pd.DataFrame) -> pd.DataFrame:
    """NC impressions (Meta) by side group x age x gender."""
    m = ads[ads["platform"] == "Meta"][["ad_id", "side_group", "nc_impressions_mid"]]
    x = m.merge(demo, on="ad_id")
    x["impressions"] = x["nc_impressions_mid"] * x["pct"]
    return x.groupby(["side_group", "age", "gender"], as_index=False)["impressions"].sum()


def platform_mix(ads: pd.DataFrame) -> pd.DataFrame:
    labels = {"meta": "Meta (FB / IG)", "youtube": "YouTube (Video)", "search": "Google Search (Text)",
              "display": "Google Display (Image)"}
    g = ads.groupby("channel", as_index=False)[["w_nc_spend_low", "w_nc_spend_mid", "w_nc_spend_high"]].sum()
    g.columns = [c.replace("w_", "") for c in g.columns]
    g["platform"] = g["channel"].map(labels)
    return g


def advertiser_table(ads: pd.DataFrame, snapshot_date: pd.Timestamp) -> pd.DataFrame:
    recent = snapshot_date - pd.Timedelta(days=7)
    def top_theme(s):
        flat = [t for th in s for t in th]
        return pd.Series(flat).mode().iloc[0] if flat else ""
    ads = ads[ads["window_frac"] > 0]
    g = ads.groupby(["advertiser", "side", "side_group"], as_index=False).agg(
        platforms=("platform", lambda s: " + ".join(sorted(set(s)))),
        n_ads=("ad_id", "nunique"),
        active_7d=("end", lambda s: int((s >= recent).sum())),
        nc_spend_low=("w_nc_spend_low", "sum"), nc_spend_mid=("w_nc_spend_mid", "sum"),
        nc_spend_high=("w_nc_spend_high", "sum"), top_theme=("message_themes", top_theme),
        first_seen=("start", "min"), last_seen=("end", "max"),
    )
    return g.sort_values("nc_spend_mid", ascending=False).reset_index(drop=True)


def alerts(ads: pd.DataFrame, snapshot_date: pd.Timestamp, labels: dict[str, str]) -> pd.DataFrame:
    """Rule-based alerts from the snapshot: new GOP-side flights, spend surges, theme shifts."""
    rows = []
    gop = ads[ads["side_group"] == "GOP side"]
    d7 = snapshot_date - pd.Timedelta(days=7)
    d14 = snapshot_date - pd.Timedelta(days=14)
    new = gop[gop["start"] >= d7]
    for adv, grp in new.groupby("advertiser"):
        spend = grp["nc_spend_mid"].sum()
        if spend >= 10_000 or len(grp) >= 5:
            rows.append({"severity": "high" if spend >= 50_000 else "medium", "type": "New flight",
                         "advertiser": adv,
                         "text": f"{adv}: {len(grp)} new ads in the last 7 days (≈${spend:,.0f} NC, modeled).",
                         "date": grp["start"].max()})
    def theme_share(df):
        flat = df.explode("message_themes").dropna(subset=["message_themes"])
        return flat.groupby("message_themes")["nc_spend_mid"].sum() / max(1.0, flat["nc_spend_mid"].sum())
    now, prev = theme_share(gop[gop["start"] >= d7]), theme_share(gop[(gop["start"] >= d14) & (gop["start"] < d7)])
    for th, s in now.items():
        p = prev.get(th, 0.0)
        if s - p >= 0.08:
            rows.append({"severity": "medium", "type": "Theme shift", "advertiser": "GOP side",
                         "text": f"GOP-side spend on {labels.get(th, th)} rose to {s:.0%} of new-ad spend (from {p:.0%} the week before).",
                         "date": snapshot_date})
    out = pd.DataFrame(rows, columns=["severity", "type", "advertiser", "text", "date"])
    out["alert_id"] = (out["type"] + "|" + out["advertiser"]).str.lower()
    return out.sort_values(["severity", "date"], ascending=[True, False]).reset_index(drop=True)
