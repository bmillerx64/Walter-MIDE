"""GS288: refine FMP catalyst filtering without broadening trading semantics."""

from __future__ import annotations

import re


_CAPITAL_INJECTION_PATTERNS = (
    re.compile(
        r"\b(receives?|secures?|lands?|obtains?|awarded)\b.{0,80}"
        r"\b(investment|funding|capital infusion|grant)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(investment|funding|capital infusion|grant)\b.{0,60}"
        r"\b(from|by)\b",
        re.IGNORECASE,
    ),
)


def install() -> None:
    from . import news

    if getattr(news, "_gs288_installed", False):
        return

    original = news.classify_headline

    def classify_headline(headline: str):
        score, flags = original(headline)
        text = str(headline or "")

        # Preserve every existing material positive/negative classification.
        # The refinement only rescues otherwise-neutral capital-injection
        # headlines such as "receives $30M investment" that the prior keyword
        # table scored at zero. Financing/offering headlines remain governed by
        # the existing negative dilution terms and are never upgraded here.
        if abs(float(score or 0)) < news.MATERIAL_CATALYST_SCORE:
            lowered = text.casefold()
            if not any(term in lowered for term in (
                "offering", "registered direct", "at-the-market", " atm ",
                "warrant inducement", "shelf registration",
            )):
                if any(pattern.search(text) for pattern in _CAPITAL_INJECTION_PATTERNS):
                    score = news.MATERIAL_CATALYST_SCORE + 2
                    flags = [*flags, "capital_injection"]

        return score, flags

    news.classify_headline = classify_headline
    news._gs288_installed = True
