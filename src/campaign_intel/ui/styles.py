"""
Design tokens and dynamic CSS injection for Light and Dark modes per UI_Design.md.
Light and dark tokens, component styles, and light-mode repaints of native widgets.
"""

import streamlit as st

TOKENS = {
    "light": {
        "bg_canvas": "#EEF0F3",
        "bg_frame": "#F6F7F9",
        "surface": "#FFFFFF",
        "surface_raised": "#FFFFFF",
        "border": "#ECEEF2",
        "gridline": "#EEF0F3",
        "text_primary": "#1B1F29",
        "text_secondary": "#6B7280",
        "text_muted": "#9CA3AF",
        "accent": "#22A06B",
        "accent_soft": "#E6F6EE",
        "dem": "#2F6FED",
        "dem_soft": "#9CC7F7",
        "rep": "#E04848",
        "rep_soft": "#F4A9A9",
        "swing": "#8B5CF6",
        "neutral_series": "#F2C14E",
        "pill_up_bg": "#E8F0FF",
        "pill_up_text": "#2F6FED",
        "pill_down_bg": "#FDECEC",
        "pill_down_text": "#D14343",
        "pill_neutral_bg": "#F1F2F4",
        "pill_neutral_text": "#6B7280",
        "badge_observed_bg": "#E6F6EE",
        "badge_observed_text": "#1E8A5C",
        "badge_aggregated_bg": "#EEF2FF",
        "badge_aggregated_text": "#4F46E5",
        "badge_modeled_bg": "#FFF4E0",
        "badge_modeled_text": "#B26B00",
        "badge_sample_bg": "#FDECEC",
        "badge_sample_text": "#B42318",
        "radius_card": "16px",
        "radius_control": "10px",
        "radius_pill": "999px",
        "shadow_card": "0 1px 3px rgba(16, 24, 40, 0.05)",
        "shadow_pop": "0 8px 24px rgba(16, 24, 40, 0.12)",
    },
    "dark": {
        "bg_canvas": "#0B0D12",
        "bg_frame": "#10131A",
        "surface": "#171B24",
        "surface_raised": "#1F2430",
        "border": "#262B36",
        "gridline": "#232834",
        "text_primary": "#E8EAF0",
        "text_secondary": "#A0A7B4",
        "text_muted": "#6B7280",
        "accent": "#2BB57A",
        "accent_soft": "rgba(43, 181, 122, 0.14)",
        "dem": "#5B8DEF",
        "dem_soft": "#2C4A85",
        "rep": "#F06363",
        "rep_soft": "#7A3434",
        "swing": "#A78BFA",
        "neutral_series": "#F2C14E",
        "pill_up_bg": "rgba(91, 141, 239, 0.16)",
        "pill_up_text": "#7AA6F4",
        "pill_down_bg": "rgba(240, 99, 99, 0.16)",
        "pill_down_text": "#F27E7E",
        "pill_neutral_bg": "rgba(160, 167, 180, 0.16)",
        "pill_neutral_text": "#A0A7B4",
        "badge_observed_bg": "rgba(43, 181, 122, 0.16)",
        "badge_observed_text": "#5FD39E",
        "badge_aggregated_bg": "rgba(79, 70, 229, 0.16)",
        "badge_aggregated_text": "#818CF8",
        "badge_modeled_bg": "rgba(178, 107, 0, 0.16)",
        "badge_modeled_text": "#FBBF24",
        "badge_sample_bg": "rgba(180, 35, 24, 0.16)",
        "badge_sample_text": "#F87171",
        "radius_card": "16px",
        "radius_control": "10px",
        "radius_pill": "999px",
        "shadow_card": "none",
        "shadow_pop": "0 8px 24px rgba(0, 0, 0, 0.5)",
    }
}


def get_tokens(theme: str = "dark") -> dict:
    return TOKENS.get(theme.lower(), TOKENS["dark"])


