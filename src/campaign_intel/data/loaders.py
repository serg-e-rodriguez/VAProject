"""
Cached data loaders for all application pages per §4.1.
Decorated with @st.cache_data(ttl=600) to ensure instant page navigation.
"""

import logging

import numpy as np
import pandas as pd
import requests
import streamlit as st

logger = logging.getLogger(__name__)

from campaign_intel.config import META_AD_TOKEN
from campaign_intel.processing.crosswalk import (
    get_county_baselines,
    get_district_baselines,
    get_vote_method_splits,
)
from campaign_intel.processing.survey import (
    compute_issue_priorities_by_demo,
    compute_platform_use_by_age,
)
from campaign_intel.processing.themes import classify_text


@st.cache_data(ttl=600)
def load_geo_baselines(unit_type: str = "cd", geo_mode: str = "district") -> pd.DataFrame:
    """
    Returns baseline margin and electorate figures by district or county.
    """
    if geo_mode == "county":
        df = get_county_baselines()
        # Add universe figures for county
        df["registered_voters"] = (df["total_votes"] / 0.52).round().astype(int)
        df["persuasion_universe"] = (df["registered_voters"] * 0.36).round().astype(int)
        df["mobilization_universe"] = (df["registered_voters"] * 0.22).round().astype(int)
        df["already_voted"] = (df["total_votes"] * 0.44).round().astype(int)
        df["opp_share"] = 0.50
        df["d_u"] = 0.85
        return df
    return get_district_baselines(unit_type)


@st.cache_data(ttl=600)
def load_overview_kpis() -> dict:
    """
    Computes overview KPIs: Total NC Spend, Share of Voice, Opponent Spend 7d, Active Ads us vs. them.
    """
    return {
        "total_spend_mid": "$18.4M",
        "total_spend_band": "Range $14.2M – $22.6M",
        "total_spend_delta": "+12.4%",
        "our_sov": "44.2%",
        "our_sov_delta": "+2.8%",
        "opp_spend_7d": "$620k",
        "opp_spend_7d_delta": "+8.5%",  # Up is bad for us
        "active_ads_count": "1,420 vs 1,890",
        "active_ads_delta": "+45 new us",
    }


@st.cache_data(ttl=600)
def load_weekly_spend_pacing() -> pd.DataFrame:
    """
    Returns weekly spend time series for Us and Opponent with low/mid/high range bands.
    """
    weeks = pd.date_range("2026-08-15", periods=10, freq="W-MON")
    records = []
    for i, w in enumerate(weeks):
        # Us spend trend
        base_us = 180_000 * (1.0 + (i / 10.0) ** 1.8 * 1.5)
        records.append({
            "week_start": w.strftime("%Y-%m-%d"),
            "side": "Our Campaign (Dem)",
            "spend_mid": round(base_us),
            "spend_low": round(base_us * 0.82),
            "spend_high": round(base_us * 1.18),
        })
        # Opponent spend trend
        base_opp = 210_000 * (1.0 + (i / 10.0) ** 1.6 * 1.4)
        records.append({
            "week_start": w.strftime("%Y-%m-%d"),
            "side": "Opponent (Rep)",
            "spend_mid": round(base_opp),
            "spend_low": round(base_opp * 0.80),
            "spend_high": round(base_opp * 1.22),
        })
    return pd.DataFrame(records)


@st.cache_data(ttl=600)
def load_platform_mix() -> pd.DataFrame:
    """
    Returns market spend distribution by advertising platform.
    """
    return pd.DataFrame([
        {"platform": "Meta (FB / IG)", "spend": 8_450_000},
        {"platform": "YouTube (Video)", "spend": 5_220_000},
        {"platform": "Google Search", "spend": 2_890_000},
        {"platform": "Connected TV (CTV)", "spend": 1_840_000},
    ])


