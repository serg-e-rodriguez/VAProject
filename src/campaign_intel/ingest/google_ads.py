"""
Google Political Ads (BigQuery public dataset) extraction for the NC snapshot.

Data-quality rules applied (PROJECT_DESIGN.md §6.4):
- `advertiser_geo_spend` is LIFETIME (since 2018) and has no dates; it is only used to find
  NC-focused advertisers, never shown as a cycle total.
- `advertiser_weekly_spend` is national, so the weekly NC series uses only advertisers with
  >= NC_FOCUS_MIN of their lifetime US spend in NC.
- Creatives targeting several states are apportioned 1/n_states to NC (validated against
  Google's own NC totals: correlation 0.25 -> 0.73 vs. counting them in full).
- Spend / impression ranges keep low, high and mid; open-ended top tiers are flagged.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from campaign_intel.config import GCP_PROJECT_ID

logger = logging.getLogger(__name__)

ADS = "bigquery-public-data.google_political_ads"
CYCLE_START = "2025-07-01"
NC_FOCUS_MIN = 0.9


def _client():
    from google.cloud import bigquery

    return bigquery.Client(project=GCP_PROJECT_ID)


def _query(client, sql: str) -> pd.DataFrame:
    job = client.query(sql)
    df = job.to_dataframe(create_bqstorage_client=False)
    logger.info("BigQuery: %d rows, %.2f GB scanned", len(df), (job.total_bytes_processed or 0) / 1e9)
    return df


def _tokens(col: str) -> str:
    return f"SPLIT(REPLACE(IFNULL({col}, ''), 'United States,', 'United States|'), '|')"


def creatives_sql(start: str) -> str:
    inc = _tokens("geo_targeting_included")
    return f"""
    SELECT ad_id, ad_url, ad_type, advertiser_id, advertiser_name,
           date_range_start, date_range_end, num_of_days, impressions,
           spend_range_min_usd, spend_range_max_usd, age_targeting, gender_targeting,
           ARRAY_TO_STRING(ARRAY(SELECT TRIM(t) FROM UNNEST({inc}) t
                WHERE ENDS_WITH(TRIM(t), 'North Carolina,United States')), '|') AS nc_targets,
           (SELECT COUNT(DISTINCT REGEXP_EXTRACT(TRIM(t), r'([^,]+),United States$'))
              FROM UNNEST({inc}) t WHERE TRIM(t) != 'United States') AS n_states,
           (SELECT COUNTIF(TRIM(t) = 'United States') FROM UNNEST({inc}) t) > 0 AS targets_whole_us
    FROM `{ADS}.creative_stats`
    WHERE regions = 'US' AND date_range_start >= '{start}'
      AND geo_targeting_included LIKE '%North Carolina%'
    """


def _parse_impressions(s: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Google buckets look like '10000-100000' or '≥10000000' / '10000000+'."""
    s = s.fillna("").astype(str).str.replace(",", "").str.replace("≤", "0-")
    lo = pd.to_numeric(s.str.extract(r"(\d+)")[0], errors="coerce")
    hi = pd.to_numeric(s.str.extract(r"\d+\s*-\s*(\d+)")[0], errors="coerce")
    return lo.fillna(0.0), hi


def extract(start: str = CYCLE_START) -> dict[str, pd.DataFrame]:
    client = _client()
    out: dict[str, pd.DataFrame] = {}

    cr = _query(client, creatives_sql(start))
    cr["spend_low"] = cr["spend_range_min_usd"].astype(float)
    hi = cr["spend_range_max_usd"].astype(float)
    cr["open_ended"] = hi.isna()
    cr["spend_high"] = hi.fillna(cr["spend_low"] * 2.0)
    cr["spend_mid"] = np.where(cr["open_ended"], cr["spend_low"] * 1.5, (cr["spend_low"] + cr["spend_high"]) / 2)
    imp_lo, imp_hi = _parse_impressions(cr["impressions"])
    cr["impressions_low"] = imp_lo
    cr["impressions_high"] = imp_hi.fillna(imp_lo * 2.0)
    cr["impressions_mid"] = (cr["impressions_low"] + cr["impressions_high"]) / 2
    # NC apportionment
    n_states = cr["n_states"].fillna(1).clip(lower=1)
    cr["nc_share"] = np.where(cr["targets_whole_us"], 0.0, 1.0 / n_states)
    cr["nc_only"] = (n_states == 1) & ~cr["targets_whole_us"]
    for c in ["spend_low", "spend_mid", "spend_high", "impressions_low", "impressions_mid", "impressions_high"]:
        cr[f"nc_{c}"] = cr[c] * cr["nc_share"]
    cr["date_range_start"] = pd.to_datetime(cr["date_range_start"])
    cr["date_range_end"] = pd.to_datetime(cr["date_range_end"])
    keep = ["ad_id", "ad_url", "ad_type", "advertiser_id", "advertiser_name", "date_range_start",
            "date_range_end", "num_of_days", "age_targeting", "gender_targeting", "nc_targets", "n_states",
            "targets_whole_us", "nc_only", "nc_share", "open_ended",
            "spend_low", "spend_mid", "spend_high", "impressions_low", "impressions_mid", "impressions_high",
            "nc_spend_low", "nc_spend_mid", "nc_spend_high",
            "nc_impressions_low", "nc_impressions_mid", "nc_impressions_high"]
    out["google_creatives"] = cr[keep]

    # Lifetime NC vs US spend per advertiser -> NC-focused advertisers
    geo = _query(client, f"""
        WITH nc AS (SELECT advertiser_id, ANY_VALUE(advertiser_name) AS advertiser_name, SUM(spend_usd) AS nc_spend
                    FROM `{ADS}.advertiser_geo_spend`
                    WHERE country = 'US' AND country_subdivision_primary = 'NC' GROUP BY advertiser_id),
             us AS (SELECT advertiser_id, SUM(spend_usd) AS us_spend
                    FROM `{ADS}.advertiser_geo_spend` WHERE country = 'US' GROUP BY advertiser_id)
        SELECT nc.*, us.us_spend, SAFE_DIVIDE(nc.nc_spend, us.us_spend) AS nc_share_lifetime
        FROM nc JOIN us USING (advertiser_id) WHERE nc.nc_spend > 0""")
    out["google_advertiser_nc_lifetime"] = geo

    focused = geo[geo["nc_share_lifetime"] >= NC_FOCUS_MIN]["advertiser_id"].tolist()
    ids = ",".join(f"'{i}'" for i in focused) or "''"
    wk = _query(client, f"""
        SELECT advertiser_id, advertiser_name, week_start_date, spend_usd
        FROM `{ADS}.advertiser_weekly_spend`
        WHERE week_start_date >= '{start}' AND advertiser_id IN ({ids}) AND spend_usd > 0""")
    wk["week_start_date"] = pd.to_datetime(wk["week_start_date"])
    out["google_weekly_nc_focused"] = wk

    out["google_cd_spend"] = _query(client, f"""
        SELECT country_subdivision_secondary AS district_label, spend_usd
        FROM `{ADS}.geo_spend` WHERE country = 'US' AND country_subdivision_primary = 'US-NC'""")
    out["google_last_updated"] = _query(client, f"SELECT report_data_updated_time FROM `{ADS}.last_updated`")
    return out