def inject(theme: str = "dark"):
    """Injects the design tokens as CSS variables plus the app's component styles."""
    t = get_tokens(theme)
    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Mulish:wght@400;500;600;700;800&display=swap');

    :root {{
        --bg-frame: {t['bg_frame']};
        --surface: {t['surface']};
        --surface-raised: {t['surface_raised']};
        --border: {t['border']};
        --text-primary: {t['text_primary']};
        --text-secondary: {t['text_secondary']};
        --text-muted: {t['text_muted']};
        --accent: {t['accent']};
        --accent-soft: {t['accent_soft']};
        --dem: {t['dem']};
        --rep: {t['rep']};
        --swing: {t['swing']};
        --dem-bg: {t['pill_up_bg']};
        --rep-bg: {t['pill_down_bg']};
        --neutral-bg: {t['pill_neutral_bg']};
        --radius: 14px;
        --shadow: {t['shadow_card']};
    }}

    html, body, .stApp, p, label, li, h1, h2, h3, h4, h5, h6, input, textarea, select {{
        font-family: 'Mulish', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    }}
    .stApp {{ background-color: var(--bg-frame) !important; color: var(--text-primary) !important; }}
    header[data-testid="stHeader"] {{ background: transparent !important; }}
    .main .block-container, [data-testid="stMainBlockContainer"] {{
        max-width: 1360px !important; padding-top: 2.2rem !important; padding-bottom: 3rem !important;
    }}

    /* Sidebar */
    section[data-testid="stSidebar"] {{
        background-color: var(--surface) !important; border-right: 1px solid var(--border) !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{ padding-top: 1.2rem; }}
    .brand {{ font-size: 15px; font-weight: 800; color: var(--text-primary); line-height: 1.25; margin-bottom: 2px; }}
    .brand small {{ display: block; font-size: 11.5px; font-weight: 600; color: var(--text-muted); margin-top: 3px; }}
    .side-label {{ font-size: 11px; font-weight: 800; letter-spacing: .7px; text-transform: uppercase;
        color: var(--text-muted); margin: 18px 0 6px; }}
    section[data-testid="stSidebar"] [data-testid="stPageLink"] a {{
        border-radius: 10px; padding: 6px 10px; margin: 1px 0;
    }}
    section[data-testid="stSidebar"] [data-testid="stPageLink"] a p {{ font-size: 14px; font-weight: 600; }}
    section[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"],
    section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"][aria-current="page"] {{
        background: var(--accent-soft) !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"] p {{ color: var(--accent) !important; }}
    .subnav {{ margin: -2px 0 4px 34px; padding-left: 10px; border-left: 2px solid var(--border);
        font-size: 12.5px; color: var(--text-secondary); line-height: 1.5; }}
    .subnav b {{ color: var(--text-primary); }}
    .side-foot {{ font-size: 11px; color: var(--text-muted); line-height: 1.5; margin-top: 8px; }}

    /* Page header */
    .page-head h1 {{ font-size: 28px; font-weight: 800; margin: 0; padding: 0; color: var(--text-primary); line-height: 1.2; }}
    .page-sub {{ font-size: 14px; color: var(--text-secondary); margin-top: 4px; }}
    .page-head {{ margin-bottom: 18px; }}

    /* Cards = bordered containers */
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: var(--surface) !important; border: 1px solid var(--border) !important;
        border-radius: var(--radius) !important; box-shadow: var(--shadow) !important;
    }}

    /* KPI tiles */
    .kpi {{ background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
        padding: 14px 18px; min-height: 112px; box-shadow: var(--shadow); }}
    .kpi-label {{ font-size: 12px; font-weight: 700; color: var(--text-secondary); text-transform: uppercase;
        letter-spacing: .5px; }}
    .kpi-value {{ font-size: 26px; font-weight: 800; color: var(--text-primary); margin-top: 6px;
        font-variant-numeric: tabular-nums; line-height: 1.15; }}
    .kpi-value.dem {{ color: var(--dem); }}
    .kpi-value.rep {{ color: var(--rep); }}
    .kpi-sub {{ font-size: 12.5px; color: var(--text-secondary); margin-top: 6px; line-height: 1.4; }}

    /* Section headers inside cards */
    .sec {{ margin-bottom: 8px; }}
    .sec-title {{ font-size: 16px; font-weight: 800; color: var(--text-primary); }}
    .sec-sub {{ font-size: 13px; color: var(--text-secondary); margin-top: 2px; line-height: 1.45; }}
    .source {{ font-size: 11.5px; color: var(--text-muted); margin-top: 4px; line-height: 1.45; }}
    .group-title {{ font-size: 13px; font-weight: 800; letter-spacing: .6px; text-transform: uppercase;
        color: var(--text-muted); margin: 26px 0 10px; }}

    /* Callouts */
    .callout {{ border-left: 4px solid var(--accent); background: var(--accent-soft); border-radius: 10px;
        padding: 12px 16px; margin: 6px 0 10px; }}
    .callout.dem {{ border-left-color: var(--dem); background: var(--dem-bg); }}
    .callout.rep {{ border-left-color: var(--rep); background: var(--rep-bg); }}
    .callout-title {{ font-size: 14.5px; font-weight: 800; color: var(--text-primary); }}
    .callout-body {{ font-size: 13px; color: var(--text-secondary); margin-top: 4px; line-height: 1.5; }}
    ul.why {{ margin: 4px 0 4px 2px; padding-left: 18px; }}
    ul.why li {{ font-size: 13.5px; color: var(--text-primary); margin-bottom: 6px; line-height: 1.45; }}

    /* Pills */
    .pill {{ display: inline-block; font-size: 12px; font-weight: 800; padding: 3px 10px; border-radius: 999px;
        background: var(--neutral-bg); color: var(--text-secondary); margin-right: 6px; }}
    .pill.dem {{ background: var(--dem-bg); color: var(--dem); }}
    .pill.rep {{ background: var(--rep-bg); color: var(--rep); }}

    /* Region header */
    .region-head {{ display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin: 2px 0 12px; }}
    .region-head h2 {{ font-size: 22px; font-weight: 800; margin: 0; padding: 0; color: var(--text-primary); }}

    /* Ad cards */
    .adcard {{ border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px; margin-bottom: 10px;
        background: var(--surface); }}
    .adcard-head {{ display: flex; justify-content: space-between; gap: 10px; font-size: 13.5px; color: var(--text-primary); }}
    .adcard-head span {{ font-size: 12px; color: var(--text-muted); white-space: nowrap; }}
    .adcard-body {{ font-size: 13px; color: var(--text-primary); margin: 6px 0; line-height: 1.5; white-space: pre-line; }}
    .adcard-tags .tag {{ display: inline-block; font-size: 10.5px; font-weight: 800; text-transform: uppercase;
        letter-spacing: .4px; padding: 2px 8px; border-radius: 999px; background: var(--rep-bg); color: var(--rep);
        margin-right: 4px; }}
    .adcard-foot {{ display: flex; flex-wrap: wrap; gap: 14px; font-size: 12px; color: var(--text-secondary); margin-top: 6px; }}
    .adcard-foot a {{ color: var(--accent); text-decoration: none; font-weight: 700; margin-left: auto; }}

    /* Inputs */
    div[data-baseweb="select"] > div, input {{ border-radius: 10px !important; }}
    button[kind="primary"] {{ background-color: var(--accent) !important; border: none !important; color: #fff !important; }}

    /* Vega tooltip */
    #vg-tooltip-element {{
        background-color: var(--surface-raised) !important; border: 1px solid var(--border) !important;
        border-radius: 10px !important; color: var(--text-primary) !important; font-family: 'Mulish', sans-serif !important;
        font-size: 12px !important; padding: 8px 12px !important;
    }}
    #vg-tooltip-element table tr td.key {{ color: var(--text-secondary) !important; }}
    #vg-tooltip-element table tr td.value {{ color: var(--text-primary) !important; font-weight: 700 !important; }}

    div[data-testid="stDataFrame"] {{ border-radius: 10px !important; }}
    {_light_overrides(t) if theme.lower() == "light" else ""}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def _light_overrides(t: dict) -> str:
    """
    Streamlit's native theme is fixed to dark in .streamlit/config.toml and cannot be switched
    from Python, so in light mode every native widget still ships dark-theme colours. This layer
    repaints them with the light tokens. Glide dataframes draw on a canvas from the JS theme, so
    they are colour-inverted (hue-preserving) instead.
    """
    return f"""
    /* ---------- Light-mode overrides for native (dark-themed) Streamlit widgets ---------- */

    /* Sidebar navigation */
    section[data-testid="stSidebar"] [data-testid="stNavSectionHeader"],
    section[data-testid="stSidebar"] [data-testid="stNavSectionHeader"] p {{
        color: {t['text_muted']} !important;
        font-weight: 700 !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] p,
    section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] span {{
        color: {t['text_primary']} !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] [data-testid="stIconMaterial"] {{
        color: {t['text_secondary']} !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover p,
    section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover span {{
        color: {t['accent']} !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] p,
    section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] span {{
        color: #FFFFFF !important;
    }}
    [data-testid="stSidebarCollapseButton"] span,
    [data-testid="stExpandSidebarButton"] span,
    header[data-testid="stHeader"] [data-testid="stIconMaterial"] {{
        color: {t['text_secondary']} !important;
    }}

    /* Custom sidebar nav (st.page_link) */
    section[data-testid="stSidebar"] [data-testid="stPageLink"] p,
    section[data-testid="stSidebar"] [data-testid="stPageLink"] span {{
        color: {t['text_primary']} !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stPageLink"] [data-testid="stIconMaterial"] {{
        color: {t['text_secondary']} !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"] p,
    section[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"] span {{
        color: {t['accent']} !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover {{
        background-color: {t['bg_frame']} !important;
    }}

    .stApp [data-testid="stSelectbox"] div[value], .stApp [data-testid="stSelectbox"] span,
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{
        color: {t['text_secondary']} !important;
    }}
    .stApp [data-testid="stSelectbox"] div[value],
    .stApp [data-testid="stSelectbox"] input {{
        color: {t['text_primary']} !important;
        -webkit-text-fill-color: {t['text_primary']} !important;
    }}

    /* Widget labels, slider ticks, tooltip icons */
    .stApp [data-testid="stWidgetLabel"],
    .stApp [data-testid="stWidgetLabel"] p {{
        color: {t['text_primary']} !important;
    }}
    .stApp [data-testid="stSliderTickBar"] p {{
        color: {t['text_secondary']} !important;
    }}
    .stApp [data-testid="stTooltipIcon"] svg {{
        color: {t['text_muted']} !important;
    }}

    /* Select boxes, multiselects, number & text inputs */
    .stApp [data-testid="stSelectbox"] div,
    .stApp [data-testid="stMultiSelect"] div:not([data-testid="stMultiSelectTagsContainer"]),
    .stApp [data-testid="stNumberInputContainer"],
    .stApp [data-testid="stNumberInputContainer"] div,
    .stApp [data-testid="stTextInputRootElement"],
    .stApp [data-testid="stTextInputRootElement"] div {{
        background-color: {t['surface']} !important;
        color: {t['text_primary']} !important;
    }}
    .stApp [data-testid="stSelectbox"] > div > div,
    .stApp [data-testid="stMultiSelect"] > div > div,
    .stApp [data-testid="stNumberInputContainer"],
    .stApp [data-testid="stTextInputRootElement"] {{
        border-color: #D5D9E0 !important;
    }}
    .stApp [data-testid="stSelectbox"] svg,
    .stApp [data-testid="stMultiSelect"] > div svg,
    .stApp [data-testid="stNumberInput"] button svg {{
        color: {t['text_secondary']} !important;
    }}
    .stApp [data-testid="stNumberInput"] button {{
        background-color: {t['surface']} !important;
        color: {t['text_secondary']} !important;
    }}
    .stApp [data-testid="stNumberInput"] button:hover {{
        background-color: {t['accent_soft']} !important;
    }}
    .stApp [data-testid="stNumberInput"] button:hover svg {{
        color: {t['accent']} !important;
    }}

    /* Dropdown menus (rendered in a portal outside .stApp) */
    div[data-baseweb="popover"] ul,
    div[data-baseweb="popover"] li,
    div[data-baseweb="popover"] [role="listbox"],
    div[data-baseweb="popover"] [role="option"] {{
        background-color: {t['surface']} !important;
        color: {t['text_primary']} !important;
    }}
    div[data-baseweb="popover"] [role="option"]:hover,
    div[data-baseweb="popover"] [aria-selected="true"] {{
        background-color: {t['accent_soft']} !important;
    }}

    /* Segmented controls & pills: unselected options */
    .stApp [data-testid="stButtonGroup"] button:not([aria-checked="true"]):not([aria-pressed="true"]):not([data-selected="true"]) {{
        background-color: {t['surface']} !important;
        color: {t['text_primary']} !important;
        border-color: #D5D9E0 !important;
    }}
    .stApp [data-testid="stButtonGroup"] button:not([aria-checked="true"]):not([aria-pressed="true"]):not([data-selected="true"]) p {{
        color: {t['text_primary']} !important;
    }}
    .stApp [data-testid="stButtonGroup"] button:not([aria-checked="true"]):not([aria-pressed="true"]):not([data-selected="true"]):hover {{
        background-color: {t['accent_soft']} !important;
        border-color: {t['accent']} !important;
    }}

    /* Secondary & link buttons */
    .stApp button[kind="secondary"],
    .stApp a[kind="secondary"] {{
        background-color: {t['surface']} !important;
        color: {t['text_primary']} !important;
        border: 1px solid #D5D9E0 !important;
    }}
    .stApp button[kind="secondary"] p,
    .stApp a[kind="secondary"] p {{
        color: {t['text_primary']} !important;
    }}
    .stApp button[kind="secondary"]:hover,
    .stApp a[kind="secondary"]:hover {{
        border-color: {t['accent']} !important;
        background-color: {t['accent_soft']} !important;
    }}
    .stApp button[kind="secondary"]:disabled,
    .stApp button[kind="secondary"]:disabled p {{
        color: {t['text_muted']} !important;
        background-color: {t['bg_frame']} !important;
    }}

    /* Radios */
    .stApp [data-testid="stRadioOption"] p {{
        color: {t['text_primary']} !important;
    }}
    /* Unchecked radio: outer ring + inner dot both use the dark canvas colour */
    .stApp [data-testid="stRadioOption"]:not([data-selected="true"]) > div > div:first-child {{
        background-color: #C3C8D1 !important;
    }}
    .stApp [data-testid="stRadioOption"]:not([data-selected="true"]) > div > div:first-child > div {{
        background-color: {t['surface']} !important;
    }}

    /* Element toolbars (fullscreen / download), progress bars */
    .stApp [data-testid="stElementToolbarButtonContainer"] {{
        background-color: {t['surface']} !important;
        border: 1px solid {t['border']} !important;
    }}
    .stApp [data-testid="stElementToolbar"] svg {{
        color: {t['text_secondary']} !important;
    }}
    .stApp [data-testid="stProgressBarTrack"] {{
        background-color: #E4E7EC !important;
    }}

    /* Code blocks & inline code */
    .stApp [data-testid="stCode"] pre,
    .stApp [data-testid="stCode"] code {{
        background-color: #F3F4F6 !important;
        color: {t['text_primary']} !important;
    }}
    .stApp [data-testid="stCode"] span {{
        color: {t['text_primary']} !important;
    }}
    .stApp [data-testid="stMarkdownContainer"] code {{
        background-color: #F1F3F5 !important;
        color: {t['badge_observed_text']} !important;
    }}

    /* Dataframes: the grid is canvas-drawn from the dark JS theme, so invert it hue-preservingly */
    .stApp [data-testid="stDataFrameResizable"] {{
        filter: invert(1) hue-rotate(180deg) !important;
    }}
    """
