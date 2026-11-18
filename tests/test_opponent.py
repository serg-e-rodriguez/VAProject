"""Opponent Tracker: only Republican-side ads are shown, and only links that were checked."""

from unittest import mock

import pytest

from campaign_intel.data import ad_links
from campaign_intel.data import loaders as L

needs_snapshot = pytest.mark.skipif(not L.snapshot_ready(), reason="snapshot not built")


def _cards(at):
    """Advertiser headings of the ad cards (bold line that names the Republican side)."""
    return [m.value for m in at.markdown if m.value.startswith("**") and "Republican\\:" in m.value]


@needs_snapshot
@pytest.mark.parametrize("race", ["house", "senate"])
def test_only_republican_ads_with_checked_links(race, monkeypatch):
    from streamlit.testing.v1 import AppTest

    calls = []

    def fake(platform, ad_id, url, page_id, start):
        calls.append(ad_id)
        return ("https://example.org/ok", "checked") if len(calls) % 2 else ("", "not found in the Meta Ad Library")

    monkeypatch.setattr(ad_links, "check_ad_link", fake)
    at = AppTest.from_file("../app_pages/opponent.py", default_timeout=180)
    at.session_state["race"], at.session_state["theme"] = race, "light"
    at.run()
    assert not at.exception
    cards = _cards(at)
    assert cards and len(calls) == len(cards)
    buttons = at.get("link_button")
    assert len(buttons) == (len(cards) + 1) // 2  # unconfirmed links are not shown
    assert all(btn.proto.url == "https://example.org/ok" for btn in buttons)
    assert not any("<a " in m.value for m in at.markdown)  # no raw-HTML links (the browser dropped those cards)
    assert not any("render_ad" in m.value for m in at.markdown)  # stored Meta snapshot links (404) never appear
    gop_ids = set(L.load_ads(race).query("side_group == 'GOP side'")["ad_id"])
    assert set(calls) <= gop_ids


def test_link_summary():
    assert ad_links.link_summary({"a": ("u", "ok"), "b": ("", "no")}) == (
        "1 of 2 ad links checked and working; 1 hidden because they could not be confirmed.")


def test_meta_snapshot_links_are_replaced_by_the_public_library_link(monkeypatch):
    import campaign_intel.config as cfg

    monkeypatch.setattr(cfg, "META_AD_TOKEN", "tok")
    resp = mock.Mock(status_code=200)
    resp.json.return_value = {"data": [{"id": "987"}]}
    with mock.patch.object(ad_links.requests, "get", return_value=resp):
        url, _ = ad_links.check_ad_link.__wrapped__("Meta", "987", "https://www.facebook.com/ads/archive/render_ad/?id=987",
                                                    "p", "2026-09-01")
    assert url == "https://www.facebook.com/ads/library/?id=987"
