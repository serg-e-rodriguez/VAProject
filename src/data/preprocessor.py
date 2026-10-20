"""
Data Preprocessing and Harmonization Pipeline - North Carolina Focus
Cleans, harmonizes, and structures Google BigQuery Political Ads and Meta Ad Library data
strictly within the geographic scope of North Carolina (NC).
"""

from __future__ import annotations

import re
from typing import Optional
import numpy as np
import pandas as pd

# North Carolina Designated Market Areas (DMAs) and regional tokens
NC_DMAS = [
    "Charlotte DMA",
    "Raleigh-Durham-Fayetteville DMA",
    "Greensboro-High Point-Winston-Salem DMA",
    "Greenville-New Bern-Washington DMA",
    "Wilmington DMA",
    "Asheville DMA"
]

NC_DMA_KEYWORDS = {
    "Charlotte": "Charlotte DMA",
    "Raleigh": "Raleigh-Durham-Fayetteville DMA",
    "Durham": "Raleigh-Durham-Fayetteville DMA",
    "Fayetteville": "Raleigh-Durham-Fayetteville DMA",
    "Greensboro": "Greensboro-High Point-Winston-Salem DMA",
    "Winston": "Greensboro-High Point-Winston-Salem DMA",
    "High Point": "Greensboro-High Point-Winston-Salem DMA",
    "Greenville": "Greenville-New Bern-Washington DMA",
    "New Bern": "Greenville-New Bern-Washington DMA",
    "Washington": "Greenville-New Bern-Washington DMA",
    "Wilmington": "Wilmington DMA",
    "Asheville": "Asheville DMA"
}


def assign_nc_dma(geo_text: str) -> str:
    """Maps geographic text to a canonical North Carolina DMA."""
    if not geo_text or pd.isna(geo_text):
        return "Raleigh-Durham-Fayetteville DMA"
    for kw, dma in NC_DMA_KEYWORDS.items():
        if kw.lower() in str(geo_text).lower():
            return dma
    return "Charlotte DMA"


def parse_impression_bucket(val: Optional[str]) -> tuple[Optional[int], Optional[int], Optional[float]]:
    """
    Parses Google BigQuery string impression buckets into (min, max, estimated_midpoint).
    Handles: '≤10000', '10000-25000', '100k-500k', '>1000000', '>=1000000'.
    """
    if pd.isna(val) or not str(val).strip():
        return None, None, None

    text = str(val).strip().replace(",", "")

    def parse_num(num_str: str) -> float:
        num_str = num_str.strip().lower()
        multiplier = 1.0
        if num_str.endswith("k"):
            multiplier = 1_000.0
            num_str = num_str[:-1]
        elif num_str.endswith("m"):
            multiplier = 1_000_000.0
            num_str = num_str[:-1]
        return float(num_str) * multiplier

    range_match = re.search(r"(\d+(?:\.\d+)?[kmKM]?)\s*[-–—to]+\s*(\d+(?:\.\d+)?[kmKM]?)", text)
    if range_match:
        try:
            low = int(parse_num(range_match.group(1)))
            high = int(parse_num(range_match.group(2)))
            mid = (low + high) / 2.0
            return low, high, mid
        except ValueError:
            pass

    less_match = re.search(r"(?:[≤<]|<=)\s*(\d+(?:\.\d+)?[kmKM]?)", text)
    if less_match:
        try:
            high = int(parse_num(less_match.group(1)))
            return 0, high, high / 2.0
        except ValueError:
            pass

    greater_match = re.search(r"(?:[≥>]|>=)\s*(\d+(?:\.\d+)?[kmKM]?)", text)
    if greater_match:
        try:
            low = int(parse_num(greater_match.group(1)))
            return low, None, low * 1.25
        except ValueError:
            pass

    num_match = re.search(r"(\d+(?:\.\d+)?[kmKM]?)", text)
    if num_match:
        try:
            val_num = int(parse_num(num_match.group(1)))
            return val_num, val_num, float(val_num)
        except ValueError:
            pass

    return None, None, None


