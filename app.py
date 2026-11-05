"""
Main Application Entry Point per PROJECT_DESIGN.md §8.1 and UI_Design.md §11.
Sets page layout, injects custom CSS tokens, enables Altair themes,
initializes global state, and executes navigation.
"""

import streamlit as st

from campaign_intel.state import init_state
from campaign_intel.ui import styles
from campaign_intel.viz import themes

# 1. Page Configuration (Wide layout, custom title & icon)
st.set_page_config(
    page_title="NC Campaign War Room — Ad Intelligence",
    page_icon="🗳️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. Initialize Global State and URL Query Params
init_state()

# 3. Dynamic Theme Injection (CSS Tokens + Altair Theme)
theme = st.session_state.get("theme", "dark")
styles.inject(theme)
themes.enable(theme)

# 4. Multi-Page Navigation Configuration with Material Symbols
pages = {
    "Analyze": [
        st.Page("app_pages/overview.py", title="Overview", icon=":material/dashboard:", default=True),
        st.Page("app_pages/audience.py", title="Audience Intelligence", icon=":material/groups:"),
        st.Page("app_pages/opponent.py", title="Opponent Tracker", icon=":material/my_location:"),
        st.Page("app_pages/electorate.py", title="Electorate & Turnout", icon=":material/how_to_vote:"),
    ],
    "Plan": [
        st.Page("app_pages/war_room.py", title="War Room", icon=":material/military_tech:"),
    ],
    "Review": [
        st.Page("app_pages/backtest.py", title="2026 Backtest", icon=":material/fact_check:"),
    ],
    "Reference": [
        st.Page("app_pages/methodology.py", title="Methodology & Data Notes", icon=":material/menu_book:"),
        st.Page("app_pages/settings.py", title="Settings", icon=":material/settings:"),
    ]
}

nav = st.navigation(pages, position="sidebar")
nav.run()
