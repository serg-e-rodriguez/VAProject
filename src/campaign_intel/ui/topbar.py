"""
Top navigation bar component per UI_Design.md §4.2.
Houses Scope Switcher, Geography Toggle, District Type Selector,
Alerts Popover, Freshness Chip, and Theme Switcher with responsive sizing.
"""

import streamlit as st

from campaign_intel.state import toggle_theme


def render_topbar(page_title: str):
    """
    Renders top navigation bar in a bordered container with responsive columns.
    Ensures button texts and icons never exceed their bounding boxes.
    """
    current_theme = st.session_state.get("theme", "dark")
    scope = st.session_state.get("scope", "statewide")
    geo_mode = st.session_state.get("geo_mode", "district")
    unit_type = st.session_state.get("unit_type", "cd")

    with st.container(border=True):
        col_title, col_scope, col_geo, col_type, col_alerts, col_chip, col_theme = st.columns(
            [2.8, 1.4, 1.3, 1.5, 1.2, 1.7, 1.1],
            vertical_alignment="center",
            gap="small"
        )

        with col_title:
            st.markdown(
                f"<h3 style='margin:0; font-size:17px; font-weight:800; color:var(--text-primary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;' title='{page_title}'>{page_title}</h3>",
                unsafe_allow_html=True
            )

        with col_scope:
            scope_idx = 0 if scope == "statewide" else 1
            new_scope = st.selectbox(
                "Race Scope",
                options=["Statewide", "District Race"],
                index=scope_idx,
                label_visibility="collapsed",
                key="topbar_scope_select"
            )
            parsed_scope = "statewide" if new_scope == "Statewide" else "district"
            if parsed_scope != scope:
                st.session_state.scope = parsed_scope
                st.query_params["scope"] = parsed_scope
                st.rerun()

        with col_geo:
            geo_idx = 0 if geo_mode == "district" else 1
            new_geo = st.segmented_control(
                "Geo View",
                options=["District", "County"],
                default=["District", "County"][geo_idx],
                label_visibility="collapsed",
                key="topbar_geo_segmented"
            )
            parsed_geo = (new_geo or "District").lower()
            if parsed_geo != geo_mode:
                st.session_state.geo_mode = parsed_geo
                st.query_params["geo_mode"] = parsed_geo
                st.rerun()

        with col_type:
            if geo_mode == "district":
                utype_map = {"cd": "Congressional", "sd": "State Senate", "hd": "State House"}
                reverse_map = {"Congressional": "cd", "State Senate": "sd", "State House": "hd"}
                current_label = utype_map.get(unit_type, "Congressional")
                new_utype_label = st.selectbox(
                    "District Type",
                    options=["Congressional", "State Senate", "State House"],
                    index=["Congressional", "State Senate", "State House"].index(current_label),
                    label_visibility="collapsed",
                    key="topbar_utype_select"
                )
                parsed_utype = reverse_map[new_utype_label]
                if parsed_utype != unit_type:
                    st.session_state.unit_type = parsed_utype
                    st.query_params["unit_type"] = parsed_utype
                    st.session_state.selected_unit = None
                    st.rerun()
            else:
                st.markdown("<span style='font-size:12px; color:var(--text-muted);'>100 NC Counties</span>", unsafe_allow_html=True)

        with col_alerts, st.popover("🔔 Alerts", use_container_width=True):
            st.markdown("#### 🚨 Opponent & Market Alerts")
            st.markdown("""
                - **NCGOP & Allies**: +18 new video ads in Raleigh & Charlotte DMAs (last 48h).
                - **Theme Emergence**: Opponent increased Economy & Inflation ads (+35%).
                - **Spend Tier Surge**: Forward NC PAC raised Meta weekly flight to ≥ $50k.
                """)
            if st.button("Open Opponent Tracker", key="topbar_goto_opponent", use_container_width=True):
                st.switch_page("app_pages/opponent.py")

        with col_chip:
            chip_html = """
            <div style="font-size: 11px; font-weight: 600; color: var(--text-secondary); background-color: var(--accent-soft); border: 1px solid rgba(43,181,122,0.25); border-radius: 999px; padding: 6px 10px; text-align: center; white-space: nowrap;">
                🟢 Meta API Live · BQ Oct 2026
            </div>
            """
            st.markdown(chip_html, unsafe_allow_html=True)

        with col_theme:
            theme_label = "☀️ Light" if current_theme == "dark" else "🌙 Dark"
            if st.button(theme_label, key="topbar_theme_toggle_btn", help="Switch Light/Dark theme", use_container_width=True):
                toggle_theme()
                st.rerun()
