"""
Theme classification of ad text (PROJECT_DESIGN.md §6.2): keyword pass from
seeds/theme_keywords.yaml, matched on word boundaries. Fundraising and GOTV are tagged so
they can be excluded from persuasion-message analysis.
"""

from __future__ import annotations

import re
from functools import lru_cache

import yaml

from campaign_intel.config import SEEDS_DIR

FUNDRAISING_RE = re.compile(r"actblue|winred|anedot|\bchip in\b|\bdonate\b|split a donation|\bcontribut", re.IGNORECASE)
GOTV_RE = re.compile(r"\bvote early\b|\bearly voting\b|one-stop|absentee ballot|polling place|\bvote by\b|"
                     r"election day|make a plan to vote|iwillvote|find your (?:polling|precinct)", re.IGNORECASE)
NON_MESSAGE_THEMES = {"fundraising", "gotv", "general"}  # "general" = no keyword matched


@lru_cache(maxsize=1)
def _seed() -> dict:
    with open(SEEDS_DIR / "theme_keywords.yaml") as f:
        return yaml.safe_load(f)


def theme_labels() -> dict[str, str]:
    return dict(_seed().get("theme_labels", {}))


@lru_cache(maxsize=1)
def _patterns() -> dict[str, list[re.Pattern]]:
    out = {}
    for theme, kws in _seed().get("theme_keywords", {}).items():
        pats = []
        for kw in kws:
            flags = 0 if (kw.isupper() and len(kw) > 1) else re.IGNORECASE
            pats.append(re.compile(rf"(?<![\w]){re.escape(kw)}(?![\w])", flags))
        out[theme] = pats
    return out


def classify_text(text: str | None) -> list[str]:
    """Matched theme keys for one ad text; ['general'] when nothing matches."""
    if not text or not isinstance(text, str):
        return ["general"]
    matched = [t for t, pats in _patterns().items() if any(p.search(text) for p in pats)]
    return matched or ["general"]


def is_fundraising(text: str | None, link: str | None = "") -> bool:
    return bool(FUNDRAISING_RE.search(f"{text or ''} {link or ''}"))


def is_gotv(text: str | None) -> bool:
    return bool(GOTV_RE.search(text or ""))
