"""
Theme classification and fundraising tag detection from ad text per §6.2.
"""

import re

import yaml

from campaign_intel.config import SEEDS_DIR


def load_theme_keywords() -> dict[str, list[str]]:
    theme_file = SEEDS_DIR / "theme_keywords.yaml"
    if not theme_file.exists():
        return {}
    with open(theme_file, "r") as f:
        data = yaml.safe_load(f)
        return data.get("theme_keywords", {})


THEME_KEYWORDS = load_theme_keywords()

FUNDRAISING_PATTERNS = re.compile(r"actblue|winred|chip in|donate|split a donation|end of quarter|contribution", re.IGNORECASE)
GOTV_PATTERNS = re.compile(r"vote early|one-stop|absentee ballot|election day|polling place|iwillvote", re.IGNORECASE)


def classify_text(text: str) -> list[str]:
    """
    Returns list of matched themes for a given ad creative text.
    """
    if not text or not isinstance(text, str):
        return ["other"]

    text_lower = text.lower()
    matched = []
    for theme, keywords in THEME_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                matched.append(theme)
                break

    if not matched:
        matched.append("general")
    return matched


def is_fundraising(text: str, link_url: str = "") -> bool:
    """
    Detects whether an ad creative is primary fundraising.
    """
    combined = f"{text} {link_url}".lower()
    return bool(FUNDRAISING_PATTERNS.search(combined))


def is_gotv(text: str) -> bool:
    """
    Detects whether an ad creative is voting info / GOTV.
    """
    return bool(GOTV_PATTERNS.search(text))
