"""
Meta / Facebook Ad Library API Loader - North Carolina Focus
Fetches political and issue ads from the Meta Graph API /ads_archive endpoint,
restricted to North Carolina with mock fallback.
"""

from __future__ import annotations

import logging
from typing import Optional
import numpy as np
import pandas as pd
import requests
import streamlit as st

try:
    from src.config import META_AD_TOKEN
except ModuleNotFoundError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from config import META_AD_TOKEN

logger = logging.getLogger(__name__)

META_API_ENDPOINT = "https://graph.facebook.com/v21.0/ads_archive"

NC_META_ADVERTISERS = [
    ("META_NC01", "Carolina Forward PAC"),
    ("META_NC02", "NC Values Coalition Action Fund"),
    ("META_NC03", "Citizens for Clean Energy NC"),
    ("META_NC04", "Tar Heel Voter Project"),
    ("META_NC05", "Defend North Carolina Leadership Fund"),
    ("META_NC06", "Working Families for North Carolina"),
    ("META_NC07", "Main Street North Carolina"),
]

NC_META_MARKETS = [
    ("Charlotte DMA", "Charlotte, North Carolina"),
    ("Raleigh-Durham-Fayetteville DMA", "Raleigh, North Carolina"),
    ("Greensboro-High Point-Winston-Salem DMA", "Greensboro, North Carolina"),
    ("Greenville-New Bern-Washington DMA", "Greenville, North Carolina"),
    ("Wilmington DMA", "Wilmington, North Carolina"),
    ("Asheville DMA", "Asheville, North Carolina"),
]
NC_META_MARKET_PROBS = [0.35, 0.30, 0.16, 0.08, 0.06, 0.05]


def generate_mock_meta_ads(n: int = 800) -> pd.DataFrame:
    """Generates synthetic Meta political ads data for North Carolina."""
    np.random.seed(99)

    age_cohorts = [
        "18-24", "25-34", "35-44", "45-54", "55-64", "≥65",
        "18-24, 25-34", "25-34, 35-44", "35-44, 45-54", "45-54, 55-64", "55-64, ≥65",
        "Not targeted"
    ]
    age_probs = [0.04, 0.12, 0.18, 0.23, 0.25, 0.14, 0.02, 0.01, 0.007, 0.002, 0.001, 0.000]

    gender_options = ["Female, Male", "Female", "Male", "Not targeted"]
    gender_probs = [0.55, 0.25, 0.18, 0.02]

    impression_buckets = [
        "≤10000", "10000-25000", "25000-50000", "50000-100000",
        "100000-500000", "500000-1000000"
    ]
    bucket_probs = [0.28, 0.26, 0.22, 0.14, 0.08, 0.02]

    records = []
    base_date = pd.Timestamp("2024-02-01")

    for i in range(n):
        adv_id, adv_name = NC_META_ADVERTISERS[np.random.choice(len(NC_META_ADVERTISERS))]
        start_offset = int(np.random.exponential(scale=70)) % 270
        start_date = base_date + pd.Timedelta(days=start_offset)
        duration = int(np.random.gamma(shape=2.5, scale=5)) + 1
        end_date = start_date + pd.Timedelta(days=duration)
        
        bucket = np.random.choice(impression_buckets, p=bucket_probs)
        min_spend = float(np.random.choice([150, 300, 750, 1500, 3500, 8000, 15000]))
        max_spend = min_spend * float(np.random.choice([1.4, 2.0, 2.8])) if np.random.rand() > 0.10 else None

        market_idx = np.random.choice(len(NC_META_MARKETS), p=NC_META_MARKET_PROBS)
        dma_name, geo_str = NC_META_MARKETS[market_idx]

        records.append({
            "ad_id": f"CR-META-NC-{i+50000:05d}",
            "ad_url": f"https://www.facebook.com/ads/library/?id=CR-META-NC-{i+50000:05d}",
            "ad_type": np.random.choice(["VIDEO", "IMAGE"], p=[0.60, 0.40]),
            "regions": "NC",
            "advertiser_id": adv_id,
            "advertiser_name": adv_name,
            "date_range_start": start_date.strftime("%Y-%m-%d"),
            "date_range_end": end_date.strftime("%Y-%m-%d"),
            "num_of_days": duration,
            "impressions": bucket,
            "spend_range_min_usd": min_spend,
            "spend_range_max_usd": max_spend,
            "age_targeting": np.random.choice(age_cohorts, p=age_probs),
            "gender_targeting": np.random.choice(gender_options, p=gender_probs),
            "geo_targeting_included": geo_str,
            "geo_targeting_excluded": "None",
            "nc_dma": dma_name,
            "platform": "Meta"
        })

    return pd.DataFrame(records)


@st.cache_data(ttl=1800, show_spinner=False)
def load_meta_ads(max_records: int = 1000) -> tuple[pd.DataFrame, bool]:
    """
    Queries Meta Ad Library API for political and issue ads in North Carolina.
    Returns (DataFrame, is_live_data). If token is invalid or rate limited, returns (mock_data, False).
    """
    if not META_AD_TOKEN or len(META_AD_TOKEN) < 20:
        logger.info("Meta token not set; returning synthetic NC Meta political ads.")
        return generate_mock_meta_ads(n=max_records), False

    params = {
        "access_token": META_AD_TOKEN,
        "ad_type": "POLITICAL_AND_ISSUE_ADS",
        "ad_reached_countries": "['US']",
        "search_terms": "North Carolina",
        "fields": "id,ad_creation_time,ad_delivery_start_time,ad_delivery_stop_time,page_id,page_name,spend,impressions,demographic_distribution,region_distribution",
        "limit": 100
    }

    try:
        response = requests.get(META_API_ENDPOINT, params=params, timeout=12)
        if response.status_code == 200:
            data = response.json().get("data", [])
            if not data:
                return generate_mock_meta_ads(n=max_records), False
            
            records = []
            for item in data:
                spend = item.get("spend", {})
                impressions = item.get("impressions", {})
                records.append({
                    "ad_id": str(item.get("id")),
                    "ad_url": f"https://www.facebook.com/ads/library/?id={item.get('id')}",
                    "ad_type": "IMAGE",
                    "regions": "NC",
                    "advertiser_id": str(item.get("page_id", "Unknown")),
                    "advertiser_name": item.get("page_name", "Unknown"),
                    "date_range_start": item.get("ad_delivery_start_time", "")[:10],
                    "date_range_end": (item.get("ad_delivery_stop_time") or "")[:10],
                    "impressions": f"{impressions.get('lower_bound', 0)}-{impressions.get('upper_bound', 1000)}",
                    "spend_range_min_usd": float(spend.get("lower_bound", 0)),
                    "spend_range_max_usd": float(spend.get("upper_bound", 0)) if spend.get("upper_bound") else None,
                    "nc_dma": "Raleigh-Durham-Fayetteville DMA",
                    "platform": "Meta"
                })
            df = pd.DataFrame(records)
            return df, True
        else:
            logger.warning(f"Meta API responded with HTTP {response.status_code}: {response.text[:200]}")
            return generate_mock_meta_ads(n=max_records), False
    except Exception as exc:
        logger.warning(f"Error querying Meta Ad Library API: {exc}")
        return generate_mock_meta_ads(n=max_records), False
