"""
Top bar (UI_Design.md §4.2): page title, race scope, geography, district type, alerts,
data-freshness chip and theme switch. All state lives in st.session_state + query params.
"""

from __future__ import annotations

import html

import streamlit as st

from campaign_intel.config import SCOPE_LABELS
from campaign_intel.data.loaders import load_alerts, load_manifest, snapshot_ready
from campaign_intel.state import set_state, toggle_theme

UTYPE_LABELS = {"cd": "Congressional (14)", "sd": "State Senate (50)", "hd": "State House (120)"}


def _freshness_chip() -> str:
    m = load_manifest()
    if not m:
        return "<span class='fresh-chip stale'>No snapshot</span>"
    built = m.get("built_at", "")[:16].replace("T", " ")
    tip = html.escape(
        f"Snapshot built {built} UTC · Google report updated {m.get('google_report_updated', '?')[:16]} · "
        f"Meta ads through {m.get('meta_latest_ad_start', '?')} · NCSBE 2026 results file "
        f"{m.get('statewide', {}).get('sen26_file_date', '?')}")
    return f"<span class='fresh-chip' title='{tip}'>Snapshot · {built[:10]}</span>"


def render_topbar(page_title: str) -> None:
    theme = st.session_state.get("theme", "dark")
    scope = st.session_state.get("scope", "statewide")
    geo_mode = st.session_state.get("geo_mode", "district")
    unit_type = st.session_state.get("unit_type", "cd")

    if not snapshot_ready():
        st.error("No data snapshot found. Build it once with: `uv run python -m campaign_intel.ingest.build_snapshot`")
        st.stop()

    with st.container(border=True):
        r1_title, r1_chip, r1_alerts, r1_theme = st.columns([7.4, 1.6, 0.8, 0.6], vertical_alignment="center", gap="small")
        with r1_title:
            st.markdown(f"<h3 class='topbar-title' title='{html.escape(page_title)}'>{html.escape(page_title)}</h3>",
                        unsafe_allow_html=True)
        c_scope, c_geo, c_type, _ = st.columns([2.2, 1.7, 2.2, 3.9], vertical_alignment="center", gap="small")
        c_alerts, c_chip, c_theme = r1_alerts, r1_chip, r1_theme
        with c_scope:
            opts = list(SCOPE_LABELS)
            new = st.selectbox("Race scope", opts, index=opts.index(scope) if scope in opts else 0,
                               format_func=SCOPE_LABELS.get, label_visibility="collapsed", key="tb_scope",
                               help="Statewide = US Senate race. District = one district's race. "
                                    "Chamber = majority of the selected district type.")
            if new != scope:
                set_state(scope=new)
                if new == "chamber" and geo_mode == "county":
                    set_state(geo_mode="district")
                st.rerun()
        with c_geo:
            new_geo = st.segmented_control("Geography", ["District", "County"],
                                           default="County" if geo_mode == "county" else "District",
                                           label_visibility="collapsed", key="tb_geo")
            parsed = (new_geo or "District").lower()
            if parsed != geo_mode:
                set_state(geo_mode=parsed, selected_unit=None, target_unit=None)
                if parsed == "county" and scope != "statewide":
                    set_state(scope="statewide")
                st.rerun()
        with c_type:
            if geo_mode == "district":
                keys = list(UTYPE_LABELS)
                new_u = st.selectbox("District type", keys, index=keys.index(unit_type), format_func=UTYPE_LABELS.get,
                                     label_visibility="collapsed", key="tb_utype")
                if new_u != unit_type:
                    set_state(unit_type=new_u, selected_unit=None, target_unit=None)
                    st.rerun()
            else:
                st.caption("100 NC counties")
        with c_alerts:
            alerts = load_alerts()
            unseen = [a for a in alerts["alert_id"] if a not in st.session_state.get("seen_alert_ids", set())]
            label = f"🔔 {len(unseen)}" if unseen else "🔔"
            with st.popover(label, width="stretch", help="Opponent activity alerts from the snapshot"):
                st.markdown("**GOP-side activity alerts**")
                if alerts.empty:
                    st.caption("No alerts in the last 7 days of the snapshot.")
                for a in alerts.head(8).itertuples():
                    icon = "🔴" if a.severity == "high" else "🟠"
                    st.markdown(f"{icon} **{a.type}** — {a.text}")
                c1, c2 = st.columns(2)
                if c1.button("Mark read", key="tb_alert_read", width="stretch"):
                    st.session_state.seen_alert_ids = set(alerts["alert_id"])
                    st.rerun()
                if c2.button("Opponent page", key="tb_goto_opp", width="stretch"):
                    st.switch_page("app_pages/opponent.py")
        with c_chip:
            st.markdown(_freshness_chip(), unsafe_allow_html=True)
        with c_theme:
            if st.button("☀️" if theme == "dark" else "🌙", key="tb_theme", help="Switch light / dark", width="stretch"):
                toggle_theme()
                st.rerun()
