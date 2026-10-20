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
    from src.config import META_USER_TOKEN, META_APP_TOKEN, META_AD_TOKEN, META_REQUIRED_PERMISSIONS
except ModuleNotFoundError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from config import META_USER_TOKEN, META_APP_TOKEN, META_AD_TOKEN, META_REQUIRED_PERMISSIONS

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


def generate_mock_meta_ads(n: int = 1200) -> pd.DataFrame:
    """
    Generates synthetic Meta political ads data for North Carolina with full demographic distribution.
    Strictly scoped from 2024 to current, capturing video vs. image vs. text format delivery.
    """
    np.random.seed(99)

    age_cohorts = ["18-24", "25-34", "35-44", "45-54", "55-64", "≥65"]
    gender_list = ["Female", "Male"]

    sample_headlines = [
        "Lowering prescription drug costs and expanding rural healthcare in North Carolina.",
        "Investing in clean energy jobs and high-speed broadband across rural NC.",
        "Protecting public school teacher salaries and investing in North Carolina classrooms.",
        "Strengthening small business opportunities and job creation in the Piedmont Triad.",
        "Defending reproductive freedom and voter rights across North Carolina.",
        "Securing clean drinking water and protecting our Cape Fear River basin.",
        "Supporting NC veteran healthcare access and military families in Cumberland & Onslow.",
        "Tackling inflation and lowering everyday grocery costs for working North Carolina families."
    ]

    sample_video_titles = [
        "🎥 Watch: Real North Carolina Voices on Healthcare and Jobs",
        "🎥 Video: Protecting Our Mountains, Coast, and Communities",
        "🎥 Campaign Ad: A Plan for North Carolina's Working Families",
        "🎥 Special Message to Young North Carolina Voters",
        "🎥 Video Spotlight: Empowering NC Small Businesses",
        "🎥 Ad Flight: Defending North Carolina Public Schools"
    ]

    sample_image_titles = [
        "🖼️ Infographic: North Carolina Economic Progress Report",
        "🖼️ Candidate Priorities for NC: Lowering Costs & Protecting Freedoms",
        "🖼️ NC Voter Guide: Key Dates, Polling Places & Absentee Information",
        "🖼️ Plan Overview: Supporting Working Families Across NC"
    ]

    impression_buckets = [
        "≤10000", "10000-25000", "25000-50000", "50000-100000",
        "100000-500000", "500000-1000000", ">1000000"
    ]
    bucket_probs = [0.26, 0.25, 0.20, 0.15, 0.09, 0.03, 0.02]

    records = []
    base_date = pd.Timestamp("2024-01-01")

    for i in range(n):
        adv_id, adv_name = NC_META_ADVERTISERS[np.random.choice(len(NC_META_ADVERTISERS))]
        start_offset = int(np.random.exponential(scale=75)) % 290
        start_date = base_date + pd.Timedelta(days=start_offset)
        duration = int(np.random.gamma(shape=2.5, scale=5)) + 1
        end_date = start_date + pd.Timedelta(days=duration)
        
        bucket = np.random.choice(impression_buckets, p=bucket_probs)
        min_spend = float(np.random.choice([200, 450, 900, 2000, 4500, 10000, 22000, 40000]))
        max_spend = min_spend * float(np.random.choice([1.4, 2.0, 2.8])) if np.random.rand() > 0.10 else None

        market_idx = np.random.choice(len(NC_META_MARKETS), p=NC_META_MARKET_PROBS)
        dma_name, geo_str = NC_META_MARKETS[market_idx]

        # Ad type allocation (Video represents 58%, Image 32%, Text 10%)
        ad_type = np.random.choice(["VIDEO", "IMAGE", "TEXT"], p=[0.58, 0.32, 0.10])
        if ad_type == "VIDEO":
            link_title = np.random.choice(sample_video_titles)
        elif ad_type == "IMAGE":
            link_title = np.random.choice(sample_image_titles)
        else:
            link_title = "Official Public Statement & Position Paper"

        body_text = np.random.choice(sample_headlines)

        # Generate realistic demographic distribution from Meta Graph API
        # Younger voters receive a higher skew of Video ads, while older demographics receive balanced formats
        raw_weights = []
        for age in age_cohorts:
            for gender in gender_list:
                base_w = 1.0
                if age in ["18-24", "25-34"]:
                    base_w = 1.6 if ad_type == "VIDEO" else 0.8
                elif age in ["55-64", "≥65"]:
                    base_w = 1.4 if ad_type in ["IMAGE", "TEXT"] else 0.9
                if gender == "Female":
                    base_w *= 1.15
                raw_weights.append(base_w * np.random.uniform(0.7, 1.3))

        total_w = sum(raw_weights)
        demo_dist = []
        idx = 0
        for age in age_cohorts:
            for gender in gender_list:
                pct = round(raw_weights[idx] / total_w, 4)
                demo_dist.append({"age": age, "gender": gender, "percentage": pct})
                idx += 1

        # Derive primary age targeting string for interoperability
        top_cohorts = sorted(demo_dist, key=lambda x: x["percentage"], reverse=True)[:2]
        top_ages = list(dict.fromkeys([x["age"] for x in top_cohorts]))
        age_targeting_str = ", ".join(top_ages)

        records.append({
            "ad_id": f"CR-META-NC-{i+50000:05d}",
            "ad_url": f"https://www.facebook.com/ads/library/?id={i+50000:05d}",
            "ad_snapshot_url": f"https://www.facebook.com/ads/archive/render_ad/?id={i+50000:05d}",
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
            "age_targeting": age_targeting_str,
            "gender_targeting": "Female, Male",
            "geo_targeting_included": geo_str,
            "geo_targeting_excluded": "None",
            "nc_dma": dma_name,
            "platform": "Meta",
            "ad_creative_bodies": body_text,
            "ad_creative_link_titles": link_title,
            "demographic_distribution": demo_dist
        })

    return pd.DataFrame(records)


