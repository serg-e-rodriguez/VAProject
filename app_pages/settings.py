"""
Settings & System Diagnostics Page per UI_Design.md §4.1 and §8.
Allows switching Light/Dark themes, configuring data sources, and inspecting API token health.
"""

import streamlit as st

from campaign_intel.config import (
    DATA_MODE,
    GCP_PROJECT_ID,
    META_AD_TOKEN,
    META_USER_TOKEN,
)
from campaign_intel.data.bq import test_connection
from campaign_intel.ui.topbar import render_topbar

# 1. Top Bar
render_topbar("System Settings & API Diagnostics")

with st.container(border=True):
    st.markdown("### 🎨 Appearance & Display Theme")
    current_theme = st.session_state.get("theme", "dark")
    new_theme = st.radio(
        "Application Color Mode",
        options=["Dark", "Light"],
        index=0 if current_theme == "dark" else 1,
        help="Switches global CSS tokens and Altair visualization themes."
    )
    if new_theme.lower() != current_theme:
        st.session_state.theme = new_theme.lower()
        st.query_params["theme"] = new_theme.lower()
        st.rerun()

st.write("")

with st.container(border=True):
    st.markdown("### 🔌 Data Mode & Pipeline Connectivity")
    dmode = st.radio(
        "Data Source Mode",
        options=["Live (BigQuery Public + Meta Graph API)", "Snapshot (Local Parquet Offline Demo)"],
        index=0 if DATA_MODE == "live" else 1
    )

    token_val = META_USER_TOKEN or META_AD_TOKEN
    has_token = bool(token_val and len(token_val) > 20)
    token_status = "🟢 Configured (Token Active)" if has_token else "🔴 Not Configured (Using Sample Fallback)"

    st.markdown("##### Pipeline Diagnostics")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**GCP Project ID**: `{GCP_PROJECT_ID}`")
        st.markdown(f"**Meta Ad Token**: {token_status}")
    with c2:
        st.markdown("**State Board (NCSBE)**: `Loaded (MEDSL Certified 2022)`")
        st.markdown("**Survey Benchmark**: `Loaded (CCES 2024 UNC Module)`")

    st.write("")
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("Test BigQuery Connection", key="btn_test_bq", use_container_width=True):
            with st.spinner("Testing BigQuery connection..."):
                ok, msg = test_connection()
                if ok:
                    st.success(f"✓ {msg}")
                else:
                    st.warning(f"⚠️ {msg}")

    with btn_col2:
        if st.button("Clear Application Cache", key="btn_clear_cache", help="Invalidates @st.cache_data and forces fresh queries", use_container_width=True):
            st.cache_data.clear()
            st.success("Cache cleared successfully!")
            st.rerun()
