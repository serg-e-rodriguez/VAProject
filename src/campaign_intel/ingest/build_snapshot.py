"""
Builds the local data snapshot the app reads (data/cache/*.parquet + manifest.json).

    uv run python -m campaign_intel.ingest.build_snapshot            # everything
    uv run python -m campaign_intel.ingest.build_snapshot --skip-meta --skip-google   # re-derive only

Steps: NCSBE (elections + registration) -> Google BigQuery -> Meta Ad Library -> derived tables.
Raw downloads are cached under data/raw/ (git-ignored); --refresh re-downloads them.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import UTC, datetime

import pandas as pd

from campaign_intel.config import CACHE_DIR
from campaign_intel.data.snapshot import MANIFEST, has_table, read_table
from campaign_intel.processing import ads as adsproc
from campaign_intel.processing.themes import theme_labels

logger = logging.getLogger("build_snapshot")
WINDOW_START = "2026-07-01"  # common window for all ad totals (Meta pull starts here)


def _save(name: str, df: pd.DataFrame) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(CACHE_DIR / f"{name}.parquet", index=False)
    logger.info("  wrote %-32s %7d rows", name, len(df))


def step_ncsbe(refresh: bool) -> None:
    from campaign_intel.ingest import ncsbe

    for name, df in ncsbe.build(force_download=refresh).items():
        _save(name, df)


def step_google() -> None:
    from campaign_intel.ingest import google_ads

    for name, df in google_ads.extract().items():
        _save(name, df)


def step_meta(refresh: bool) -> None:
    from campaign_intel.ingest import meta_ads

    for name, df in meta_ads.extract(refresh=refresh).items():
        _save(name, df)


def _cd_spend(df: pd.DataFrame) -> pd.DataFrame:
    """Google geo_spend rows for the 2024 congressional map (the map our shapes use)."""
    rows = []
    for r in df.itertuples():
        lab = str(r.district_label)
        m = re.match(r"NC-(\d+)\s*\((\d{4}) redistricting\)", lab) or \
            re.match(r"North Carolina's (\d+)\w* Congressional District.*?(\d{4})", lab)
        if m:
            rows.append({"unit_id": f"CD{int(m.group(1))}", "map_vintage": m.group(2), "spend_usd": float(r.spend_usd),
                         "label": lab})
    return pd.DataFrame(rows)


def step_derive() -> dict:
    now = pd.Timestamp(datetime.now(UTC).date())
    google, meta = read_table("google_creatives"), read_table("meta_ads")
    demo = read_table("meta_demographics")
    ads = adsproc.add_window_fraction(adsproc.unified_ads(google, meta, now), WINDOW_START)
    _save("ads_unified", ads)

    labels = theme_labels()
    _save("weekly_spend_by_side", adsproc.weekly_by_side(ads, since="2026-06-01"))  # 4 extra weeks for context
    _save("cpm_observed", adsproc.observed_cpm(ads))
    _save("platform_mix", adsproc.platform_mix(ads))
    _save("theme_by_age", adsproc.theme_by_age(ads, demo))
    _save("delivery_by_demo", adsproc.delivery_by_demo(ads, demo))
    adv = adsproc.advertiser_table(ads, now)
    _save("advertisers", adv)
    _save("advertisers_unclassified", adv[adv["side"] == "unclassified"].head(200))
    _save("alerts", adsproc.alerts(ads, now, labels))
    _save("google_cd_spend_units", _cd_spend(read_table("google_cd_spend")))

    sov = ads.groupby("side_group")["w_nc_spend_mid"].sum()
    partisan = sov.get("Dem side", 0) + sov.get("GOP side", 0)
    return {"dem_share_of_voice": float(sov.get("Dem side", 0) / partisan) if partisan else None,
            "ads_total": len(ads),
            "ads_classified_share_of_spend": float(partisan / ads["w_nc_spend_mid"].sum()) if len(ads) else None,
            "window_start": WINDOW_START}


def write_manifest(extra: dict) -> None:
    m = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    m.update(extra)
    m["built_at"] = datetime.now(UTC).isoformat(timespec="minutes")
    if has_table("google_last_updated"):
        m["google_report_updated"] = str(read_table("google_last_updated").iloc[0, 0])
    if has_table("meta_ads"):
        m["meta_latest_ad_start"] = str(read_table("meta_ads")["start"].max())[:10]
    if has_table("statewide"):
        m["statewide"] = {k: (v if isinstance(v, str) else int(v))
                          for k, v in read_table("statewide").iloc[0].to_dict().items()}
    m["tables"] = sorted(p.stem for p in CACHE_DIR.glob("*.parquet"))
    MANIFEST.write_text(json.dumps(m, indent=2, default=str))
    logger.info("Manifest written: %s", MANIFEST)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-ncsbe", action="store_true")
    ap.add_argument("--skip-google", action="store_true")
    ap.add_argument("--skip-meta", action="store_true")
    ap.add_argument("--refresh", action="store_true", help="re-download raw NCSBE / Meta files")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    extra = {}
    if not args.skip_ncsbe:
        logger.info("NCSBE ..."); step_ncsbe(args.refresh)
    if not args.skip_google:
        logger.info("Google BigQuery ..."); step_google(); extra["google_extracted_at"] = datetime.now(UTC).isoformat(timespec="minutes")
    if not args.skip_meta:
        logger.info("Meta Ad Library ..."); step_meta(args.refresh); extra["meta_extracted_at"] = datetime.now(UTC).isoformat(timespec="minutes")
    logger.info("Deriving ...")
    extra.update(step_derive())
    write_manifest(extra)


if __name__ == "__main__":
    main()