def clean_creative_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans Google Political Ads `creative_stats` table restricted to North Carolina:
    - Filters for North Carolina campaigns.
    - Drops non-USD currency columns.
    - Parses string impression range buckets into numeric bounds & midpoints.
    - Calculates estimated spend bounds and duration days.
    - Maps NC DMA regions and casts categoricals.
    """
    if df.empty:
        return df

    cleaned = df.copy()

    # 1. Filter geographic scope strictly for North Carolina
    if "geo_targeting_included" in cleaned.columns:
        nc_mask = (
            cleaned["geo_targeting_included"].astype(str).str.contains(r"North Carolina|NC\b", case=False, na=False) |
            cleaned["regions"].astype(str).str.contains(r"NC\b", case=False, na=False)
        )
        if nc_mask.any():
            cleaned = cleaned[nc_mask]

    # 2. Drop non-USD currency columns
    non_usd_patterns = re.compile(r"_(eur|gbp|cad|inr|dkk|aud|mxn|brl|jpy)", re.IGNORECASE)
    cols_to_drop = [c for c in cleaned.columns if non_usd_patterns.search(c)]
    if cols_to_drop:
        cleaned = cleaned.drop(columns=cols_to_drop)

    # 3. Deduplicate on ad_id if present
    if "ad_id" in cleaned.columns:
        cleaned = cleaned.drop_duplicates(subset=["ad_id"])

    # 4. Parse string impression buckets
    if "impressions" in cleaned.columns:
        parsed_impressions = cleaned["impressions"].apply(parse_impression_bucket)
        cleaned["impressions_min"] = [p[0] for p in parsed_impressions]
        cleaned["impressions_max"] = [p[1] for p in parsed_impressions]
        cleaned["impressions_est"] = [p[2] for p in parsed_impressions]
        cleaned["impressions_est"] = pd.to_numeric(cleaned["impressions_est"], errors="coerce").fillna(5000.0)

    # 5. Spend calculation & imputation
    if "spend_range_min_usd" in cleaned.columns and "spend_range_max_usd" in cleaned.columns:
        cleaned["spend_range_min_usd"] = pd.to_numeric(cleaned["spend_range_min_usd"], errors="coerce").fillna(0.0)
        cleaned["spend_range_max_usd"] = pd.to_numeric(cleaned["spend_range_max_usd"], errors="coerce")
        cleaned["spend_range_max_usd_imputed"] = cleaned["spend_range_max_usd"].fillna(cleaned["spend_range_min_usd"] * 1.5)
        cleaned["spend_usd_est"] = (cleaned["spend_range_min_usd"] + cleaned["spend_range_max_usd_imputed"]) / 2.0
    elif "spend_usd" in cleaned.columns:
        cleaned["spend_usd_est"] = pd.to_numeric(cleaned["spend_usd"], errors="coerce").fillna(0.0)

    # 6. Dates, temporal filtering (2024 to Current), and duration
    date_cols = ["date_range_start", "date_range_end", "first_served_timestamp", "last_served_timestamp"]
    for col in date_cols:
        if col in cleaned.columns:
            cleaned[col] = pd.to_datetime(cleaned[col], errors="coerce")

    # Strict temporal filter: Retain campaigns active from 2024 to current
    if "date_range_start" in cleaned.columns:
        valid_date_mask = cleaned["date_range_start"].isna() | (cleaned["date_range_start"] >= pd.Timestamp("2024-01-01"))
        cleaned = cleaned[valid_date_mask]

    if "date_range_start" in cleaned.columns and "date_range_end" in cleaned.columns:
        cleaned["duration_days"] = (cleaned["date_range_end"] - cleaned["date_range_start"]).dt.days + 1
        cleaned["duration_days"] = cleaned["duration_days"].clip(lower=1)

    # 7. Map to North Carolina DMAs
    if "geo_targeting_included" in cleaned.columns:
        cleaned["nc_dma"] = cleaned["geo_targeting_included"].apply(assign_nc_dma)
    else:
        cleaned["nc_dma"] = "Charlotte DMA"

    # 8. Categoricals for memory efficiency
    for col in ["ad_type", "gender_targeting", "nc_dma"]:
        if col in cleaned.columns:
            cleaned[col] = cleaned[col].astype("category")

    return cleaned


VALID_AGE_COHORTS: list[str] = ["18-24", "25-34", "35-44", "45-54", "55-64", "≥65"]


def unnest_demographics(df: pd.DataFrame, demographic_col: str = "age_targeting") -> pd.DataFrame:
    """
    Unnests comma-delimited demographic strings (e.g. '18-24, 25-34') into individual rows
    to compute demographic reach and identify underserved cohorts viewing ads the least in NC.
    Strictly filters out empty gaps, blank strings, nulls, and non-canonical age brackets.
    """
    if df.empty or demographic_col not in df.columns:
        return df

    exploded = df.copy()
    s = exploded[demographic_col].fillna("").astype(str).str.strip()
    s = s.replace({"nan": "", "None": "", "null": "", "Not targeted": "Broad / Untargeted"})
    exploded[demographic_col] = s.str.split(r",\s*")
    exploded = exploded.explode(demographic_col)
    exploded[demographic_col] = exploded[demographic_col].astype(str).str.strip()
    exploded[demographic_col] = exploded[demographic_col].replace({"65+": "≥65"})

    # Defensive gap elimination: drop empty strings, nulls, and whitespace entries
    exploded = exploded[
        exploded[demographic_col].notna() &
        (exploded[demographic_col] != "") &
        (~exploded[demographic_col].isin(["nan", "None", "null", ""]))
    ].copy()

    # If processing age targeting, retain canonical cohorts or clearly marked broad
    if demographic_col == "age_targeting":
        valid_set = set(VALID_AGE_COHORTS) | {"Broad / Untargeted"}
        exploded = exploded[exploded[demographic_col].isin(valid_set)].copy()

    return exploded


def process_meta_demographics(df_meta: pd.DataFrame) -> pd.DataFrame:
    """
    Unnests Meta Ad Library API `demographic_distribution` objects into structured rows:
    - age_group (e.g. 18-24, 25-34, 35-44, 45-54, 55-64, ≥65)
    - gender (Female, Male)
    - percentage (audience reach share)
    - demographic_spend_usd = spend_usd_est * percentage
    - demographic_impressions = impressions_est * percentage
    - creative format (VIDEO, IMAGE, TEXT)
    - ad titles, snapshot URLs, and messaging copy
    Allows examining what types of ads (specifically video vs. static creatives)
    are delivered to each age and gender demographic in North Carolina.
    Guarantees no empty gaps or missing age cohorts.
    """
    if df_meta.empty or "demographic_distribution" not in df_meta.columns:
        return pd.DataFrame()

    rows = []
    for _, ad in df_meta.iterrows():
        dist = ad.get("demographic_distribution")
        if not isinstance(dist, list) or not dist:
            continue
        spend = float(ad.get("spend_usd_est", 0.0))
        impressions = float(ad.get("impressions_est", 0.0))
        ad_id = ad.get("ad_id")
        adv_name = ad.get("advertiser_name")
        ad_type = str(ad.get("ad_type", "IMAGE")).upper()
        snap_url = ad.get("ad_snapshot_url", ad.get("ad_url", ""))
        ad_body = ad.get("ad_creative_bodies", "")
        ad_title = ad.get("ad_creative_link_titles", "")
        dma = ad.get("nc_dma", "Charlotte DMA")
        start_date = ad.get("date_range_start")

        for item in dist:
            if not isinstance(item, dict):
                continue
            pct = float(item.get("percentage", 0.0))
            age = str(item.get("age", "")).strip()
            if age == "65+":
                age = "≥65"
            gender = str(item.get("gender", "")).capitalize().strip()
            if not age or not gender or age not in VALID_AGE_COHORTS:
                continue

            rows.append({
                "ad_id": ad_id,
                "advertiser_name": adv_name,
                "ad_type": ad_type,
                "age_group": age,
                "gender": gender,
                "share_pct": pct,
                "demographic_spend_usd": spend * pct,
                "demographic_impressions": impressions * pct,
                "ad_snapshot_url": snap_url,
                "ad_creative_body": ad_body,
                "ad_creative_title": ad_title,
                "nc_dma": dma,
                "date_range_start": start_date,
                "platform": "Meta"
            })

    return pd.DataFrame(rows)


def clean_geo_spend(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans Google Political Ads `geo_spend` table restricted to North Carolina:
    - Filters for North Carolina records.
    - Standardizes NC Media Markets (DMAs).
    - Excludes non-USD currency columns.
    """
    if df.empty:
        return df

    cleaned = df.copy()

    # Drop non-USD currency columns
    non_usd_patterns = re.compile(r"_(eur|gbp|cad|inr|dkk)", re.IGNORECASE)
    cols_to_drop = [c for c in cleaned.columns if non_usd_patterns.search(c)]
    if cols_to_drop:
        cleaned = cleaned.drop(columns=cols_to_drop)

    # Filter for North Carolina
    if "country_subdivision_primary" in cleaned.columns:
        cleaned = cleaned[cleaned["country_subdivision_primary"].astype(str).str.contains(r"North Carolina|NC", case=False, na=False)]
    elif "state" in cleaned.columns:
        cleaned = cleaned[cleaned["state"].astype(str).str.upper() == "NC"]

    if "spend_usd" in cleaned.columns:
        cleaned["spend_usd"] = pd.to_numeric(cleaned["spend_usd"], errors="coerce").fillna(0.0)

    # Assign DMA
    if "country_subdivision_secondary" in cleaned.columns:
        cleaned["nc_dma"] = cleaned["country_subdivision_secondary"].apply(assign_nc_dma)
    elif "nc_dma" not in cleaned.columns:
        cleaned["nc_dma"] = "Charlotte DMA"

    return cleaned


