"""
Reusable UI components matching UI_Design.md specifications.
Enforces data fidelity badges, styled KPI cards, and chart card wrappers.
"""

from typing import Literal

import altair as alt
import pandas as pd
import streamlit as st

from campaign_intel.ui.styles import get_tokens

FidelityType = Literal["observed", "aggregated", "modeled", "sample"]


def fidelity_badge(fidelity: FidelityType) -> str:
    """
    Returns HTML for a data-fidelity badge per UI spec §3.1.
    """
    tooltips = {
        "observed": "Directly measured empirical data from platform transparency APIs or certified election returns.",
        "aggregated": "Statistically rolled up from precinct records or respondent survey files without modeled extrapolation.",
        "modeled": "Estimated using registered voter shares, demographic weighting, or simulation models.",
        "sample": "Calibrated demonstration dataset — live transparency API feed unavailable."
    }
    f_clean = fidelity.lower().strip()
    tip = tooltips.get(f_clean, "Data fidelity status")
    display_text = f_clean.capitalize() if f_clean != "sample" else "Sample Data"
    return f'<span class="fidelity-badge badge-{f_clean}" title="{tip}">{display_text}</span>'


def kpi_card(
    label: str,
    value: str,
    delta: str | None = None,
    good_direction: Literal["up", "down", "neutral"] = "up",
    fidelity: FidelityType = None,  # Mandatory
    band: str | None = None,
    spark_data: list[float] | None = None,
):
    """
    Renders a KPI card per UI_Design.md §4.3.
    Raises TypeError if fidelity is not provided.
    """
    if fidelity is None:
        raise TypeError("fidelity is a REQUIRED argument for kpi_card (observed | aggregated | modeled | sample).")

    theme = st.session_state.get("theme", "light")
    t = get_tokens(theme)

    # Determine delta pill style
    delta_html = ""
    if delta:
        delta_str = str(delta).strip()
        is_positive = delta_str.startswith("+") or (not delta_str.startswith("-") and "▲" in delta_str)
        is_negative = delta_str.startswith("-") or "▼" in delta_str

        if good_direction == "neutral":
            pill_bg, pill_fg = t["pill_neutral_bg"], t["pill_neutral_text"]
        elif (good_direction == "up" and is_positive) or (good_direction == "down" and is_negative):
            # Good for us
            pill_bg, pill_fg = t["pill_up_bg"], t["pill_up_text"]
        else:
            # Bad for us
            pill_bg, pill_fg = t["pill_down_bg"], t["pill_down_text"]

        delta_html = f'<span class="kpi-delta-pill" style="background-color: {pill_bg}; color: {pill_fg};">{delta}</span>'

    badge_html = fidelity_badge(fidelity)
    band_html = f'<div style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">{band}</div>' if band else ""

    card_html = f"""
    <div class="kpi-card">
        <div class="kpi-header">
            <span class="kpi-label">{label}</span>
            {badge_html}
        </div>
        <div class="kpi-main">
            <span class="kpi-value">{value}</span>
            {delta_html}
        </div>
        {band_html}
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

    # Optional mini sparkline below card
    if spark_data and len(spark_data) >= 3:
        df_spark = pd.DataFrame({
            "idx": list(range(len(spark_data))),
            "val": spark_data,
            "is_last": [1 if i == len(spark_data) - 1 else 0 for i in range(len(spark_data))]
        })
        chart = alt.Chart(df_spark).mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(
            x=alt.X("idx:O", axis=None),
            y=alt.Y("val:Q", axis=None),
            color=alt.condition(
                alt.datum.is_last == 1,
                alt.value(t["accent"]),
                alt.value("#E5E7EB" if theme == "light" else "#262B36")
            )
        ).properties(height=24, width="container")
        st.altair_chart(chart, use_container_width=True)


def chart_card_header(
    title: str,
    subtitle: str | None = None,
    fidelity: FidelityType = None,  # Mandatory
):
    """
    Renders chart card header per §4.4.
    """
    if fidelity is None:
        raise TypeError("fidelity is a REQUIRED argument for chart_card_header (observed | aggregated | modeled | sample).")

    badge_html = fidelity_badge(fidelity)
    sub_html = f'<div style="font-size: 12px; color: var(--text-secondary); margin-top: 2px;">{subtitle}</div>' if subtitle else ""

    header_html = f"""
    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
        <div>
            <h4 style="margin: 0; font-size: 16px; font-weight: 700; color: var(--text-primary);">{title}</h4>
            {sub_html}
        </div>
        <div>
            {badge_html}
        </div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)


def sample_banner():
    """
    Renders the full-width sample data alert banner per §7.
    """
    html = """
    <div style="background-color: #FDECEC; border-left: 4px solid #B42318; color: #912018; padding: 12px 18px; border-radius: 8px; margin-bottom: 20px; font-size: 13px; font-weight: 600;">
        ⚠️ <strong>Notice:</strong> Showing calibrated <strong>SAMPLE / DEMO</strong> data — live transparency feeds or warehouse tables are currently in demonstration fallback mode.
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def model_ribbon():
    """
    Renders the 'Model, not forecast' ribbon under the War Room title per §6.5.
    """
    html = """
    <div class="model-ribbon">
        <span>🛡️ <strong>Model, not forecast</strong> — Simulates marginal response from media saturation curves and turn-out assumptions. Not a poll-based predictive forecast.</span>
        <span style="font-size: 12px; opacity: 0.85;">Assumption-driven · Vectorized Monte Carlo</span>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def creative_card(
    advertiser: str,
    date_str: str,
    body: str,
    spend_band: str,
    top_demo: str,
    themes: list[str],
    url: str,
    platform: str = "Meta"
):
    """
    Renders an inspectable political ad creative card with link button per §4.6.
    """
    theme = st.session_state.get("theme", "light")
    t = get_tokens(theme)

    theme_pills = "".join(
        f'<span style="background-color: {t["accent_soft"]}; color: {t["accent"]}; font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 999px; margin-right: 4px;">{th.upper()}</span>'
        for th in themes[:3]
    )

    with st.container(border=True):
        col1, col2 = st.columns([8, 4])
        with col1:
            st.markdown(f"**{advertiser}** · <span style='color: var(--text-secondary); font-size: 12px;'>{date_str}</span>", unsafe_allow_html=True)
            truncated_body = (body[:210] + "...") if len(body) > 210 else body
            st.markdown(f"<p style='font-size: 13px; line-height: 1.5; color: var(--text-primary); margin: 6px 0;'>{truncated_body}</p>", unsafe_allow_html=True)
            st.markdown(f"<div>{theme_pills}</div>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"<div style='text-align: right; font-size: 12px; color: var(--text-secondary);'>Spend: <strong style='color: var(--text-primary);'>{spend_band}</strong></div>", unsafe_allow_html=True)
            st.markdown(f"<div style='text-align: right; font-size: 11px; color: var(--text-muted); margin-bottom: 8px;'>Demo: {top_demo}</div>", unsafe_allow_html=True)
            st.link_button(f"Open in {platform} Library", url, use_container_width=True)