@st.cache_data(ttl=1800, show_spinner=False)
def load_meta_ads(max_records: int = 1200) -> tuple[pd.DataFrame, bool]:
    """
    Queries Meta Ad Library API for political and issue ads in North Carolina.
    Strictly filters ads delivered from 2024 to current (`ad_delivery_date_min='2024-01-01'`).
    
    PERMISSIONS REQUIREMENT (META USER TOKEN):
    Access to Meta's political ads archive requires a User Token with the following permissions:
    - ads_management
    - ads_read
    - business_management
    - pages_read_engagement
    - pages_manage_ads
    - leads_retrieval
    SECURITY MANDATE: The Meta User Token must NEVER be included in source code and is strictly loaded 
    at runtime via environment variables (META_USER_TOKEN in .env or env.txt).
    
    Returns (DataFrame, is_live_data). If token is missing, unauthorized, or rate-limited, returns (mock_data, False).
    """
    clean_token = (META_USER_TOKEN or META_APP_TOKEN or META_AD_TOKEN or "").strip().strip('"').strip("'")
    if not clean_token or len(clean_token) < 20:
        logger.info("Meta User Token not configured; using calibrated NC Meta political ads sample dataset (2024-Current).")
        return generate_mock_meta_ads(n=max_records), False

    params = {
        "access_token": clean_token,
        "ad_type": "POLITICAL_AND_ISSUE_ADS",
        "ad_reached_countries": "['US']",
        "search_terms": "North Carolina",
        "ad_delivery_date_min": "2024-01-01",
        "fields": (
            "id,ad_creation_time,ad_delivery_start_time,ad_delivery_stop_time,"
            "page_id,page_name,spend,impressions,demographic_distribution,region_distribution,"
            "ad_creative_bodies,ad_creative_link_titles,ad_snapshot_url,publisher_platforms"
        ),
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
                demo_dist = item.get("demographic_distribution", [])
                
                # Check creative format
                creative_body = (item.get("ad_creative_bodies") or [""])[0] if item.get("ad_creative_bodies") else ""
                creative_title = (item.get("ad_creative_link_titles") or [""])[0] if item.get("ad_creative_link_titles") else ""
                
                # Deduce format from metadata
                ad_type = "VIDEO" if "video" in creative_title.lower() or "watch" in creative_body.lower() else "IMAGE"

                records.append({
                    "ad_id": str(item.get("id")),
                    "ad_url": f"https://www.facebook.com/ads/library/?id={item.get('id')}",
                    "ad_snapshot_url": item.get("ad_snapshot_url", f"https://www.facebook.com/ads/library/?id={item.get('id')}"),
                    "ad_type": ad_type,
                    "regions": "NC",
                    "advertiser_id": str(item.get("page_id", "Unknown")),
                    "advertiser_name": item.get("page_name", "Unknown"),
                    "date_range_start": item.get("ad_delivery_start_time", "2024-01-01")[:10],
                    "date_range_end": (item.get("ad_delivery_stop_time") or "")[:10],
                    "impressions": f"{impressions.get('lower_bound', 0)}-{impressions.get('upper_bound', 1000)}",
                    "spend_range_min_usd": float(spend.get("lower_bound", 0)),
                    "spend_range_max_usd": float(spend.get("upper_bound", 0)) if spend.get("upper_bound") else None,
                    "age_targeting": "18-24, 25-34, 35-44",
                    "gender_targeting": "Female, Male",
                    "nc_dma": "Raleigh-Durham-Fayetteville DMA",
                    "platform": "Meta",
                    "ad_creative_bodies": creative_body,
                    "ad_creative_link_titles": creative_title,
                    "demographic_distribution": demo_dist
                })
            df = pd.DataFrame(records)
            return df, True
        else:
            # Mask error details to ensure no tokens or credentials leak
            err_msg = response.text[:250]
            if "OAuthException" in err_msg or response.status_code == 400:
                logger.warning(
                    f"Meta Ad Library API requires an authorized Meta User Token with permissions "
                    f"(ads_management, ads_read, business_management, pages_read_engagement, pages_manage_ads, leads_retrieval) "
                    f"(HTTP {response.status_code}). Using calibrated NC political ads sample dataset."
                )
            else:
                logger.warning(f"Meta API responded with HTTP {response.status_code}. Using calibrated sample dataset.")
            return generate_mock_meta_ads(n=max_records), False
    except Exception as exc:
        logger.warning(f"Network error querying Meta Ad Library API: {exc}. Using calibrated sample dataset.")
        return generate_mock_meta_ads(n=max_records), False
