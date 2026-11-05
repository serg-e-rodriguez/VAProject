"""
Design tokens and dynamic CSS injection for Light and Dark modes per UI_Design.md.
Provides authoritative styling, typography, component resets, and dark mode themes.
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
    """
    Injects custom CSS adhering strictly to UI_Design.md tokens.
    Guarantees Material Symbols icons render as glyphs without text collision.
    """
    t = get_tokens(theme)
    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Mulish:wght@400;500;600;700;800&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');

    :root {{
        --bg-canvas: {t['bg_canvas']};
        --bg-frame: {t['bg_frame']};
        --surface: {t['surface']};
        --surface-raised: {t['surface_raised']};
        --border: {t['border']};
        --gridline: {t['gridline']};
        --text-primary: {t['text_primary']};
        --text-secondary: {t['text_secondary']};
        --text-muted: {t['text_muted']};
        --accent: {t['accent']};
        --accent-soft: {t['accent_soft']};
        --dem: {t['dem']};
        --dem-soft: {t['dem_soft']};
        --rep: {t['rep']};
        --rep-soft: {t['rep_soft']};
        --swing: {t['swing']};
        --neutral-series: {t['neutral_series']};
        --radius-card: {t['radius_card']};
        --radius-control: {t['radius_control']};
        --radius-pill: {t['radius_pill']};
        --shadow-card: {t['shadow_card']};
        --shadow-pop: {t['shadow_pop']};
    }}

    /* Global Typography - NEVER override font-family with [class*="st-"] */
    html, body, .stApp, p, label, h1, h2, h3, h4, h5, h6, input, textarea, select {{
        font-family: 'Mulish', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    }}

    /* CRITICAL: Explicitly isolate and protect Material Symbols & Icons font family */
    [data-testid="stIconMaterial"],
    [data-testid="stIcon"],
    .material-symbols-rounded,
    .material-symbols-outlined,
    .material-icons,
    [class*="material-symbols"],
    [class*="material-icons"],
    span[data-testid="stIconMaterial"] {{
        font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons' !important;
        font-weight: normal !important;
        font-style: normal !important;
        font-size: 20px !important;
        line-height: 1 !important;
        letter-spacing: normal !important;
        text-transform: none !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        white-space: nowrap !important;
        word-wrap: normal !important;
        direction: ltr !important;
        -webkit-font-feature-settings: 'liga' 1 !important;
        font-feature-settings: 'liga' 1 !important;
        -webkit-font-smoothing: antialiased !important;
        vertical-align: middle !important;
    }}

    /* Application Canvas & Dark Frame */
    .stApp {{
        background-color: var(--bg-frame) !important;
        color: var(--text-primary) !important;
    }}

    header[data-testid="stHeader"] {{
        background-color: var(--bg-frame) !important;
    }}

    /* Limit maximum container width to 1440px per UI design spec §2 */
    .main .block-container {{
        max-width: 1440px !important;
        padding-top: 1.2rem !important;
        padding-bottom: 2.5rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }}

    /* Sidebar Styling & Clean Alignment */
    section[data-testid="stSidebar"] {{
        background-color: var(--surface) !important;
        border-right: 1px solid var(--border) !important;
    }}

    section[data-testid="stSidebar"] .stMarkdown {{
        color: var(--text-primary) !important;
    }}

    /* Sidebar Navigation Links Alignment */
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] li a {{
        display: flex !important;
        align-items: center !important;
        gap: 12px !important;
        padding: 8px 14px !important;
        border-radius: var(--radius-control) !important;
        color: var(--text-primary) !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        margin-bottom: 4px !important;
        text-decoration: none !important;
        transition: background-color 0.15s ease !important;
    }}

    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] li a:hover {{
        background-color: var(--accent-soft) !important;
        color: var(--accent) !important;
    }}

    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] li a[aria-current="page"] {{
        background-color: var(--accent) !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }}

    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] li a[aria-current="page"] [data-testid="stIconMaterial"] {{
        color: #FFFFFF !important;
    }}

    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] span[data-testid="stIconMaterial"] {{
        min-width: 24px !important;
        width: 24px !important;
        height: 24px !important;
        flex-shrink: 0 !important;
        overflow: hidden !important;
        margin-right: 6px !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
    }}

    /* Modern Card Container */
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius-card) !important;
        box-shadow: var(--shadow-card) !important;
        padding: 1.25rem !important;
        margin-bottom: 1rem !important;
        color: var(--text-primary) !important;
    }}

    /* KPI Value styling with tabular-nums */
    .kpi-card {{
        background-color: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius-card);
        padding: 16px 20px;
        box-shadow: var(--shadow-card);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-height: 110px;
    }}

    .kpi-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }}

    .kpi-label {{
        font-size: 13px;
        font-weight: 600;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}

    .kpi-main {{
        display: flex;
        flex-wrap: wrap;
        align-items: baseline;
        gap: 4px 8px;
    }}

    .kpi-value {{
        font-size: 24px;
        font-weight: 800;
        color: var(--text-primary);
        font-variant-numeric: tabular-nums;
        line-height: 1.2;
    }}

    .kpi-delta-pill {{
        font-size: 11px;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: var(--radius-pill);
        display: inline-flex;
        align-items: center;
    }}

    .kpi-footer {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 6px;
        font-size: 12px;
        color: var(--text-muted);
    }}

    /* Fidelity Badges */
    .fidelity-badge {{
        font-size: 10px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        padding: 2px 7px;
        border-radius: var(--radius-pill);
        display: inline-block;
    }}

    .badge-observed {{
        background-color: {t['badge_observed_bg']};
        color: {t['badge_observed_text']};
    }}

    .badge-aggregated {{
        background-color: {t['badge_aggregated_bg']};
        color: {t['badge_aggregated_text']};
    }}

    .badge-modeled {{
        background-color: {t['badge_modeled_bg']};
        color: {t['badge_modeled_text']};
    }}

    .badge-sample {{
        background-color: {t['badge_sample_bg']};
        color: {t['badge_sample_text']};
    }}

    /* Model Ribbon */
    .topbar-title {{ margin: 0; font-size: 17px; font-weight: 800; color: var(--text-primary);
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .fresh-chip {{ display: inline-block; font-size: 11px; font-weight: 600; color: var(--text-secondary);
        background: var(--accent-soft); border: 1px solid var(--border); border-radius: 999px;
        padding: 6px 10px; white-space: nowrap; cursor: help; }}
    .fresh-chip.stale {{ background: rgba(224,72,72,0.12); }}
    .insight {{ border-left: 4px solid var(--accent); background: var(--accent-soft); padding: 10px 14px;
        border-radius: 8px; margin-bottom: 10px; font-size: 13px; color: var(--text-primary); }}
    .insight.dem {{ border-left-color: var(--dem); background: rgba(91,141,239,0.10); }}
    .insight.rep {{ border-left-color: var(--rep); background: rgba(240,99,99,0.10); }}
    .insight b {{ font-weight: 700; }}
    .insight .sub {{ display: block; color: var(--text-secondary); font-size: 12px; margin-top: 3px; }}
    .model-ribbon {{
        background-color: rgba(34, 160, 107, 0.12);
        border: 1px solid rgba(43, 181, 122, 0.35);
        color: var(--accent);
        border-radius: var(--radius-control);
        padding: 8px 16px;
        font-size: 13px;
        font-weight: 600;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }}

    /* Vega-Lite Tooltip restyling per §4.5 */
    #vg-tooltip-element {{
        background-color: var(--surface-raised) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
        color: var(--text-primary) !important;
        box-shadow: var(--shadow-pop) !important;
        font-family: 'Mulish', sans-serif !important;
        font-size: 12px !important;
        padding: 8px 12px !important;
        z-index: 10000 !important;
    }}

    #vg-tooltip-element table tr td.key {{
        color: var(--text-secondary) !important;
        font-weight: 500 !important;
    }}

    #vg-tooltip-element table tr td.value {{
        color: var(--text-primary) !important;
        font-weight: 700 !important;
    }}

    /* Custom Top Bar */
    .topbar-container {{
        background-color: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius-card);
        padding: 12px 20px;
        margin-bottom: 20px;
        box-shadow: var(--shadow-card);
        display: flex;
        align-items: center;
        justify-content: space-between;
    }}

    /* Button and Popover Sizing Fixes */
    button[data-testid="stPopoverButton"] {{
        border-radius: var(--radius-control) !important;
        border: 1px solid var(--border) !important;
        background-color: var(--surface) !important;
        color: var(--text-primary) !important;
        min-height: 38px !important;
        max-height: 40px !important;
        height: 40px !important;
        padding: 0 10px !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 6px !important;
        overflow: hidden !important;
        box-sizing: border-box !important;
        white-space: nowrap !important;
    }}

    button[data-testid="stPopoverButton"] p,
    button[data-testid="stPopoverButton"] span {{
        font-size: 13px !important;
        font-weight: 600 !important;
        margin: 0 !important;
        white-space: nowrap !important;
    }}

    button[data-testid="stPopoverButton"] [data-testid="stIconMaterial"],
    button[data-testid="stPopoverButton"] svg {{
        font-size: 16px !important;
        width: 16px !important;
        height: 16px !important;
        line-height: 1 !important;
        flex-shrink: 0 !important;
    }}

    /* Popover Content Styling */
    div[data-testid="stPopoverBody"] {{
        background-color: var(--surface-raised) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius-card) !important;
        color: var(--text-primary) !important;
        box-shadow: var(--shadow-pop) !important;
    }}

    /* Top right button sizing */
    div[data-testid="stButton"] > button {{
        border-radius: var(--radius-control) !important;
        height: 40px !important;
        padding: 0 12px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        box-sizing: border-box !important;
        white-space: nowrap !important;
    }}

    button[kind="primary"] {{
        background-color: var(--accent) !important;
        border-radius: var(--radius-control) !important;
        border: none !important;
        font-weight: 700 !important;
        color: #FFFFFF !important;
    }}

    /* Dark Mode Dropdowns, Inputs, and Segmented Controls */
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div,
    input, select, textarea {{
        background-color: var(--surface) !important;
        border-color: var(--border) !important;
        color: var(--text-primary) !important;
        border-radius: var(--radius-control) !important;
    }}

    div[data-testid="stSegmentedControl"] {{
        background-color: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius-control) !important;
    }}

    /* Data table header & styling */
    div[data-testid="stDataFrame"],
    div[data-testid="stDataEditor"] {{
        border: 1px solid var(--border) !important;
        border-radius: var(--radius-control) !important;
        background-color: var(--surface) !important;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
