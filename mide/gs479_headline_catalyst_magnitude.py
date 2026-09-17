"""GS479: extract stated economic scale from material catalyst headlines.

Sep. 17 PAAI validation exposed a semantic compression problem. Walter already knows
that words such as ``agreement`` and ``contract`` are material catalyst terms, but a
plain agreement and a headline stating a 10-year, $1 billion agreement currently land
in essentially the same news bucket. That loses useful operator context.

GS479 adds deterministic headline facts only. It extracts disclosed dollar amounts and
multi-year duration from the headline, builds a factual scale band, and attaches that
context to the existing GS315 news-intelligence metadata and analyzed candidate record.
The operator Catalyst panel can then say, for example, ``$1.0B stated · 10-year term``.

This module intentionally does NOT infer the company's market capitalization, revenue,
probability of closing, or valuation impact from a headline. Relative company scale is
reported as unavailable unless another future evidence source supplies it. It does not
change catalyst_score, discovery eligibility, scanner scores, ranking, qualification,
readiness, anti-chase, alert authority, execution or orders.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
import re
from typing import Any


AUTHORITY = "CATALYST_CONTEXT_ONLY"
_OWNER_ANALYZE = "_walter_gs479_headline_magnitude_analyze_owner"
_OWNER_CLASSIFY = "_walter_gs479_headline_magnitude_classify_owner"
_OWNER_WHY = "_walter_gs479_headline_magnitude_why_owner"

_MONEY_RE = re.compile(
    r"(?<![A-Z0-9])(?:US\s*)?\$\s*"
    r"(?P<value>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>trillion|billion|million|bln|bn|mln|mm|b|m)?\b",
    re.IGNORECASE,
)
_WORD_MONEY_RE = re.compile(
    r"\b(?P<value>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>trillion|billion|million|bln|bn|mln|mm)\s*"
    r"(?:dollars?|usd)\b",
    re.IGNORECASE,
)
_DURATION_RE = re.compile(
    r"\b(?P<value>\d+(?:\.\d+)?)\s*(?:-|\s)?\s*(?:years?|yrs?)\b",
    re.IGNORECASE,
)
_CONTRACT_TERMS = (
    "agreement",
    "contract",
    "purchase order",
    "award",
    "license",
    "licensing",
    "partnership",
    "collaboration",
)

_UNIT_MULTIPLIER = {
    "": 1.0,
    "m": 1_000_000.0,
    "mm": 1_000_000.0,
    "mln": 1_000_000.0,
    "million": 1_000_000.0,
    "b": 1_000_000_000.0,
    "bn": 1_000_000_000.0,
    "bln": 1_000_000_000.0,
    "billion": 1_000_000_000.0,
    "trillion": 1_000_000_000_000.0,
}


def _money_value(match: re.Match) -> float | None:
    try:
        value = float(match.group("value"))
    except (TypeError, ValueError):
        return None
    unit = str(match.group("unit") or "").casefold()
    multiplier = _UNIT_MULTIPLIER.get(unit)
    if multiplier is None:
        return None
    return value * multiplier


def _dollar_amounts(headline: str) -> list[float]:
    text = str(headline or "")
    values = []
    spans = []
    for match in _MONEY_RE.finditer(text):
        amount = _money_value(match)
        if amount is not None and amount > 0:
            values.append(amount)
            spans.append(match.span())
    # Catch ``1 billion dollars`` only when it was not already captured by a $ form.
    for match in _WORD_MONEY_RE.finditer(text):
        if any(start <= match.start() < end for start, end in spans):
            continue
        amount = _money_value(match)
        if amount is not None and amount > 0:
            values.append(amount)
    return sorted(set(values), reverse=True)


def _duration_years(headline: str) -> float | None:
    values = []
    for match in _DURATION_RE.finditer(str(headline or "")):
        try:
            value = float(match.group("value"))
        except (TypeError, ValueError):
            continue
        if 0 < value <= 100:
            values.append(value)
    return max(values) if values else None


def _scale_band(largest: float | None) -> str:
    if largest is None:
        return "UNDISCLOSED"
    if largest >= 1_000_000_000:
        return "BILLION_PLUS"
    if largest >= 100_000_000:
        return "HUNDRED_MILLION_PLUS"
    if largest >= 10_000_000:
        return "TEN_MILLION_PLUS"
    if largest >= 1_000_000:
        return "MILLION_PLUS"
    return "DISCLOSED_UNDER_1M"


def _format_money(value: float | None) -> str | None:
    if value is None:
        return None
    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.2g}T"
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2g}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.3g}M"
    if value >= 1_000:
        return f"${value / 1_000:.3g}K"
    return f"${value:,.0f}"


def headline_magnitude_context(headline: str) -> dict:
    """Extract factual economic scale while explicitly withholding valuation inference."""
    text = " ".join(str(headline or "").split())
    normalized = text.casefold()
    amounts = _dollar_amounts(text)
    largest = amounts[0] if amounts else None
    years = _duration_years(text)
    contractual = any(term in normalized for term in _CONTRACT_TERMS)

    facts = []
    if largest is not None:
        facts.append(f"{_format_money(largest)} stated")
    if years is not None:
        years_text = f"{years:g}"
        facts.append(f"{years_text}-year term")
    summary = " · ".join(facts)

    return {
        "authority": AUTHORITY,
        "headline_scale_band": _scale_band(largest),
        "largest_stated_dollar_amount": largest,
        "stated_dollar_amounts": amounts,
        "stated_duration_years": years,
        "contractual_language": contractual,
        "summary": summary,
        "relative_company_scale": "NOT_EVALUATED_NO_COMPANY_BASELINE",
        "valuation_impact_inferred": False,
        "closing_probability_inferred": False,
        "catalyst_score_changed": False,
        "trading_authority_changed": False,
    }


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def _install_gs315_metadata() -> None:
    from . import gs315_news_intelligence as gs315

    current = gs315.classify_news_intelligence
    if getattr(current, _OWNER_CLASSIFY, False):
        return

    @wraps(current)
    def classify_with_magnitude(headline: str, **kwargs):
        result = dict(current(headline, **kwargs))
        result["catalyst_magnitude"] = headline_magnitude_context(headline)
        return result

    _inherit(classify_with_magnitude, current)
    classify_with_magnitude._gs479_headline_catalyst_magnitude = True
    classify_with_magnitude._gs479_original = current
    setattr(classify_with_magnitude, _OWNER_CLASSIFY, True)
    gs315.classify_news_intelligence = classify_with_magnitude


def _install_analyzed_records() -> None:
    from . import discovery

    current = discovery.analyze_candidates
    if getattr(current, _OWNER_ANALYZE, False):
        return

    @wraps(current)
    def analyze_with_catalyst_magnitude(client, candidates, news_index, discovery_reasons):
        records = current(client, candidates, news_index, discovery_reasons)
        enriched = []
        for record in records or []:
            headline = str(record.get("headline") or "").strip()
            if not headline:
                enriched.append(record)
                continue
            row = deepcopy(record)
            row["catalyst_magnitude"] = headline_magnitude_context(headline)
            enriched.append(row)
        diagnostics = getattr(client, "diagnostics", None)
        if isinstance(diagnostics, dict):
            diagnostics["gs479_headline_catalyst_magnitude"] = {
                "authority": AUTHORITY,
                "records_with_headline": sum(bool(r.get("headline")) for r in enriched),
                "records_with_disclosed_dollar_scale": sum(
                    bool((r.get("catalyst_magnitude") or {}).get("largest_stated_dollar_amount"))
                    for r in enriched
                ),
                "relative_company_scale_evaluated": False,
                "catalyst_score_changed": False,
                "trading_logic_changed": False,
            }
        return enriched

    _inherit(analyze_with_catalyst_magnitude, current)
    analyze_with_catalyst_magnitude._gs479_headline_catalyst_magnitude = True
    analyze_with_catalyst_magnitude._gs479_original = current
    setattr(analyze_with_catalyst_magnitude, _OWNER_ANALYZE, True)
    discovery.analyze_candidates = analyze_with_catalyst_magnitude


def _install_operator_presentation() -> None:
    from . import ui

    current = ui._why_sections
    if getattr(current, _OWNER_WHY, False):
        return

    @wraps(current)
    def why_sections_with_magnitude(record: dict):
        sections = dict(current(record))
        detail = record.get("catalyst_magnitude") or {}
        summary = str(detail.get("summary") or "").strip()
        if summary:
            existing = str(sections.get("Catalyst") or "").strip()
            if summary not in existing:
                sections["Catalyst"] = f"{existing} · {summary}" if existing else summary
        return sections

    _inherit(why_sections_with_magnitude, current)
    why_sections_with_magnitude._gs479_headline_catalyst_magnitude = True
    why_sections_with_magnitude._gs479_original = current
    setattr(why_sections_with_magnitude, _OWNER_WHY, True)
    ui._why_sections = why_sections_with_magnitude


def install() -> None:
    """Attach deterministic catalyst magnitude to GS315, records, and Catalyst display."""
    _install_gs315_metadata()
    _install_analyzed_records()
    _install_operator_presentation()
