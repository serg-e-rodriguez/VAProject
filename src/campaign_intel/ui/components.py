"""
Small UI building blocks: KPI tiles, section headers, callouts, ad cards, page header.
All text passed in is escaped; '$' is HTML-encoded so Streamlit never reads it as LaTeX.
"""

from __future__ import annotations

import html
from typing import Literal

import streamlit as st

Tone = Literal["neutral", "good", "bad", "dem", "rep"]
# Blue and red mean Democrats and Republicans, nothing else. "good" / "bad" (a judgement, not a party) stay neutral.
_PARTY_CLS = {"dem": "dem", "rep": "rep"}


def party_tone(margin: float) -> Tone:
    """Tone for a D−R number: blue when Democrats lead, red when Republicans do."""
    return "dem" if margin > 0 else "rep" if margin < 0 else "neutral"


def _md(s: str) -> None:
    st.markdown(s.replace("$", "&#36;"), unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "") -> None:
    sub = f"<div class='page-sub'>{html.escape(subtitle)}</div>" if subtitle else ""
    _md(f"<div class='page-head'><h1>{html.escape(title)}</h1>{sub}</div>")


def kpi(label: str, value: str, sub: str = "", tone: Tone = "neutral", help: str = "") -> None:
    """A KPI tile. `tone` colours the value only for party information: dem = blue, rep = red."""
    cls = _PARTY_CLS.get(tone, "")
    tip = f" title='{html.escape(help)}'" if help else ""
    sub_html = f"<div class='kpi-sub'>{html.escape(sub)}</div>" if sub else ""
    _md(f"<div class='kpi'{tip}><div class='kpi-label'>{html.escape(label)}</div>"
        f"<div class='kpi-value {cls}'>{html.escape(value)}</div>{sub_html}</div>")


def kpi_vs(label: str, dem: str, gop: str, sub: str = "") -> None:
    """KPI tile with the Democratic number in blue and the Republican number in red."""
    sub_html = f"<div class='kpi-sub'>{html.escape(sub)}</div>" if sub else ""
    _md(f"<div class='kpi'><div class='kpi-label'>{html.escape(label)}</div><div class='kpi-value'>"
        f"<span style='color:var(--dem)'>{html.escape(dem)}</span> <span style='font-size:16px;"
        f"color:var(--text-muted)'>vs</span> <span style='color:var(--rep)'>{html.escape(gop)}</span></div>{sub_html}</div>")


def no_data(what: str, detail: str = "") -> None:
    """Marks a section that has nothing in the selected timeframe (instead of an empty chart or $0)."""
    d = f" {html.escape(detail)}" if detail else ""
    _md(f"<div class='nodata'><span class='nodata-tag'>No data found</span>{html.escape(what)}{d}</div>")


def timeframe_banner(race: str, sources: tuple[str, ...] = ("google", "meta")) -> dict:
    """One line under the page header when the timeframe holds no (or only some) ad data. Returns the coverage."""
    from campaign_intel.data.loaders import coverage, timeframe_label

    c = coverage(race)
    names = {"google": "Google ads (BigQuery)", "meta": "Meta Ad Library"}
    missing = [names[x] for x in sources if not c[x]["has_data"]]
    if missing:
        what = " and ".join(missing)
        rest = ("Ad sections below are marked; election and voter data are not affected."
                if len(missing) == len(sources) else "Sections that need them are marked.")
        callout(f"No data found for {what} in {timeframe_label()}",
                f"{rest} Change the timeframe in the sidebar to see more.")
    return c


def pct(x: float, signed: bool = False) -> str:
    """'45%' (or '+3 pts'), or '—' when there is nothing to divide."""
    import math

    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    return f"{x:+.0f} pts" if signed else f"{x:.0%}"


def section(title: str, subtitle: str = "") -> None:
    sub = f"<div class='sec-sub'>{html.escape(subtitle)}</div>" if subtitle else ""
    _md(f"<div class='sec'><div class='sec-title'>{html.escape(title)}</div>{sub}</div>")


def source(text: str) -> None:
    _md(f"<div class='source'>{html.escape(text)}</div>")


def callout(title: str, body: str = "", tone: Tone = "neutral") -> None:
    cls = _PARTY_CLS.get(tone, "")
    b = f"<div class='callout-body'>{html.escape(body)}</div>" if body else ""
    _md(f"<div class='callout {cls}'><div class='callout-title'>{html.escape(title)}</div>{b}</div>")


def bullets(items: list[str]) -> None:
    lis = "".join(f"<li>{html.escape(i)}</li>" for i in items)
    _md(f"<ul class='why'>{lis}</ul>")


def pill(text: str, tone: Tone = "neutral") -> str:
    cls = _PARTY_CLS.get(tone, "neutral")
    return f"<span class='pill {cls}'>{html.escape(text)}</span>"


def ad_card(advertiser: str, date: str, body: str, spend: str, platform: str, url: str,
            audience: str | None = None, themes: list[str] | None = None) -> None:
    import re

    body = re.sub(r"\n\s*\n+", "\n", body.strip()) if body else ""
    if not body:
        body = "Video / image ad — open it in the ad library to view the creative."
    if len(body) > 260:
        body = body[:257].rsplit(" ", 1)[0] + "…"
    # Built from Streamlit's own elements, not one raw-HTML block: on the deployed app the raw-HTML card (with an
    # <a target=_blank> inside) was dropped by the browser, leaving an empty space. Text is markdown-escaped.
    with st.container(border=True):
        st.markdown(f"**{_esc_md(advertiser)}**")
        st.caption(f"{_esc_md(platform)} · {_esc_md(date)}")
        st.markdown(_esc_md(body))
        if themes:
            st.caption(" · ".join(_esc_md(t).upper() for t in themes[:3]))
        st.caption(f"Spend **{_esc_md(spend)}**" + (f" · Mostly reached: **{_esc_md(audience)}**" if audience else ""))
        if url:
            st.link_button(f"Open in {platform} library ↗", url)


_MD_SPECIAL = set("\\`*_{}[]()<>#+-.!|~$:")


def _esc_md(text: str) -> str:
    """Escape markdown, emoji-shortcode and LaTeX characters so ad text shows exactly as written."""
    return "".join("\\" + c if c in _MD_SPECIAL else c for c in " ".join(str(text).split()))


def chart(c, **kwargs):
    """Render an Altair chart with the app's own Altair theme (Streamlit's theme would override it and
    let a top legend squash charts with a categorical axis)."""
    return st.altair_chart(c, width="stretch", theme=None, **kwargs)
