"""
Settings & diagnostics: theme, data snapshot status, credential checks and how to rebuild.
"""

import requests
import streamlit as st

from campaign_intel.config import GCP_PROJECT_ID, META_AD_TOKEN
from campaign_intel.data.bq import test_connection
from campaign_intel.data.loaders import load_manifest
from campaign_intel.state import set_state
from campaign_intel.ui.topbar import render_topbar

render_topbar("Settings & Data Diagnostics")

with st.container(border=True):
    st.markdown("### 🎨 Appearance")
    cur = st.session_state.get("theme", "dark")
    new = st.radio("Colour mode", ["Dark", "Light"], index=0 if cur == "dark" else 1, horizontal=True)
    if new.lower() != cur:
        set_state(theme=new.lower())
        st.rerun()

with st.container(border=True):
    st.markdown("### 🗄️ Data snapshot")
    st.markdown("The app reads **only** from the local snapshot in `data/cache/` — real data frozen at build time, so "
                "the demo never depends on a live API. Rebuild it to refresh:")
    st.code("uv run python -m campaign_intel.ingest.build_snapshot\n"
            "# re-derive only (no downloads):\n"
            "uv run python -m campaign_intel.ingest.build_snapshot --skip-ncsbe --skip-google --skip-meta", language="bash")
    m = load_manifest()
    if m:
        c1, c2 = st.columns(2)
        c1.markdown(f"**Built:** {m.get('built_at', '?')} UTC  \n"
                    f"**Google report updated:** {m.get('google_report_updated', '?')}  \n"
                    f"**Meta ads through:** {m.get('meta_latest_ad_start', '?')}")
        sw = m.get("statewide", {})
        c2.markdown(f"**Ads in snapshot:** {m.get('ads_total', 0):,}  \n"
                    f"**Spend classified to a side:** {m.get('ads_classified_share_of_spend', 0):.0%}  \n"
                    f"**NCSBE 2026 results file:** {sw.get('sen26_file_date', '?')}")
        with st.expander("Snapshot tables"):
            st.write(", ".join(m.get("tables", [])))
    if st.button("Clear app cache (reload snapshot files)"):
        st.cache_data.clear()
        st.success("Cache cleared.")

with st.container(border=True):
    st.markdown("### 🔌 Credentials (used only by the snapshot builder)")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**GCP project:** `{GCP_PROJECT_ID}`")
        if st.button("Test BigQuery", width="stretch"):
            ok, msg = test_connection()
            (st.success if ok else st.warning)(msg)
    with c2:
        st.markdown(f"**Meta Ad Library token:** {'configured' if META_AD_TOKEN else 'missing (set META_AD_TOKEN in .env)'}")
        if st.button("Test Meta token", width="stretch", disabled=not META_AD_TOKEN):
            try:
                r = requests.get("https://graph.facebook.com/v23.0/me", params={"access_token": META_AD_TOKEN}, timeout=10)
                if r.ok:
                    st.success("Token valid.")
                else:
                    st.warning(r.json().get("error", {}).get("message", "Token rejected"))
            except requests.RequestException as exc:
                st.warning(f"Network error: {exc}")
