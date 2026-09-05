"""GS315: classify news by trading usefulness without changing trading decisions.

The scanner already distinguishes material catalyst seeds from morning-mover
attention seeds.  This layer makes that distinction explicit and auditable by
classifying headline type, source quality, freshness, discovery value, and
catalyst value.  It is presentation/discovery metadata only: it does not change
price, float, participation, expansion, ranking, readiness, trigger, or execution
thresholds.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping

DIRECT_CATALYST = "DIRECT_CATALYST"
MORNING_MOVER = "MORNING_MOVER"
WATCHLIST_MENTION = "WATCHLIST_MENTION"
SECTOR_CONTEXT = "SECTOR_CONTEXT"
RECAP = "RECAP"
LEGAL_NOISE = "LEGAL_NOISE"
STALE = "STALE"
UNKNOWN = "UNKNOWN"

_HIGH = "HIGH"
_MEDIUM = "MEDIUM"
_LOW = "LOW"
_NONE = "NONE"

_DIRECT_TERMS = (
    "approval", "clearance", "authorization", "fda", "contract", "purchase order",
    "award", "partnership", "collaboration", "agreement", "selected", "patent",
    "license", "acquisition", "merger", "clinical", "trial results", "milestone",
    "raises guidance", "earnings beat", "investment", "funding",
)
_MOVER_TERMS = (
    "stocks moving premarket", "stocks moving pre-market", "stocks moving in",
    "premarket gainers", "pre-market gainers", "stocks on the move",
    "shares are trading higher", "stock is trading higher", "stocks are trading higher",
    "after-hours gainers", "after hours gainers",
)
_WATCHLIST_TERMS = (
    "stocks to watch", "investors radar", "investors' radar", "on investors radar",
    "on investors' radar", "penny stocks are on", "watch list", "watchlist",
)
_RECAP_TERMS = (
    "weekly report", "what happened at", "last week", "why is penny stock",
    "why penny stock", "why shares are up", "why stock is up", "here's what happened",
)
_LEGAL_TERMS = (
    "class action", "shareholder alert", "investor alert", "law firm reminds",
    "lead plaintiff", "securities fraud", "deadline", "lawsuit",
)
_SECTOR_TERMS = (
    "health care stocks", "healthcare stocks", "industrial stocks", "consumer stocks",
    "energy stocks", "biotech stocks", "crypto stocks", "technology stocks",
)


def _norm(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _source_quality(source: object, trusted_source: bool | None = None) -> str:
    if trusted_source is True:
        return "TRUSTED"
    text = _norm(source)
    trusted = (
        "reuters", "benzinga", "tipranks", "business wire", "globenewswire",
        "globe newswire", "pr newswire", "accesswire", "company press release",
    )
    return "TRUSTED" if any(term in text for term in trusted) else "UNVERIFIED"


def classify_news_intelligence(
    headline: str,
    *,
    source: str = "",
    age_minutes: float | None = None,
    catalyst_score: float = 0.0,
    trusted_source: bool | None = None,
) -> dict:
    """Return a stable, human-readable classification for one article/headline."""
    text = _norm(headline)
    source_quality = _source_quality(source, trusted_source)
    age = None if age_minutes is None else max(0.0, float(age_minutes))

    if age is not None and age > 360:
        article_type = STALE
    elif any(term in text for term in _LEGAL_TERMS):
        article_type = LEGAL_NOISE
    elif any(term in text for term in _RECAP_TERMS):
        article_type = RECAP
    elif abs(float(catalyst_score or 0)) >= 7 or any(term in text for term in _DIRECT_TERMS):
        article_type = DIRECT_CATALYST
    elif any(term in text for term in _WATCHLIST_TERMS):
        article_type = WATCHLIST_MENTION
    elif any(term in text for term in _MOVER_TERMS):
        article_type = MORNING_MOVER
    elif any(term in text for term in _SECTOR_TERMS):
        article_type = SECTOR_CONTEXT
    else:
        article_type = UNKNOWN

    if article_type == DIRECT_CATALYST:
        discovery_value, catalyst_value = _HIGH, _HIGH
    elif article_type in {MORNING_MOVER, WATCHLIST_MENTION}:
        discovery_value, catalyst_value = _HIGH, _LOW
    elif article_type == SECTOR_CONTEXT:
        discovery_value, catalyst_value = _MEDIUM, _LOW
    elif article_type in {RECAP, LEGAL_NOISE, STALE}:
        discovery_value, catalyst_value = _LOW, _NONE
    else:
        discovery_value, catalyst_value = _LOW, _LOW

    if source_quality != "TRUSTED" and discovery_value == _HIGH:
        discovery_value = _MEDIUM
    if source_quality != "TRUSTED" and catalyst_value == _HIGH:
        catalyst_value = _MEDIUM

    return {
        "article_type": article_type,
        "source_quality": source_quality,
        "discovery_value": discovery_value,
        "catalyst_value": catalyst_value,
        "age_minutes": age,
    }


def classify_seed(seed: Mapping[str, object]) -> dict:
    """Classify an existing GS298/GS306 seed without changing its eligibility."""
    return classify_news_intelligence(
        str(seed.get("headline") or ""),
        source=str(seed.get("source") or ""),
        age_minutes=seed.get("age_minutes"),
        catalyst_score=float(seed.get("catalyst_score") or 0),
        trusted_source=bool(seed.get("trusted_source")),
    )


def install() -> None:
    """Attach GS315 metadata to news seeds and discovery diagnostics."""
    from . import discovery
    from . import gs298_news_seeded_discovery as news_seed

    current_select = news_seed.select_material_news_seeds
    if not getattr(current_select, "_gs315_news_intelligence", False):
        original_select = current_select

        def select_material_news_seeds(*args, **kwargs):
            selected = original_select(*args, **kwargs)
            enriched = []
            for item in selected:
                row = dict(item)
                row.update(classify_seed(row))
                enriched.append(row)
            return enriched

        select_material_news_seeds._gs315_news_intelligence = True
        select_material_news_seeds._gs315_original = original_select
        news_seed.select_material_news_seeds = select_material_news_seeds

    current_build = discovery.build_seed_symbols
    if getattr(current_build, "_gs315_news_intelligence", False):
        return
    original_build = current_build

    def build_seed_symbols(client, settings, news_items, *, universe_verification=None):
        # Preserve the discovery call contract explicitly. app.py inspects this
        # signature to decide whether to pass UniverseVerification; hiding it
        # behind *args/**kwargs caused live Webull source accounting to be skipped
        # and produced a false Universe verification: FAIL.
        if universe_verification is None:
            result = original_build(client, settings, news_items)
        else:
            result = original_build(
                client,
                settings,
                news_items,
                universe_verification=universe_verification,
            )
        diagnostics = getattr(client, "diagnostics", None)
        block = diagnostics.get("news_seeded_discovery") if isinstance(diagnostics, dict) else None
        if isinstance(block, dict):
            evidence = block.get("evidence") or []
            enriched = []
            for item in evidence:
                row = dict(item)
                row.update(classify_seed(row))
                enriched.append(row)
            block["evidence"] = enriched
            block["classification_contract"] = (
                "article_type + source_quality + age + discovery_value + catalyst_value; "
                "classification is metadata only and cannot bypass scanner gates"
            )
        return result

    build_seed_symbols._gs315_news_intelligence = True
    build_seed_symbols._gs315_original = original_build
    discovery.build_seed_symbols = build_seed_symbols
