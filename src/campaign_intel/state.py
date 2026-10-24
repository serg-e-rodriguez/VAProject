"""
Global session state initialization and URL query-param synchronization.
"""

import pandas as pd
import streamlit as st

from campaign_intel.config import (
    DEFAULT_DISTRICT_TYPE,
    DEFAULT_GEO_MODE,
    DEFAULT_SCOPE,
    DISTRICT_TYPES,
    GEO_MODES,
    SCOPES,
)


def init_state():
    """
    Initializes st.session_state with default values, syncing with st.query_params.
    Allows shareable deep links with ?scope=...&unit_type=...&theme=...
    """
    # 1. Theme
    if "theme" not in st.session_state:
        param_theme = st.query_params.get("theme")
        st.session_state.theme = param_theme if param_theme in ["light", "dark"] else "dark"
    st.query_params["theme"] = st.session_state.theme

    # 2. Scope (statewide vs district)
    if "scope" not in st.session_state:
        param_scope = st.query_params.get("scope", DEFAULT_SCOPE)
        st.session_state.scope = param_scope if param_scope in SCOPES else DEFAULT_SCOPE
    st.query_params["scope"] = st.session_state.scope

    # 3. Geo Mode (district vs county)
    if "geo_mode" not in st.session_state:
        param_geo = st.query_params.get("geo_mode", DEFAULT_GEO_MODE)
        st.session_state.geo_mode = param_geo if param_geo in GEO_MODES else DEFAULT_GEO_MODE
    st.query_params["geo_mode"] = st.session_state.geo_mode

    # 4. District Type (cd, sd, hd)
    if "unit_type" not in st.session_state:
        param_utype = st.query_params.get("unit_type", DEFAULT_DISTRICT_TYPE)
        st.session_state.unit_type = param_utype if param_utype in DISTRICT_TYPES else DEFAULT_DISTRICT_TYPE
    st.query_params["unit_type"] = st.session_state.unit_type

    # 5. Target Unit (e.g. for single district race)
    if "target_unit" not in st.session_state:
        st.session_state.target_unit = st.query_params.get("target_unit", None)
    if st.session_state.target_unit:
        st.query_params["target_unit"] = st.session_state.target_unit
    elif "target_unit" in st.query_params and not st.session_state.target_unit:
        del st.query_params["target_unit"]

    # 6. Selected Unit (for drill-down and map selection cross-filtering)
    if "selected_unit" not in st.session_state:
        st.session_state.selected_unit = st.query_params.get("selected_unit", None)
    if st.session_state.selected_unit:
        st.query_params["selected_unit"] = st.session_state.selected_unit
    elif "selected_unit" in st.query_params and not st.session_state.selected_unit:
        del st.query_params["selected_unit"]

    # 7. Date Range
    if "date_range" not in st.session_state:
        st.session_state.date_range = st.query_params.get("date_range", "Last 8 weeks")
    st.query_params["date_range"] = st.session_state.date_range

    # 8. Alert Tracker
    if "seen_alert_ids" not in st.session_state:
        st.session_state.seen_alert_ids = set()

    # 9. War Room Allocation DataFrame
    if "allocation" not in st.session_state:
        st.session_state.allocation = pd.DataFrame(columns=["unit_id", "channel", "audience", "week", "dollars"])

    # 10. War Room Locked rows
    if "locked_items" not in st.session_state:
        st.session_state.locked_items = set()


def toggle_theme():
    """Toggles theme between light and dark and syncs to query params."""
    current = st.session_state.get("theme", "light")
    new_theme = "dark" if current == "light" else "light"
    st.session_state.theme = new_theme
    st.query_params["theme"] = new_theme