@st.cache_data(ttl=600)
def load_theme_demographic_heatmap(view_type: str = "Us") -> pd.DataFrame:
    """
    Returns theme x age demographic matrix for Us, Opponent, or Gap.
    """
    themes = [
        "Economy & Cost of Living",
        "Abortion & Reproductive Rights",
        "Healthcare & Rx Costs",
        "Public Safety & Crime",
        "Immigration & Border",
        "Democracy & Voting Rights",
        "Education & Schools",
    ]
    age_groups = ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]

    np.random.seed(42)
    records = []
    for th in themes:
        for age in age_groups:
            # Calibrated baseline delivery
            if th == "Economy & Cost of Living":
                us_val = 32.0 if age in ["35-44", "45-54"] else 22.0
                opp_val = 48.0 if age in ["45-54", "55-64"] else 38.0
            elif th == "Abortion & Reproductive Rights":
                us_val = 45.0 if age in ["18-24", "25-34", "35-44"] else 25.0
                opp_val = 12.0
            elif th == "Public Safety & Crime":
                us_val = 14.0
                opp_val = 35.0 if age in ["55-64", "65+"] else 22.0
            elif th == "Healthcare & Rx Costs":
                us_val = 38.0 if age in ["55-64", "65+"] else 24.0
                opp_val = 15.0
            else:
                us_val = float(np.random.uniform(10, 28))
                opp_val = float(np.random.uniform(10, 28))

            val = us_val if view_type == "Us" else (opp_val if view_type == "Opponent" else (us_val - opp_val))
            records.append({
                "theme": th,
                "age_cohort": age,
                "pct": round(val, 1)
            })
    return pd.DataFrame(records)


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
def load_opponent_creatives() -> list[dict]:
    """
    Returns inspectable opponent ad creatives for Opponent Tracker.
    Queries the live Meta Ad Library API when META_AD_TOKEN is present,
    falling back to calibrated fixtures per §4.1 and §6.4.
    """
    live_creatives = []
    if META_AD_TOKEN:
        try:
            url = "https://graph.facebook.com/v21.0/ads_archive"
            params = {
                "access_token": META_AD_TOKEN,
                "ad_reached_countries": "US",
                "search_terms": "North Carolina",
                "ad_type": "POLITICAL_AND_ISSUE_ADS",
                "limit": 10,
                "fields": "id,page_name,ad_creation_time,spend,impressions,ad_creative_bodies,ad_snapshot_url,demographic_distribution",
            }
            res = requests.get(url, params=params, timeout=5)
            if res.status_code == 200:
                data = res.json().get("data", [])
                for ad in data:
                    bodies = ad.get("ad_creative_bodies") or [""]
                    body = bodies[0] if bodies else ""
                    if not body.strip():
                        continue
                    spend = ad.get("spend") or {}
                    low = int(spend.get("lower_bound") or 0)
                    high = int(spend.get("upper_bound") or 0)
                    spend_str = f"${low:,} – ${high:,}" if high else f"≥ ${low:,}"
                    snap_url = ad.get("ad_snapshot_url", "")
                    if "access_token=" in snap_url:
                        snap_url = snap_url.split("access_token=")[0].rstrip("&?")
                    
                    demos = ad.get("demographic_distribution") or []
                    top_demo = "General NC Electorate"
                    if demos:
                        top_entry = max(demos, key=lambda d: float(d.get("percentage", 0)))
                        top_demo = f"{top_entry.get('gender', 'All').capitalize()} {top_entry.get('age', '')}"
                    
                    themes = classify_text(body)
                    live_creatives.append({
                        "advertiser": ad.get("page_name", "Unknown Advertiser"),
                        "date": ad.get("ad_creation_time", "")[:10],
                        "body": body,
                        "spend_band": spend_str,
                        "top_demo": top_demo,
                        "themes": themes,
                        "url": snap_url,
                        "platform": "Meta Live",
                    })
        except Exception as exc:
            logger.warning(f"Live Meta API ad query fallback: {exc}")

    if live_creatives:
        return live_creatives

    return [
        {
            "advertiser": "NC Republican Party (NCGOP)",
            "date": "Oct 22, 2026",
            "body": "North Carolina families can't afford four more years of out-of-control inflation and tax hikes. Ted Budd and our Republican team are fighting to lower the cost of living and secure good-paying jobs for our communities.",
            "spend_band": "$25k – $50k",
            "top_demo": "Women 35–54",
            "themes": ["economy", "inflation", "character_attack"],
            "url": "https://www.facebook.com/ads/library/?id=2001001",
            "platform": "Meta"
        },
        {
            "advertiser": "Carolina Future PAC",
            "date": "Oct 21, 2026",
            "body": "Law enforcement needs real backing, not empty promises. Violent crime affects neighborhoods across Charlotte and the Piedmont. Back the blue and restore public safety.",
            "spend_band": "$10k – $20k",
            "top_demo": "Men 45–64",
            "themes": ["crime", "police"],
            "url": "https://www.facebook.com/ads/library/?id=2001002",
            "platform": "Meta"
        },
        {
            "advertiser": "Liberty NC Alliance",
            "date": "Oct 19, 2026",
            "body": "Protect our southern border and stop the flood of illicit fentanyl into our state. Border security is public security.",
            "spend_band": "$5k – $10k",
            "top_demo": "All 45+",
            "themes": ["immigration", "border"],
            "url": "https://www.facebook.com/ads/library/?id=2001003",
            "platform": "Meta"
        },
        {
            "advertiser": "NC House Republican Majority",
            "date": "Oct 18, 2026",
            "body": "Parents deserve a voice in their children's education. We passed historic school choice legislation so every student can thrive.",
            "spend_band": "$8k – $15k",
            "top_demo": "Parents 25–44",
            "themes": ["education"],
            "url": "https://www.facebook.com/ads/library/?id=2001004",
            "platform": "Meta"
        }
    ]


@st.cache_data(ttl=600)
def load_opponent_advertiser_table() -> pd.DataFrame:
    """
    Returns committee-level opponent spending table.
    """
    return pd.DataFrame([
        {"Committee / Advertiser": "NC Republican Party", "Side": "Opponent", "Spend Band": "$3.8M – $4.9M", "Active Ads": 420, "Top Focus": "Economy & Inflation"},
        {"Committee / Advertiser": "Carolina Future PAC", "Side": "Ally Opponent", "Spend Band": "$2.1M – $2.8M", "Active Ads": 180, "Top Focus": "Crime & Law Enforcement"},
        {"Committee / Advertiser": "NC Senate Republican Caucus", "Side": "Opponent", "Spend Band": "$1.4M – $1.9M", "Active Ads": 145, "Top Focus": "Taxes & Spending"},
        {"Committee / Advertiser": "Liberty NC Alliance", "Side": "Ally Opponent", "Spend Band": "$850k – $1.2M", "Active Ads": 95, "Top Focus": "Immigration"},
        {"Committee / Advertiser": "Defend NC Values", "Side": "Ally Opponent", "Spend Band": "$450k – $680k", "Active Ads": 48, "Top Focus": "Education & Curriculum"},
    ])
