"""
NC Democrats — midterm campaign planning for the US Senate and US House races (2026 cycle).

Sidebar: pick the race (Senate / House) and the timeframe of ad data to analyze, then a page:
Overview · Region Analysis (-> Audience Analysis of the selected region) · Opponent Tracker · War Room · Model Check.
"""

import html

import pandas as pd
import streamlit as st

from campaign_intel.config import RACES
from campaign_intel.data.loaders import (
    TIMEFRAME_FLOOR,
    coverage,
    default_timeframe,
    fmt_money,
    load_manifest,
    load_regions,
    snapshot_date,
    snapshot_ready,
    timeframe,
)
from campaign_intel.state import init_state, race, set_state, theme, toggle_theme
from campaign_intel.ui import styles
from campaign_intel.viz import themes

st.set_page_config(page_title="NC Democrats · Race Intelligence", page_icon="🗳️", layout="wide",
                   initial_sidebar_state="expanded")
init_state()
styles.inject(theme())
themes.enable(theme())

if not snapshot_ready():
    st.warning("No data snapshot found. Build it once with: "
             "`uv run python -m campaign_intel.ingest.build_snapshot --skip-google --skip-meta`")
    st.stop()

PAGES = {
    "overview": st.Page("app_pages/overview.py", title="Overview", icon=":material/dashboard:", default=True),
    "regions": st.Page("app_pages/regions.py", title="Region Analysis", icon=":material/map:"),
    "opponent": st.Page("app_pages/opponent.py", title="Opponent Tracker", icon=":material/my_location:"),
    "war_room": st.Page("app_pages/war_room.py", title="War Room", icon=":material/strategy:"),
    "model_check": st.Page("app_pages/model_check.py", title="Model Check", icon=":material/fact_check:"),
}
nav = st.navigation(list(PAGES.values()), position="hidden")


def _set_timeframe():
    v = st.session_state.get("tf_pick") or ()
    if len(v) == 2:  # the picker returns one date while the second is still being chosen
        st.session_state["timeframe"] = (pd.Timestamp(v[0]), pd.Timestamp(v[1]))


def _reset_timeframe():
    st.session_state["timeframe"] = default_timeframe()
    st.session_state["tf_pick"] = tuple(d.date() for d in default_timeframe())


def _status(ok: bool, title: str, text: str) -> str:
    cls = "ok" if ok else "none"
    return (f"<div class='src-status {cls}'><span class='src-mark'>{'✓' if ok else '!'}</span>"
            f"<div><b>{html.escape(title)}</b><br>{html.escape(text)}</div></div>")


def timeframe_picker() -> None:
    """Date range for the ad data (Google via BigQuery, Meta Ad Library) and a per-source check of what is there."""
    s, e = timeframe()
    if "tf_pick" not in st.session_state:
        st.session_state["tf_pick"] = (s.date(), e.date())
    st.date_input("Timeframe", key="tf_pick", min_value=TIMEFRAME_FLOOR.date(),
                  max_value=max(pd.Timestamp.today(), snapshot_date()).date(), format="MM/DD/YYYY",
                  label_visibility="collapsed", on_change=_set_timeframe,
                  help="Ad spend, weekly trends, advertisers, messages and audiences use only ad delivery inside "
                       "this range (each ad's spend is pro-rated by its days inside it).")
    c = coverage(race())
    rows = []
    for src, title in (("google", "Google ads · BigQuery"), ("meta", "Meta Ad Library")):
        x = c[src]
        if x["has_data"]:
            rows.append(_status(True, title, f"{x['ads']:,} ads · {fmt_money(x['spend'])} in this race"))
        else:
            held = (f"stored: {x['stored_first']:%b %-d, %Y} – {x['stored_last']:%b %-d, %Y}"
                    if x["stored_first"] is not None else "nothing stored")
            rows.append(_status(False, title, f"No data found in this timeframe ({held})"))
    if c["after_snapshot"]:
        rows.append(_status(False, "After the snapshot",
                            f"Stored data ends {snapshot_date():%b %-d, %Y}; later days have no data."))
    rows.append(_status(True, "NCSBE & survey files", "Fixed dates (2022 turnout, 2024 registration and "
                                                       "results); not filtered by the timeframe."))
    st.markdown("".join(rows), unsafe_allow_html=True)
    if (s, e) != default_timeframe():
        st.button("Reset to the campaign window", key="tf_reset", on_click=_reset_timeframe, width="stretch")
    st.caption("The War Room plans from its own date; the timeframe does not change it.")


with st.sidebar:
    st.markdown("<div class='brand'>🗳️ NC Democrats<small>Midterm campaign planning</small></div>", unsafe_allow_html=True)

    st.markdown("<div class='side-label'>1 · Choose the race</div>", unsafe_allow_html=True)
    picked = st.segmented_control("Race", list(RACES), default=race(), format_func=lambda r: RACES[r]["label"],
                                  key="race_pick", label_visibility="collapsed", width="stretch")
    if picked and picked != race():
        set_state(race=picked, region=None)
        st.rerun()
    st.caption("Statewide, mapped by county" if race() == "senate" else "14 congressional districts")

    st.markdown("<div class='side-label'>2 · Timeframe</div>", unsafe_allow_html=True)
    timeframe_picker()

    st.markdown("<div class='side-label'>3 · Explore</div>", unsafe_allow_html=True)
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

    st.markdown("<div class='side-label'>4 · Plan</div>", unsafe_allow_html=True)
    st.page_link(PAGES["war_room"])

    st.markdown("<div class='side-label'>5 · Check the model</div>", unsafe_allow_html=True)
    st.page_link(PAGES["model_check"])
    st.caption("Model estimate vs the 2026 results")

    st.divider()
    if st.button("☀️ Light mode" if theme() == "dark" else "🌙 Dark mode", key="theme_btn", width="stretch"):
        toggle_theme()
        st.rerun()
    m = load_manifest()
    st.markdown(
        f"<div class='side-foot'>Data snapshot {m.get('built_at', '?')[:10]} · NCSBE election results & voter files · "
        f"Google Ads Transparency · Meta Ad Library. Ad spend is NC-apportioned and limited to the timeframe above.</div>",
        unsafe_allow_html=True)

nav.run()
