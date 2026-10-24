"""
Altair light and dark theme registrations matching UI_Design.md tokens.
"""

import altair as alt

from campaign_intel.ui.styles import get_tokens


def create_altair_theme(theme_name: str = "light") -> dict:
    t = get_tokens(theme_name)
    return {
        "config": {
            "font": "Mulish, sans-serif",
            "background": "transparent",
            "view": {
                "stroke": "transparent"
            },
            "axis": {
                "domain": False,
                "domainColor": "transparent",
                "grid": True,
                "gridColor": t["gridline"],
                "gridDash": [3, 3],
                "labelColor": t["text_secondary"],
                "labelFont": "Mulish, sans-serif",
                "labelFontSize": 11,
                "titleColor": t["text_primary"],
                "titleFont": "Mulish, sans-serif",
                "titleFontSize": 12,
                "titleFontWeight": 600,
                "tickColor": "transparent"
            },
            "legend": {
                "labelColor": t["text_primary"],
                "labelFont": "Mulish, sans-serif",
                "labelFontSize": 11,
                "titleColor": t["text_secondary"],
                "titleFont": "Mulish, sans-serif",
                "titleFontSize": 12,
                "titleFontWeight": 600,
                "orient": "top",
                "symbolType": "circle"
            },
            "header": {
                "labelColor": t["text_primary"],
                "labelFont": "Mulish, sans-serif",
                "titleColor": t["text_primary"],
                "titleFont": "Mulish, sans-serif"
            },
            "range": {
                "category": [
                    t["dem"],
                    t["rep"],
                    t["accent"],
                    t["swing"],
                    t["neutral_series"],
                    "#38BDF8",
                    "#FB923C",
                    "#A855F7"
                ],
                "diverging": [
                    t["rep"],
                    "#F7F7F7" if theme_name == "light" else "#2A2F3A",
                    t["dem"]
                ]
            }
        }
    }


def register_themes():
    alt.themes.register("campaign_light", lambda: create_altair_theme("light"))
    alt.themes.register("campaign_dark", lambda: create_altair_theme("dark"))


def enable(theme: str = "light"):
    register_themes()
    target = f"campaign_{theme.lower()}"
    if target in alt.themes.names():
        alt.themes.enable(target)
    else:
        alt.themes.enable("campaign_light")
