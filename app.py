"""
NC Democrats — campaign intelligence for the 2026 US Senate and US House races.

Sidebar: pick the race first (Senate / House), then one of three views:
Overview · Region Analysis (-> Audience Analysis of the selected region) · Opponent Tracker · War Room.
"""

import streamlit as st

from campaign_intel.config import RACES
from campaign_intel.data.loaders import load_manifest, load_regions, snapshot_ready
from campaign_intel.state import init_state, race, set_state, theme, toggle_theme
from campaign_intel.ui import styles
from campaign_intel.viz import themes

st.set_page_config(page_title="NC Democrats · Race Intelligence", page_icon="🗳️", layout="wide",
                   initial_sidebar_state="expanded")
init_state()
styles.inject(theme())
themes.enable(theme())

if not snapshot_ready():
    st.error("No data snapshot found. Build it once with: "
             "`uv run python -m campaign_intel.ingest.build_snapshot --skip-google --skip-meta`")
    st.stop()

PAGES = {
    "overview": st.Page("app_pages/overview.py", title="Overview", icon=":material/dashboard:", default=True),
    "regions": st.Page("app_pages/regions.py", title="Region Analysis", icon=":material/map:"),
    "opponent": st.Page("app_pages/opponent.py", title="Opponent Tracker", icon=":material/my_location:"),
    "war_room": st.Page("app_pages/war_room.py", title="War Room", icon=":material/strategy:"),
}
nav = st.navigation(list(PAGES.values()), position="hidden")

with st.sidebar:
    st.markdown("<div class='brand'>🗳️ NC Democrats<small>2026 race intelligence</small></div>", unsafe_allow_html=True)

    st.markdown("<div class='side-label'>1 · Choose the race</div>", unsafe_allow_html=True)
    picked = st.segmented_control("Race", list(RACES), default=race(), format_func=lambda r: RACES[r]["label"],
                                  key="race_pick", label_visibility="collapsed", width="stretch")
    if picked and picked != race():
        set_state(race=picked, region=None)
        st.rerun()
    st.caption("Statewide, mapped by county" if race() == "senate" else "14 congressional districts")

    st.markdown("<div class='side-label'>2 · Explore</div>", unsafe_allow_html=True)
    st.page_link(PAGES["overview"])
    st.page_link(PAGES["regions"])
    reg = st.session_state.get("region")
    name = None
    if reg:
        r = load_regions(race())
        hit = r[r["unit_id"] == reg]
        name = hit["label"].iloc[0] if len(hit) else None
    sub = (f"↳ Audience Analysis · <b>{name}</b>" if name else
           f"↳ Audience Analysis · pick a {RACES[race()]['unit_word']} on the map")
    st.markdown(f"<div class='subnav'>{sub}</div>", unsafe_allow_html=True)
    st.page_link(PAGES["opponent"])

    st.markdown("<div class='side-label'>3 · Plan</div>", unsafe_allow_html=True)
    st.page_link(PAGES["war_room"])

    st.divider()
    if st.button("☀️ Light mode" if theme() == "dark" else "🌙 Dark mode", key="theme_btn", width="stretch"):
        toggle_theme()
        st.rerun()
    m = load_manifest()
    st.markdown(
        f"<div class='side-foot'>Data snapshot {m.get('built_at', '?')[:10]} · NCSBE election results & voter files · "
        f"Google Ads Transparency · Meta Ad Library. Ad spend is NC-apportioned, since Jul 1, 2026.</div>",
        unsafe_allow_html=True)

nav.run()
