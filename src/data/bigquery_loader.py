"""
BigQuery Data Loader - North Carolina Focus
Fetches political advertising data from Google Cloud BigQuery public dataset
restricted strictly to the geographic scope of North Carolina (NC).
"""

from __future__ import annotations

import logging
from typing import Optional
import numpy as np
import pandas as pd
import streamlit as st

try:
    from src.config import GCP_PROJECT_ID, BIGQUERY_POLITICAL_ADS_DATASET
except ModuleNotFoundError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from config import GCP_PROJECT_ID, BIGQUERY_POLITICAL_ADS_DATASET

logger = logging.getLogger(__name__)

NC_ADVERTISERS = [
    ("ADV_NC01", "Carolina Forward PAC"),
    ("ADV_NC02", "NC Values Coalition Action Fund"),
    ("ADV_NC03", "Citizens for Clean Energy NC"),
    ("ADV_NC04", "Tar Heel Voter Project"),
    ("ADV_NC05", "Defend North Carolina Leadership Fund"),
    ("ADV_NC06", "Working Families for North Carolina"),
    ("ADV_NC07", "Piedmont Prosperity Alliance"),
    ("ADV_NC08", "Coastal Carolina Action PAC"),
]

NC_MARKET_LOCATIONS = [
    ("Charlotte DMA", "Charlotte, North Carolina, United States"),
    ("Raleigh-Durham-Fayetteville DMA", "Raleigh-Durham, North Carolina, United States"),
    ("Greensboro-High Point-Winston-Salem DMA", "Greensboro, North Carolina, United States"),
    ("Greenville-New Bern-Washington DMA", "Greenville, North Carolina, United States"),
    ("Wilmington DMA", "Wilmington, North Carolina, United States"),
    ("Asheville DMA", "Asheville, North Carolina, United States"),
]
NC_MARKET_PROBS = [0.32, 0.28, 0.18, 0.10, 0.07, 0.05]


def generate_mock_creative_stats(n: int = 1200) -> pd.DataFrame:
    """Generates realistic synthetic Google Political Ads creative_stats data for North Carolina."""
    np.random.seed(42)
    
    ad_types = ["VIDEO", "IMAGE", "TEXT"]
    ad_type_probs = [0.55, 0.35, 0.10]
    
    age_cohorts = [
        "18-24", "25-34", "35-44", "45-54", "55-64", "≥65",
        "18-24, 25-34", "25-34, 35-44", "35-44, 45-54", "45-54, 55-64", "55-64, ≥65",
        "Not targeted"
    ]
    age_probs = [0.05, 0.11, 0.17, 0.22, 0.24, 0.15, 0.03, 0.015, 0.01, 0.003, 0.001, 0.001]
    
    gender_options = ["Female, Male", "Female", "Male", "Not targeted"]
    gender_probs = [0.65, 0.18, 0.14, 0.03]

    impression_buckets = [
        "≤10000", "10000-25000", "25000-50000", "50000-100000",
        "100000-500000", "500000-1000000", ">1000000"
    ]
    bucket_probs = [0.30, 0.25, 0.20, 0.12, 0.08, 0.03, 0.02]

    records = []
    base_date = pd.Timestamp("2024-01-01")

    for i in range(n):
        adv_id, adv_name = NC_ADVERTISERS[np.random.choice(len(NC_ADVERTISERS))]
        ad_type = np.random.choice(ad_types, p=ad_type_probs)
        start_offset = int(np.random.exponential(scale=90)) % 300
        start_date = base_date + pd.Timedelta(days=start_offset)
        duration = int(np.random.gamma(shape=2, scale=7)) + 1
        end_date = start_date + pd.Timedelta(days=duration)
        
        bucket = np.random.choice(impression_buckets, p=bucket_probs)
        
        min_spend = float(np.random.choice([150, 350, 750, 1500, 3000, 7500, 15000, 30000]))
        max_spend = min_spend * float(np.random.choice([1.5, 2.0, 3.0])) if np.random.rand() > 0.12 else None

        market_idx = np.random.choice(len(NC_MARKET_LOCATIONS), p=NC_MARKET_PROBS)
        dma_name, geo_str = NC_MARKET_LOCATIONS[market_idx]

        records.append({
            "ad_id": f"CR-NC-{i+10000:05d}",
            "ad_url": f"https://adstransparency.google.com/political?ad_id=CR-NC-{i+10000:05d}",
            "ad_type": ad_type,
            "regions": "NC",
            "advertiser_id": adv_id,
            "advertiser_name": adv_name,
            "date_range_start": start_date.strftime("%Y-%m-%d"),
            "date_range_end": end_date.strftime("%Y-%m-%d"),
            "num_of_days": duration,
            "impressions": bucket,
            "spend_range_min_usd": min_spend,
            "spend_range_max_usd": max_spend,
            "spend_range_min_eur": min_spend * 0.92,
            "spend_range_max_eur": max_spend * 0.92 if max_spend else None,
            "age_targeting": np.random.choice(age_cohorts, p=age_probs),
            "gender_targeting": np.random.choice(gender_options, p=gender_probs),
            "geo_targeting_included": geo_str,
            "geo_targeting_excluded": "None",
            "nc_dma": dma_name,
            "platform": "Google"
        })

    return pd.DataFrame(records)


