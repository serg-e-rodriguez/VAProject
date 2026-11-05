"""
Global session state + URL query-param sync (PROJECT_DESIGN.md §8.2), so views are deep-linkable:
?scope=statewide&geo_mode=district&unit_type=cd&theme=dark
"""

from __future__ import annotations

import streamlit as st

from campaign_intel.config import (
    DEFAULT_DISTRICT_TYPE,
    DEFAULT_GEO_MODE,
    DEFAULT_SCOPE,
    DEFAULT_THEME,
    DISTRICT_TYPES,
    GEO_MODES,
    SCOPES,
)

_PARAMS = {
    "theme": (["light", "dark"], DEFAULT_THEME),
    "scope": (SCOPES, DEFAULT_SCOPE),
    "geo_mode": (GEO_MODES, DEFAULT_GEO_MODE),
    "unit_type": (DISTRICT_TYPES, DEFAULT_DISTRICT_TYPE),
}
_FREE = ["target_unit", "selected_unit"]


def init_state() -> None:
    for key, (allowed, default) in _PARAMS.items():
        if key not in st.session_state:
            val = st.query_params.get(key, default)
            st.session_state[key] = val if val in allowed else default
        st.query_params[key] = st.session_state[key]
    for key in _FREE:
        if key not in st.session_state:
            st.session_state[key] = st.query_params.get(key) or None
        _sync_free(key)
    st.session_state.setdefault("seen_alert_ids", set())


def _sync_free(key: str) -> None:
    val = st.session_state.get(key)
    if val:
        st.query_params[key] = val
    elif key in st.query_params:
        del st.query_params[key]


def set_state(**kwargs) -> None:
    for key, val in kwargs.items():
        st.session_state[key] = val
        if key in _PARAMS:
            st.query_params[key] = val
        elif key in _FREE:
            _sync_free(key)


def toggle_theme() -> None:
    set_state(theme="light" if st.session_state.get("theme", DEFAULT_THEME) == "dark" else "dark")
