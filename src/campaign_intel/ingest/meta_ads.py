"""
Meta Ad Library API extraction for the NC snapshot (POLITICAL_AND_ISSUE_ADS).

Verified API behaviour (Graph API v23, Nov 2026):
- The endpoint requires `search_terms` or `search_page_ids`; `search_terms="*"` matches all.
- `delivery_by_region=['North Carolina']` returns every ad with *any* NC delivery, so most
  results are national ads with a tiny NC share (median ~2.5%). `region_distribution` is gone;
  each ad's `delivery_by_region` gives its NC percentage.

Two-stage pull:
1. Seed scan (light fields) over the window -> NC share per ad -> NC-focused pages
   (pages whose ads put >= PAGE_FOCUS_MIN of their spend in NC).
2. Full-field fetch of every ad from those pages, plus the full-field records from the seed
   for big national ads, so totals include NC-apportioned national money.

NC spend per ad = spend band x NC delivery share (Modeled).
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

from campaign_intel.config import DATA_DIR, META_AD_TOKEN

logger = logging.getLogger(__name__)

API = "https://graph.facebook.com/v23.0/ads_archive"
RAW_DIR = DATA_DIR / "raw" / "meta"
WINDOW_START = "2026-07-01"
PAGE_FOCUS_MIN = 0.5
FULL_FIELDS = ",".join([
    "id", "page_id", "page_name", "bylines", "ad_creation_time", "ad_delivery_start_time",
    "ad_delivery_stop_time", "spend", "impressions", "demographic_distribution", "delivery_by_region",
    "ad_creative_bodies", "ad_creative_link_captions", "ad_creative_link_titles", "publisher_platforms",
    "ad_snapshot_url",
])
SEED_FIELDS = "id,page_id,page_name,bylines,spend,delivery_by_region"


def _params(fields: str, start: str, **extra) -> dict[str, Any]:
    p = {
        "access_token": META_AD_TOKEN,
        "ad_reached_countries": "['US']",
        "ad_type": "POLITICAL_AND_ISSUE_ADS",
        "delivery_by_region": "['North Carolina']",
        "ad_delivery_date_min": start,
        "ad_active_status": "ALL",
        "fields": fields,
        "limit": 500,
    }
    p.update(extra)
    return p


def _get(url: str, params: dict | None, retries: int = 6) -> dict:
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=90)
            if r.status_code == 200:
                return r.json()
            err = r.json().get("error", {})
            logger.warning("Meta API %s: %s", r.status_code, err.get("message", r.text[:200]))
            if err.get("code") in (190,):  # invalid / expired token
                raise RuntimeError(f"Meta token rejected: {err.get('message')}")
            if params and params.get("limit", 0) > 100 and err.get("code") in (1, 2, 500, None):
                params = {**params, "limit": max(100, params["limit"] // 2)}
        except requests.RequestException as exc:
            logger.warning("Meta request failed: %s", exc)
        time.sleep(min(60, 5 * 2**attempt))
    raise RuntimeError("Meta API: retries exhausted")


def iter_ads(params: dict, max_pages: int | None = None) -> Iterator[dict]:
    url, p, n = API, params, 0
    while url:
        payload = _get(url, p)
        yield from payload.get("data", [])
        n += 1
        if max_pages and n >= max_pages:
            break
        url = payload.get("paging", {}).get("next")
        p = None  # `next` carries every parameter


def nc_share(dbr: Any) -> float:
    if not isinstance(dbr, list):
        return np.nan
    for item in dbr:
        if item.get("region") == "North Carolina":
            return float(item.get("percentage", 0) or 0)
    return 0.0


def _bound(d: Any, key: str) -> float:
    try:
        return float((d or {}).get(key))
    except (TypeError, ValueError):
        return np.nan


def _cache_jsonl(path: Path, rows: Iterator[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
            n += 1
            if n % 5000 == 0:
                logger.info("  %s: %d ads", path.name, n)
    return n


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open() as fh:
        for line in fh:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:  # a scan stopped mid-write leaves one partial line
                continue
    return rows


# Keyword scans that surface small NC-focused pages a capped wildcard scan can miss.
NC_TERMS = ["North Carolina", "NC", "Raleigh", "Charlotte", "Greensboro", "Durham", "Wilmington", "Asheville",
            "Fayetteville", "Winston-Salem", "Cooper", "Whatley", "Tillis", "Stein", "NCGOP", "NCDP",
            "General Assembly", "Tar Heel", "Carolina"]


def keyword_seed(start: str = WINDOW_START, terms: list[str] = NC_TERMS, max_pages_per_term: int = 40,
                 refresh: bool = False) -> pd.DataFrame:
    path = RAW_DIR / f"seed_terms_{start}.jsonl"
    if refresh or not path.exists():
        def gen():
            for term in terms:
                logger.info("  keyword seed: %s", term)
                yield from iter_ads(_params(SEED_FIELDS, start, search_terms=term), max_pages_per_term)
        _cache_jsonl(path, gen())
    return _seed_frame(_read_jsonl(path))


def _seed_frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{
        "ad_id": r.get("id"), "page_id": r.get("page_id"), "page_name": r.get("page_name"),
        "bylines": r.get("bylines"),
        "spend_low": _bound(r.get("spend"), "lower_bound"), "spend_high": _bound(r.get("spend"), "upper_bound"),
        "nc_share": nc_share(r.get("delivery_by_region")),
    } for r in rows]).drop_duplicates("ad_id")


def seed_scan(start: str = WINDOW_START, max_pages: int | None = 600, refresh: bool = False) -> pd.DataFrame:
    """Wildcard scan (newest first), capped at max_pages x 500 ads to keep the build under ~1 hour."""
    path = RAW_DIR / f"seed_{start}.jsonl"
    if refresh or not path.exists():
        n = _cache_jsonl(path, iter_ads(_params(SEED_FIELDS, start, search_terms="*"), max_pages))
        logger.info("Seed scan: %d ads", n)
    return _seed_frame(_read_jsonl(path))


def nc_focused_pages(seed: pd.DataFrame, min_share: float = PAGE_FOCUS_MIN) -> pd.DataFrame:
    s = seed.copy()
    s["spend_mid"] = np.where(s["spend_high"].notna(), (s["spend_low"] + s["spend_high"]) / 2, s["spend_low"] * 1.5)
    s["nc_spend_mid"] = s["spend_mid"] * s["nc_share"].fillna(0)
    g = s.groupby("page_id").agg(page_name=("page_name", "first"), n_ads=("ad_id", "count"),
                                 spend_mid=("spend_mid", "sum"), nc_spend_mid=("nc_spend_mid", "sum"))
    g["nc_share_page"] = g["nc_spend_mid"] / g["spend_mid"].replace(0, np.nan)
    return g[g["nc_share_page"] >= min_share].reset_index().sort_values("nc_spend_mid", ascending=False)


def fetch_full(page_ids: list[str], start: str = WINDOW_START, refresh: bool = False) -> list[dict]:
    path = RAW_DIR / f"full_{start}.jsonl"
    if refresh or not path.exists():
        def gen():
            for i in range(0, len(page_ids), 10):
                batch = page_ids[i:i + 10]
                yield from iter_ads(_params(FULL_FIELDS, start, search_page_ids=json.dumps(batch)))
        n = _cache_jsonl(path, gen())
        logger.info("Full fetch: %d ads from %d pages", n, len(page_ids))
    return _read_jsonl(path)


def to_frames(raw: list[dict]) -> dict[str, pd.DataFrame]:
    ads, demo = [], []
    for r in raw:
        bodies = r.get("ad_creative_bodies") or []
        captions = r.get("ad_creative_link_captions") or []
        sl, sh = _bound(r.get("spend"), "lower_bound"), _bound(r.get("spend"), "upper_bound")
        il, ih = _bound(r.get("impressions"), "lower_bound"), _bound(r.get("impressions"), "upper_bound")
        snap = (r.get("ad_snapshot_url") or "").split("access_token=")[0].rstrip("&?")
        ads.append({
            "ad_id": r.get("id"), "page_id": r.get("page_id"), "page_name": r.get("page_name"),
            "bylines": r.get("bylines"),
            "created": r.get("ad_creation_time"), "start": r.get("ad_delivery_start_time"),
            "stop": r.get("ad_delivery_stop_time"),
            "spend_low": sl, "spend_high": sh, "impressions_low": il, "impressions_high": ih,
            "nc_share": nc_share(r.get("delivery_by_region")),
            "body": bodies[0] if bodies else "",
            "link_caption": captions[0] if captions else "",
            "platforms": ",".join(r.get("publisher_platforms") or []),
            "snapshot_url": snap,
        })
        for d in r.get("demographic_distribution") or []:
            demo.append({"ad_id": r.get("id"), "age": d.get("age"), "gender": d.get("gender"),
                         "pct": float(d.get("percentage", 0) or 0)})
    a = pd.DataFrame(ads).drop_duplicates("ad_id")
    for c in ["created", "start", "stop"]:
        a[c] = pd.to_datetime(a[c], errors="coerce")
    a["open_ended"] = a["spend_high"].isna()
    a["spend_mid"] = np.where(a["open_ended"], a["spend_low"] * 1.5, (a["spend_low"] + a["spend_high"]) / 2)
    a["spend_high"] = a["spend_high"].fillna(a["spend_low"] * 2)
    a["impressions_high"] = a["impressions_high"].fillna(a["impressions_low"] * 2)
    a["impressions_mid"] = (a["impressions_low"] + a["impressions_high"]) / 2
    share = a["nc_share"].fillna(0)
    for c in ["spend_low", "spend_mid", "spend_high", "impressions_low", "impressions_mid", "impressions_high"]:
        a[f"nc_{c}"] = a[c] * share
    d = pd.DataFrame(demo, columns=["ad_id", "age", "gender", "pct"])
    return {"meta_ads": a, "meta_demographics": d}


def extract(start: str = WINDOW_START, max_seed_pages: int | None = 600, refresh: bool = False):
    if not META_AD_TOKEN:
        raise RuntimeError("META_AD_TOKEN is not set in .env")
    seed = pd.concat([seed_scan(start, max_seed_pages, refresh), keyword_seed(start, refresh=refresh)],
                     ignore_index=True).drop_duplicates("ad_id")
    pages = nc_focused_pages(seed)
    logger.info("NC-focused pages: %d (of %d pages in seed)", len(pages), seed["page_id"].nunique())
    raw = fetch_full(pages["page_id"].astype(str).tolist(), start, refresh)
    frames = to_frames(raw)
    frames["meta_seed_pages"] = seed.groupby(["page_id", "page_name"], as_index=False).agg(
        n_ads=("ad_id", "count"), spend_low=("spend_low", "sum"))
    frames["meta_nc_pages"] = pages
    # National money reaching NC from pages NOT in the focused set (seed has spend + nc share)
    other = seed[~seed["page_id"].isin(pages["page_id"])].copy()
    other["spend_mid"] = np.where(other["spend_high"].notna(), (other["spend_low"] + other["spend_high"]) / 2,
                                  other["spend_low"] * 1.5)
    other["nc_spend_mid"] = other["spend_mid"] * other["nc_share"].fillna(0)
    frames["meta_national_nc_spend"] = pd.DataFrame([{
        "n_ads": len(other), "nc_spend_mid": float(other["nc_spend_mid"].sum())}])
    return frames