def generate_mock_geo_spend() -> pd.DataFrame:
    """Generates synthetic regional spend distribution across North Carolina DMAs."""
    nc_dma_totals = [
        ("Charlotte DMA", 2850000.0),
        ("Raleigh-Durham-Fayetteville DMA", 2620000.0),
        ("Greensboro-High Point-Winston-Salem DMA", 1740000.0),
        ("Greenville-New Bern-Washington DMA", 890000.0),
        ("Wilmington DMA", 620000.0),
        ("Asheville DMA", 480000.0),
    ]

    records = []
    for dma_name, base_total in nc_dma_totals:
        for adv_id, adv_name in NC_ADVERTISERS[:6]:
            share = np.random.uniform(0.10, 0.35)
            spend = round(base_total * share, 2)
            records.append({
                "advertiser_id": adv_id,
                "advertiser_name": adv_name,
                "country": "US",
                "country_subdivision_primary": "North Carolina",
                "state": "NC",
                "nc_dma": dma_name,
                "spend_usd": spend,
                "spend_eur": round(spend * 0.92, 2)
            })
    return pd.DataFrame(records)


def generate_mock_weekly_spend() -> pd.DataFrame:
    """Generates synthetic weekly spend pacing for North Carolina campaigns."""
    weeks = pd.date_range("2024-03-01", "2024-11-05", freq="W-MON")
    records = []
    for i, w in enumerate(weeks):
        multiplier = 1.0 + (i / len(weeks)) ** 2 * 3.8
        for adv_id, adv_name in NC_ADVERTISERS[:5]:
            spend = float(np.random.normal(loc=18000, scale=3000) * multiplier)
            records.append({
                "advertiser_id": adv_id,
                "advertiser_name": adv_name,
                "election_cycle": "NC 2024",
                "week_start_date": w.strftime("%Y-%m-%d"),
                "spend_usd": round(max(spend, 800.0), 2),
                "spend_eur": round(max(spend, 800.0) * 0.92, 2)
            })
    return pd.DataFrame(records)


@st.cache_data(ttl=3600, show_spinner=False)
def load_bigquery_creative_stats(limit: int = 5000) -> tuple[pd.DataFrame, bool]:
    """Loads creative_stats for North Carolina from BigQuery or mock dataset."""
    try:
        from google.cloud import bigquery
        client = bigquery.Client(project=GCP_PROJECT_ID)
        query = f"""
        SELECT 
            ad_id, ad_url, ad_type, regions, advertiser_id, advertiser_name,
            date_range_start, date_range_end, num_of_days, impressions,
            spend_range_min_usd, spend_range_max_usd, age_targeting,
            gender_targeting, geo_targeting_included
        FROM `{BIGQUERY_POLITICAL_ADS_DATASET}.creative_stats`
        WHERE regions = 'US' AND REGEXP_CONTAINS(geo_targeting_included, r'North Carolina|NC')
        LIMIT {limit}
        """
        df = client.query(query).to_dataframe()
        df["platform"] = "Google"
        return df, True
    except Exception as exc:
        logger.info(f"BigQuery live query unavailable ({exc}); loading mock NC dataset.")
        return generate_mock_creative_stats(n=limit), False


@st.cache_data(ttl=3600, show_spinner=False)
def load_bigquery_geo_spend() -> tuple[pd.DataFrame, bool]:
    """Loads North Carolina regional spend from BigQuery or mock dataset."""
    try:
        from google.cloud import bigquery
        client = bigquery.Client(project=GCP_PROJECT_ID)
        query = f"""
        SELECT 
            advertiser_id, advertiser_name, country, country_subdivision_primary, spend_usd
        FROM `{BIGQUERY_POLITICAL_ADS_DATASET}.geo_spend`
        WHERE country_subdivision_primary = 'North Carolina'
        """
        df = client.query(query).to_dataframe()
        return df, True
    except Exception:
        return generate_mock_geo_spend(), False


@st.cache_data(ttl=3600, show_spinner=False)
def load_bigquery_weekly_spend() -> tuple[pd.DataFrame, bool]:
    """Loads NC weekly spend pacing from BigQuery or mock dataset."""
    try:
        from google.cloud import bigquery
        client = bigquery.Client(project=GCP_PROJECT_ID)
        query = f"""
        SELECT 
            advertiser_id, advertiser_name, election_cycle, week_start_date, spend_usd
        FROM `{BIGQUERY_POLITICAL_ADS_DATASET}.advertiser_weekly_spend`
        WHERE spend_usd IS NOT NULL
        """
        df = client.query(query).to_dataframe()
        return df, True
    except Exception:
        return generate_mock_weekly_spend(), False
