"""
Global session state + URL query-param sync, so every view is deep-linkable:
?race=senate&region=37183&theme=dark
"""

from __future__ import annotations

import streamlit as st

from campaign_intel.config import DEFAULT_THEME, RACES

_PARAMS = {
    "theme": (["light", "dark"], DEFAULT_THEME),
    "race": (list(RACES), "senate"),
}
_FREE = ["region"]


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


def race() -> str:
    return st.session_state.get("race", "senate")


def theme() -> str:
    return st.session_state.get("theme", DEFAULT_THEME)


def toggle_theme() -> None:
    set_state(theme="light" if theme() == "dark" else "dark")
