"""
Small UI building blocks: KPI tiles, section headers, callouts, ad cards, page header.
All text passed in is escaped; '$' is HTML-encoded so Streamlit never reads it as LaTeX.
"""

from __future__ import annotations

import html
from typing import Literal

import streamlit as st

Tone = Literal["neutral", "good", "bad", "dem", "rep"]


def _md(s: str) -> None:
    st.markdown(s.replace("$", "&#36;"), unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "") -> None:
    sub = f"<div class='page-sub'>{html.escape(subtitle)}</div>" if subtitle else ""
    _md(f"<div class='page-head'><h1>{html.escape(title)}</h1>{sub}</div>")


def kpi(label: str, value: str, sub: str = "", tone: Tone = "neutral", help: str = "") -> None:
    """A KPI tile. `tone` colours the value: good/dem = blue, bad/rep = red."""
    cls = {"good": "dem", "dem": "dem", "bad": "rep", "rep": "rep"}.get(tone, "")
    tip = f" title='{html.escape(help)}'" if help else ""
    sub_html = f"<div class='kpi-sub'>{html.escape(sub)}</div>" if sub else ""
    _md(f"<div class='kpi'{tip}><div class='kpi-label'>{html.escape(label)}</div>"
        f"<div class='kpi-value {cls}'>{html.escape(value)}</div>{sub_html}</div>")


def section(title: str, subtitle: str = "") -> None:
    sub = f"<div class='sec-sub'>{html.escape(subtitle)}</div>" if subtitle else ""
    _md(f"<div class='sec'><div class='sec-title'>{html.escape(title)}</div>{sub}</div>")


def source(text: str) -> None:
    _md(f"<div class='source'>{html.escape(text)}</div>")


def callout(title: str, body: str = "", tone: Tone = "neutral") -> None:
    cls = {"good": "dem", "dem": "dem", "bad": "rep", "rep": "rep"}.get(tone, "")
    b = f"<div class='callout-body'>{html.escape(body)}</div>" if body else ""
    _md(f"<div class='callout {cls}'><div class='callout-title'>{html.escape(title)}</div>{b}</div>")


def bullets(items: list[str]) -> None:
    lis = "".join(f"<li>{html.escape(i)}</li>" for i in items)
    _md(f"<ul class='why'>{lis}</ul>")


def pill(text: str, tone: Tone = "neutral") -> str:
    cls = {"good": "dem", "dem": "dem", "bad": "rep", "rep": "rep"}.get(tone, "neutral")
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