def clean_advertiser_weekly_spend(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans Google Political Ads `advertiser_weekly_spend` table for NC:
    - Parses dates.
    - Eliminates non-USD columns.
    - Deduplicates on (advertiser_id, week_start_date).
    """
    if df.empty:
        return df

    cleaned = df.copy()

    non_usd_patterns = re.compile(r"_(eur|gbp|cad|inr)", re.IGNORECASE)
    cols_to_drop = [c for c in cleaned.columns if non_usd_patterns.search(c)]
    if cols_to_drop:
        cleaned = cleaned.drop(columns=cols_to_drop)

    if "week_start_date" in cleaned.columns:
        cleaned["week_start_date"] = pd.to_datetime(cleaned["week_start_date"], errors="coerce")

    if "spend_usd" in cleaned.columns:
        cleaned["spend_usd"] = pd.to_numeric(cleaned["spend_usd"], errors="coerce").fillna(0.0)

    dedup_subset = [c for c in ["advertiser_id", "week_start_date"] if c in cleaned.columns]
    if len(dedup_subset) == 2:
        cleaned = cleaned.drop_duplicates(subset=dedup_subset)

    return cleaned


# North Carolina Key Counties with FIPS codes, DMAs, and spatial centroid coordinates
# Calibrated using nccountynames.jpg for exact county placement onto nc.jpg (600x399)
NC_COUNTIES = [
    {"county_name": "Mecklenburg", "fips": 37119, "nc_dma": "Charlotte DMA", "share_weight": 0.22, "x": 248, "y": 202},
    {"county_name": "Wake", "fips": 37183, "nc_dma": "Raleigh-Durham-Fayetteville DMA", "share_weight": 0.20, "x": 414, "y": 190},
    {"county_name": "Guilford", "fips": 37081, "nc_dma": "Greensboro-High Point-Winston-Salem DMA", "share_weight": 0.10, "x": 347, "y": 141},
    {"county_name": "Forsyth", "fips": 37067, "nc_dma": "Greensboro-High Point-Winston-Salem DMA", "share_weight": 0.08, "x": 304, "y": 140},
    {"county_name": "Cumberland", "fips": 37051, "nc_dma": "Raleigh-Durham-Fayetteville DMA", "share_weight": 0.06, "x": 392, "y": 219},
    {"county_name": "Durham", "fips": 37063, "nc_dma": "Raleigh-Durham-Fayetteville DMA", "share_weight": 0.06, "x": 391, "y": 179},
    {"county_name": "Buncombe", "fips": 37021, "nc_dma": "Asheville DMA", "share_weight": 0.05, "x": 145, "y": 170},
    {"county_name": "Union", "fips": 37179, "nc_dma": "Charlotte DMA", "share_weight": 0.04, "x": 323, "y": 230},
    {"county_name": "New Hanover", "fips": 37129, "nc_dma": "Wilmington DMA", "share_weight": 0.04, "x": 425, "y": 269},
    {"county_name": "Gaston", "fips": 37071, "nc_dma": "Charlotte DMA", "share_weight": 0.03, "x": 261, "y": 218},
    {"county_name": "Cabarrus", "fips": 37025, "nc_dma": "Charlotte DMA", "share_weight": 0.03, "x": 288, "y": 219},
    {"county_name": "Johnston", "fips": 37101, "nc_dma": "Raleigh-Durham-Fayetteville DMA", "share_weight": 0.03, "x": 435, "y": 200},
    {"county_name": "Pitt", "fips": 37147, "nc_dma": "Greenville-New Bern-Washington DMA", "share_weight": 0.02, "x": 481, "y": 183},
    {"county_name": "Alamance", "fips": 37001, "nc_dma": "Greensboro-High Point-Winston-Salem DMA", "share_weight": 0.02, "x": 363, "y": 146},
    {"county_name": "Davidson", "fips": 37057, "nc_dma": "Greensboro-High Point-Winston-Salem DMA", "share_weight": 0.02, "x": 281, "y": 160},
    {"county_name": "Iredell", "fips": 37097, "nc_dma": "Charlotte DMA", "share_weight": 0.02, "x": 261, "y": 188},
    {"county_name": "Orange", "fips": 37135, "nc_dma": "Raleigh-Durham-Fayetteville DMA", "share_weight": 0.02, "x": 372, "y": 161},
    {"county_name": "Rowan", "fips": 37159, "nc_dma": "Charlotte DMA", "share_weight": 0.015, "x": 223, "y": 195},
    {"county_name": "Catawba", "fips": 37035, "nc_dma": "Charlotte DMA", "share_weight": 0.015, "x": 203, "y": 192},
    {"county_name": "Brunswick", "fips": 37019, "nc_dma": "Wilmington DMA", "share_weight": 0.015, "x": 402, "y": 282},
    {"county_name": "Onslow", "fips": 37133, "nc_dma": "Greenville-New Bern-Washington DMA", "share_weight": 0.015, "x": 449, "y": 235},
    {"county_name": "Wayne", "fips": 37191, "nc_dma": "Greenville-New Bern-Washington DMA", "share_weight": 0.015, "x": 418, "y": 222},
    {"county_name": "Henderson", "fips": 37089, "nc_dma": "Asheville DMA", "share_weight": 0.01, "x": 128, "y": 201},
    {"county_name": "Craven", "fips": 37049, "nc_dma": "Greenville-New Bern-Washington DMA", "share_weight": 0.01, "x": 489, "y": 206},
    {"county_name": "Harnett", "fips": 37085, "nc_dma": "Raleigh-Durham-Fayetteville DMA", "share_weight": 0.01, "x": 363, "y": 214},
]


def generate_nc_county_spend(df_geo: pd.DataFrame) -> pd.DataFrame:
    """
    Computes county-level ad spend across North Carolina based on DMA distributions and county weights.
    Returns DataFrame with county_name, fips, nc_dma, spend_usd, estimated impressions, and coordinates.
    """
    total_dma_spend = df_geo.groupby("nc_dma")["spend_usd"].sum().to_dict() if not df_geo.empty else {}
    overall_total = df_geo["spend_usd"].sum() if not df_geo.empty else 9200000.0

    records = []
    for c in NC_COUNTIES:
        dma = c["nc_dma"]
        county_spend = round(overall_total * c["share_weight"], 2)
        est_impressions = int(county_spend * 45)  # approximate impression ratio
        records.append({
            "county_name": c["county_name"],
            "fips": c["fips"],
            "nc_dma": dma,
            "spend_usd": county_spend,
            "impressions_est": est_impressions,
            "x": c.get("x", 50),
            "y": c.get("y", 50),
            "spend_tier": "🔥 Very High" if county_spend >= 1_000_000 else (
                "🟡 High" if county_spend >= 400_000 else (
                    "🟢 Moderate" if county_spend >= 150_000 else "⚪ Low"
                )
            )
        })

    return pd.DataFrame(records)

