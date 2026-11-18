"""
Ad-library links, checked before they are shown.

- Google Ads Transparency Center links must answer HTTP 200.
- Meta: the snapshot stores ad_snapshot_url links (facebook.com/ads/archive/render_ad/?id=...), which need an API
  token and return 404 for people. The public Ad Library page (facebook.com/ads/library/?id=...) blocks automated
  checks (403), so each Meta ad is confirmed through the Meta Ad Library API (the advertiser's ads delivered that
  day must include it) and then the public link is shown.

A link that cannot be confirmed is not shown. Results are cached for a day; checks run in parallel.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests
import streamlit as st


def public_meta_url(ad_id: str) -> str:
    return f"https://www.facebook.com/ads/library/?id={ad_id}"


@st.cache_data(show_spinner=False, ttl=86_400, max_entries=2048)
def check_ad_link(platform: str, ad_id: str, url: str, page_id: str, start: str) -> tuple[str, str]:
    """(link to show, '' if it could not be confirmed; status note).

    Google: the transparency-center URL must answer HTTP 200. Meta: the stored snapshot URLs need an API token
    (they 404 for users) and the public library page blocks automated checks, so the ad is confirmed through the
    Meta Ad Library API (the advertiser's ads delivered that day must include it), then the public link is shown."""
    try:
        if platform == "Google":
            if not url:
                return "", "no link"
            r = requests.get(url, timeout=6, allow_redirects=True, stream=True,
                             headers={"User-Agent": "Mozilla/5.0 (campaign dashboard link check)"})
            r.close()
            return (url, "checked") if r.status_code == 200 else ("", f"link returned HTTP {r.status_code}")
        if platform == "Meta":
            from campaign_intel.config import META_AD_TOKEN

            if not META_AD_TOKEN or not page_id:
                return "", "not verified (no Meta API token)"
            params = {"access_token": META_AD_TOKEN, "ad_reached_countries": "['US']", "ad_active_status": "ALL",
                      "ad_type": "POLITICAL_AND_ISSUE_ADS", "search_page_ids": json.dumps([str(page_id)]),
                      "ad_delivery_date_min": start, "ad_delivery_date_max": start, "fields": "id", "limit": 500}
            nxt: str | None = "https://graph.facebook.com/v23.0/ads_archive"
            for _ in range(3):
                r = requests.get(nxt, params=params, timeout=10)
                if r.status_code != 200:
                    return "", f"not verified (Meta API HTTP {r.status_code})"
                j = r.json()
                if str(ad_id) in {x.get("id") for x in j.get("data", [])}:
                    return public_meta_url(ad_id), "verified in the Meta Ad Library"
                nxt, params = (j.get("paging") or {}).get("next"), None
                if not nxt:
                    break
            return "", "not found in the Meta Ad Library"
    except requests.RequestException as exc:
        return "", f"not verified ({type(exc).__name__})"
    return "", "no link"


def checked_links(ads: pd.DataFrame) -> dict[str, tuple[str, str]]:
    """ad_id -> (link or '', note), checked in parallel."""
    jobs = [(str(r.ad_id), r.platform, str(r.url or ""), str(r.advertiser_id or ""),
             f"{r.start:%Y-%m-%d}" if pd.notna(r.start) else "") for r in ads.itertuples()]
    with ThreadPoolExecutor(max_workers=6) as ex:
        res = list(ex.map(lambda j: check_ad_link(j[1], j[0], j[2], j[3], j[4]), jobs))
    return {j[0]: r for j, r in zip(jobs, res)}




def link_summary(links: dict[str, tuple[str, str]]) -> str:
    ok = sum(1 for u, _ in links.values() if u)
    return f"{ok} of {len(links)} ad links checked and working" + (
        f"; {len(links) - ok} hidden because they could not be confirmed." if ok < len(links) else ".")
