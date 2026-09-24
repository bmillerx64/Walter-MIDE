"""Authoritative Walter Next Discovery + News boundary.

Legacy discovery/news behavior remains the execution source while consolidation
continues. Replaceable functions resolve dynamically so Streamlit warm reruns and
later compatibility installers cannot leave this authority holding stale callables.
Provider classes remain stable imports.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from functools import wraps
from html import unescape
import os
import re
from time import perf_counter
from typing import Any, Callable, Iterable

from mide.news_provider import (
    MarketDataNewsProvider,
    NewsService,
    UnavailableNewsProvider,
)


UTC = timezone.utc
AUTHORITY = "NEWS_AWARENESS_AND_OBSERVABILITY_ONLY"
STORY_TEXT_LIMIT = 2400
STORY_SEED_TYPE = "story_material_attention"
STORY_SEED_REASON = "FMP story material attention seed"
STORY_FRESHNESS = timedelta(hours=6)

_NORMALIZE_OWNER = "_walter_gs480_story_normalize_owner"
_AS_DICT_OWNER = "_walter_gs480_story_as_dict_owner"
_CACHED_OWNER = "_walter_gs480_story_cached_owner"
_SERVICE_FETCH_OWNER = "_walter_gs480_story_service_fetch_owner"
_SELECT_OWNER = "_walter_gs480_story_select_owner"
_MERGE_OWNER = "_walter_gs480_story_merge_owner"
_BUILD_OWNER = "_walter_gs480_story_build_owner"
_INDEX_OWNER = "_walter_gs480_story_index_owner"
_ANALYZE_OWNER = "_walter_gs480_story_analyze_owner"

# Explicit forms only.  Do not treat arbitrary ALL-CAPS words as tickers.
_EXCHANGE_TICKER_RE = re.compile(
    r"(?:\(|\b)(?:NYSE(?:\s+American)?|NASDAQ|Nasdaq|NYSEAMERICAN|AMEX)\s*:\s*"
    r"(?P<symbol>[A-Z][A-Z0-9.-]{0,9})(?:\)|\b)",
)
_TICKER_LABEL_RE = re.compile(
    r"\b(?i:ticker(?:\s+symbol)?|symbol)\s*[:#-]?\s*(?P<symbol>[A-Z][A-Z0-9.-]{0,9})\b"
)
_CASHTAG_RE = re.compile(r"(?<![$A-Za-z0-9])\$(?P<symbol>[A-Z]{1,6})(?![A-Za-z0-9])")

_EVENT_PATTERNS: dict[str, tuple[str, ...]] = {
    "CONTRACT_ORDER": (
        r"\b(?:contract|agreement|purchase order|backlog|award|awarded|renewal|extension)\b",
        r"\b(?:secures?|wins?|won|signs?|entered into)\b.{0,50}\b(?:contract|agreement|order|award)\b",
        r"\b(?:supply|distribution|master service|definitive) agreement\b",
    ),
    "PARTNERSHIP_EXPANSION": (
        r"\b(?:partnership|partnered|collaboration|joint venture|strategic alliance)\b",
        r"\b(?:commercialization|commercialize|new customer|customer win|expansion|expands into)\b",
    ),
    "M_AND_A_INVESTMENT": (
        r"\b(?:acquisition|acquire[sd]?|merger|merge[sd]?|buyout|takeover|strategic investment|minority investment)\b",
    ),
    "REGULATORY_CLINICAL": (
        r"\b(?:fda|510\(k\)|fast track|breakthrough therapy|orphan drug|ind|nda|bla)\b",
        r"\b(?:phase\s*(?:2|ii|3|iii)|top[- ]?line|primary endpoint|met (?:the )?endpoint|clearance|authorization|approval)\b",
    ),
    "FINANCIAL_GROWTH": (
        r"\b(?:raises?|raised)\b.{0,40}\b(?:guidance|outlook)\b",
        r"\b(?:record revenue|annualized revenue|revenue growth|sales growth|earnings beat|beats? estimates)\b",
        r"\b(?:ebitda[- ]positive|profitable|profitability|positive cash flow)\b",
    ),
    "IP_LICENSE": (
        r"\b(?:patent|patented|license|licensing|exclusive rights|intellectual property)\b",
    ),
    "NON_DILUTIVE_FUNDING": (
        r"\b(?:non[- ]dilutive|grant award|government grant|research grant)\b",
    ),
    "DILUTION_RISK": (
        r"\b(?:public offering|registered direct|at[- ]the[- ]market|atm offering|warrant inducement|shelf registration|equity line)\b",
    ),
    "DISTRESS_RISK": (
        r"\b(?:reverse split|delisting|bankruptcy|going concern|chapter 11|chapter 7|default notice)\b",
    ),
}

_POSITIVE_ATTENTION_CATEGORIES = frozenset({
    "CONTRACT_ORDER", "PARTNERSHIP_EXPANSION", "M_AND_A_INVESTMENT",
    "REGULATORY_CLINICAL", "FINANCIAL_GROWTH", "IP_LICENSE",
    "NON_DILUTIVE_FUNDING",
})
_RISK_CATEGORIES = frozenset({"DILUTION_RISK", "DISTRESS_RISK"})

_NUMBER_RE = re.compile(
    r"(?P<cash>\$|US\$)?\s*(?P<value>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*"
    r"(?P<unit>trillion|billion|million|thousand|bln|bn|mln|mm|[TBMK])?\b",
    re.IGNORECASE,
)
_PERCENT_RE = re.compile(r"\b(?P<value>\d+(?:\.\d+)?)\s*%")
_UNIT_MULTIPLIER = {
    "": 1.0, "k": 1_000.0, "thousand": 1_000.0,
    "m": 1_000_000.0, "mm": 1_000_000.0, "mln": 1_000_000.0,
    "million": 1_000_000.0, "b": 1_000_000_000.0, "bn": 1_000_000_000.0,
    "bln": 1_000_000_000.0, "billion": 1_000_000_000.0,
    "t": 1_000_000_000_000.0, "trillion": 1_000_000_000_000.0,
}

_MARKETWIDE_BY_SYMBOL: dict[str, Any] = {}
_LAST_SELECTED: list[dict] = []
_LATEST_MARKETWIDE_TRACE: list[dict] = []
_LATEST_TARGETED_TRACE: dict[str, dict] = {}


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def _utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        stamp = value
    else:
        try:
            stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return stamp.astimezone(UTC)


def _story_text(item: dict) -> str:
    value = item.get("text") or item.get("summary") or item.get("content") or ""
    return " ".join(str(value).split())[:STORY_TEXT_LIMIT]


def explicit_ticker_mentions(text: str) -> list[str]:
    """Return only explicitly labelled exchange/ticker references from story text."""
    from mide import discovery

    value = str(text or "")
    found = []
    for pattern in (_EXCHANGE_TICKER_RE, _TICKER_LABEL_RE, _CASHTAG_RE):
        for match in pattern.finditer(value):
            symbol = str(match.group("symbol") or "").strip().upper()
            if discovery.is_valid_us_symbol(symbol) and symbol not in found:
                found.append(symbol)
    return found


def _event_categories(text: str) -> list[str]:
    value = " ".join(str(text or "").casefold().split())
    categories = []
    for category, patterns in _EVENT_PATTERNS.items():
        if any(re.search(pattern, value, re.IGNORECASE) for pattern in patterns):
            categories.append(category)
    return categories


def _number_role(window: str) -> str:
    value = window.casefold()
    if re.search(r"offering|registered direct|at[- ]the[- ]market|warrant|shelf|proceeds", value):
        return "DILUTION_OR_FINANCING"
    if re.search(r"annualized revenue|revenue|sales|arr\b|bookings", value):
        return "REVENUE"
    if re.search(r"investment|invests?|funding|financing|capital commitment|grant", value):
        return "INVESTMENT_OR_FUNDING"
    if re.search(r"contract|agreement|purchase order|award|transaction value|consideration|backlog", value):
        return "DEAL_OR_BACKLOG"
    if re.search(r"tam\b|addressable market|market opportunity|opportunity", value):
        return "MARKET_OPPORTUNITY"
    if re.search(r"users?|customers?|consumers?|subscribers?|units?|shares?", value):
        return "COUNT_OR_OWNERSHIP_BASE"
    return "STATED_QUANTITY"


def _quantities(text: str) -> list[dict]:
    value = str(text or "")
    output = []
    for match in _NUMBER_RE.finditer(value):
        raw = match.group(0).strip()
        unit = str(match.group("unit") or "").casefold()
        cash = bool(match.group("cash"))
        # Ignore ordinary small integers/years unless currency, scaled, or comma-formatted.
        if not cash and not unit and "," not in raw:
            continue
        try:
            base = float(str(match.group("value")).replace(",", ""))
        except (TypeError, ValueError):
            continue
        normalized = base * _UNIT_MULTIPLIER.get(unit, 1.0)
        start = max(0, match.start() - 70)
        end = min(len(value), match.end() + 70)
        role = _number_role(value[start:end])
        output.append({
            "text": raw,
            "normalized_value": normalized,
            "currency": cash or bool(re.search(r"dollars?|usd", value[match.end():match.end()+20], re.I)),
            "role": role,
        })
    # Preserve useful percentages as facts, not direction/valuation inference.
    for match in _PERCENT_RE.finditer(value):
        start = max(0, match.start() - 55)
        end = min(len(value), match.end() + 55)
        output.append({
            "text": match.group(0),
            "normalized_value": float(match.group("value")),
            "currency": False,
            "role": _number_role(value[start:end]) if _number_role(value[start:end]) != "STATED_QUANTITY" else "PERCENTAGE",
        })
    return output[:12]


def story_intelligence(headline: str, text: str = "") -> dict:
    """Catalog factual event semantics without converting them into trade authority."""
    combined = " ".join(part for part in (str(headline or ""), str(text or "")) if part).strip()
    categories = _event_categories(combined)
    quantities = _quantities(combined)
    positive = [category for category in categories if category in _POSITIVE_ATTENTION_CATEGORIES]
    risks = [category for category in categories if category in _RISK_CATEGORIES]
    material_attention = bool(positive) and not bool(risks)
    return {
        "authority": AUTHORITY,
        "categories": categories,
        "positive_attention_categories": positive,
        "risk_categories": risks,
        "quantities": quantities,
        "material_attention": material_attention,
        "generic_growth_word_alone_is_material": False,
        "catalyst_score_changed": False,
        "trading_authority_changed": False,
    }


def _article_context(article) -> dict:
    text = str(getattr(article, "_walter_story_text", "") or "")
    return story_intelligence(getattr(article, "headline", ""), text)


def _remember_marketwide(articles: Iterable) -> None:
    now = datetime.now(UTC)
    cutoff = now - STORY_FRESHNESS
    stale = [symbol for symbol, article in _MARKETWIDE_BY_SYMBOL.items()
             if (_utc(getattr(article, "created_at", None)) or now) < cutoff]
    for symbol in stale:
        _MARKETWIDE_BY_SYMBOL.pop(symbol, None)
    for article in articles or []:
        created = _utc(getattr(article, "created_at", None))
        if created is None or created < cutoff:
            continue
        for raw in getattr(article, "symbols", []) or []:
            symbol = str(raw or "").strip().upper()
            if not symbol:
                continue
            prior = _MARKETWIDE_BY_SYMBOL.get(symbol)
            prior_created = _utc(getattr(prior, "created_at", None)) if prior else None
            if prior is None or prior_created is None or created >= prior_created:
                _MARKETWIDE_BY_SYMBOL[symbol] = article


def _safe_selected(item: dict, *, added: set[str] | None = None) -> dict:
    created = _utc(item.get("created_at"))
    context = item.get("story_context") or {}
    symbol = str(item.get("symbol") or "").upper()
    return {
        "symbol": symbol,
        "headline": str(item.get("headline") or "")[:500],
        "source": str(item.get("source") or "")[:120],
        "provider": str(item.get("provider") or "")[:120],
        "created_at": created.isoformat() if created else None,
        "age_minutes": item.get("age_minutes"),
        "catalyst_score": item.get("catalyst_score"),
        "seed_type": item.get("seed_type"),
        "attention_only": bool(item.get("attention_only")),
        "story_derived": bool(item.get("story_derived")),
        "identity_added": symbol in (added or set()),
        "categories": list(context.get("categories") or []),
        "risk_categories": list(context.get("risk_categories") or []),
        "explicit_symbols": list(item.get("explicit_symbols") or []),
    }


def _install_article_transport() -> None:
    from mide.news_provider import FMPNewsProvider, NewsArticle, NewsService

    current_normalize = FMPNewsProvider._normalize
    if not getattr(current_normalize, _NORMALIZE_OWNER, False):
        @wraps(current_normalize)
        def normalize(cls, item: dict, *, endpoint: str):
            article = current_normalize(item, endpoint=endpoint)
            if article is None:
                return None
            text = _story_text(item)
            explicit = explicit_ticker_mentions(" ".join((article.headline, text)))
            symbols = list(dict.fromkeys([*article.symbols, *explicit]))
            if symbols != article.symbols:
                article = replace(article, symbols=sorted(symbols))
            object.__setattr__(article, "_walter_story_text", text)
            object.__setattr__(article, "_walter_explicit_symbols", explicit)
            object.__setattr__(article, "_walter_story_context", story_intelligence(article.headline, text))
            return article

        setattr(normalize, _NORMALIZE_OWNER, True)
        normalize._gs480_original = current_normalize
        FMPNewsProvider._normalize = classmethod(normalize)

    current_as_dict = NewsArticle.as_dict
    if not getattr(current_as_dict, _AS_DICT_OWNER, False):
        @wraps(current_as_dict)
        def as_dict(self):
            result = dict(current_as_dict(self))
            text = str(getattr(self, "_walter_story_text", "") or "")
            if text:
                result["text"] = text[:STORY_TEXT_LIMIT]
            explicit = list(getattr(self, "_walter_explicit_symbols", []) or [])
            if explicit:
                result["explicit_symbols"] = explicit
            context = getattr(self, "_walter_story_context", None)
            if isinstance(context, dict):
                result["story_context"] = deepcopy(context)
            return result

        setattr(as_dict, _AS_DICT_OWNER, True)
        as_dict._gs480_original = current_as_dict
        NewsArticle.as_dict = as_dict

    current_cached = NewsService._cached
    if not getattr(current_cached, _CACHED_OWNER, False):
        @wraps(current_cached)
        def cached(self):
            articles = current_cached(self)
            state_by_id = {str(item.get("id")): item for item in self._state.get("articles", []) if isinstance(item, dict)}
            for article in articles:
                saved = state_by_id.get(str(article.id)) or {}
                text = str(saved.get("text") or "")[:STORY_TEXT_LIMIT]
                explicit = list(saved.get("explicit_symbols") or [])
                context = saved.get("story_context") or story_intelligence(article.headline, text)
                object.__setattr__(article, "_walter_story_text", text)
                object.__setattr__(article, "_walter_explicit_symbols", explicit)
                object.__setattr__(article, "_walter_story_context", context)
            return articles

        setattr(cached, _CACHED_OWNER, True)
        cached._gs480_original = current_cached
        NewsService._cached = cached


def _install_marketwide_selection() -> None:
    from mide import gs298_news_seeded_discovery as gs298
    from mide.news import classify_headline, trusted_catalyst_source

    current_select = gs298.select_material_news_seeds
    if not getattr(current_select, _SELECT_OWNER, False):
        @wraps(current_select)
        def select(articles, *, now=None, limit=gs298.NEWS_SEED_LIMIT):
            global _LAST_SELECTED
            article_list = list(articles or [])
            _remember_marketwide(article_list)
            selected = [dict(item) for item in current_select(article_list, now=now, limit=limit)]
            current_time = gs298._now_utc(now)
            by_symbol = {str(item.get("symbol") or "").upper(): item for item in selected}

            for article in article_list:
                text = str(getattr(article, "_walter_story_text", "") or "")
                context = story_intelligence(getattr(article, "headline", ""), text)
                explicit = list(getattr(article, "_walter_explicit_symbols", []) or [])
                for raw_symbol in getattr(article, "symbols", []) or []:
                    symbol = str(raw_symbol or "").strip().upper()
                    if symbol in by_symbol:
                        by_symbol[symbol]["story_context"] = deepcopy(context)
                        by_symbol[symbol]["explicit_symbols"] = list(explicit)
                        continue
                    created = _utc(getattr(article, "created_at", None))
                    if (
                        not symbol or created is None
                        or current_time - created > STORY_FRESHNESS
                        or created > current_time + timedelta(minutes=5)
                        or not context.get("material_attention")
                        or not trusted_catalyst_source(getattr(article, "source", ""))
                    ):
                        continue
                    headline_score, flags = classify_headline(getattr(article, "headline", ""))
                    row = {
                        "symbol": symbol,
                        "headline": str(getattr(article, "headline", "") or ""),
                        "source": str(getattr(article, "source", "") or "FMP"),
                        "provider": str(getattr(article, "provider", "") or "Financial Modeling Prep"),
                        "created_at": created,
                        "age_minutes": round(max(0.0, (current_time - created).total_seconds()) / 60, 1),
                        "catalyst_score": float(headline_score or 0),
                        "catalyst_flags": list(flags),
                        "trusted_source": True,
                        "seed_type": STORY_SEED_TYPE,
                        "attention_only": True,
                        "story_derived": True,
                        "story_context": deepcopy(context),
                        "explicit_symbols": list(explicit),
                    }
                    selected.append(row)
                    by_symbol[symbol] = row

            selected.sort(key=lambda item: (_utc(item.get("created_at")) or datetime.min.replace(tzinfo=UTC)), reverse=True)
            _LAST_SELECTED.clear()
            _LAST_SELECTED.extend(deepcopy(selected[: max(0, int(limit))]))
            return selected[: max(0, int(limit))]

        _inherit(select, current_select)
        setattr(select, _SELECT_OWNER, True)
        select._gs480_original = current_select
        gs298.select_material_news_seeds = select

    current_merge = gs298.merge_news_seeds
    if not getattr(current_merge, _MERGE_OWNER, False):
        @wraps(current_merge)
        def merge(seeds, reasons, selected):
            story_rows = [dict(item) for item in selected or [] if item.get("seed_type") == STORY_SEED_TYPE]
            regular = [item for item in selected or [] if item.get("seed_type") != STORY_SEED_TYPE]
            output, updated_reasons, added = current_merge(seeds, reasons, regular)
            existing = {str(symbol or "").strip().upper() for symbol in output}
            for item in story_rows:
                symbol = str(item.get("symbol") or "").strip().upper()
                if not symbol or symbol in existing:
                    continue
                output.append(symbol)
                existing.add(symbol)
                updated_reasons.setdefault(symbol, []).append(
                    f"{STORY_SEED_REASON}: {str(item.get('source') or 'FMP').strip()}"
                )
                added.append(dict(item))
            return output, updated_reasons, added

        _inherit(merge, current_merge)
        setattr(merge, _MERGE_OWNER, True)
        merge._gs480_original = current_merge
        gs298.merge_news_seeds = merge


def _install_discovery_diagnostics() -> None:
    from mide import discovery

    current_build = discovery.build_seed_symbols
    if getattr(current_build, _BUILD_OWNER, False):
        return

    @wraps(current_build)
    def build(client, settings, news_items, *, universe_verification=None):
        global _LAST_SELECTED, _LATEST_MARKETWIDE_TRACE
        _LAST_SELECTED.clear()
        if universe_verification is None:
            result = current_build(client, settings, news_items)
        else:
            result = current_build(client, settings, news_items, universe_verification=universe_verification)
        seeds, _reasons = result
        diagnostics = getattr(client, "diagnostics", None)
        news_diag = diagnostics.get("news_seeded_discovery") if isinstance(diagnostics, dict) else None
        added = set(news_diag.get("symbols_added") or []) if isinstance(news_diag, dict) else set()
        trace = [_safe_selected(item, added=added) for item in _LAST_SELECTED]
        _LATEST_MARKETWIDE_TRACE.clear()
        _LATEST_MARKETWIDE_TRACE.extend(deepcopy(trace))
        if isinstance(news_diag, dict):
            news_diag["selected_evidence"] = deepcopy(trace)
            news_diag["selected_symbols"] = [item["symbol"] for item in trace]
            news_diag["already_native_symbols"] = [
                item["symbol"] for item in trace if item["symbol"] in set(seeds) and item["symbol"] not in added
            ]
            news_diag["story_attention_symbols"] = [
                item["symbol"] for item in trace if item.get("seed_type") == STORY_SEED_TYPE
            ]
            news_diag["gs480_authority"] = AUTHORITY
        return result

    _inherit(build, current_build)
    setattr(build, _BUILD_OWNER, True)
    build._gs480_original = current_build
    discovery.build_seed_symbols = build


def _install_targeted_handoff() -> None:
    from mide.news_provider import NewsService
    from mide import news as news_module

    current_fetch = NewsService.fetch
    if getattr(current_fetch, _SERVICE_FETCH_OWNER, False):
        return

    @wraps(current_fetch)
    def fetch(self, *, symbols=(), initial_lookback=timedelta(days=3), force_lookback=False):
        global _LATEST_TARGETED_TRACE
        requested = sorted({str(symbol or "").strip().upper() for symbol in symbols if str(symbol or "").strip()})
        returned = list(current_fetch(
            self, symbols=requested, initial_lookback=initial_lookback,
            force_lookback=force_lookback,
        ) or [])
        identities = {(str(item.get("provider") or "").casefold(), str(item.get("id") or "")) for item in returned}
        handoff_ids = set()
        handoff_symbols = set()
        now = self.now().astimezone(UTC)
        for symbol in requested:
            article = _MARKETWIDE_BY_SYMBOL.get(symbol)
            created = _utc(getattr(article, "created_at", None)) if article else None
            if article is None or created is None or now - created > STORY_FRESHNESS:
                continue
            row = article.as_dict()
            identity = (str(row.get("provider") or "").casefold(), str(row.get("id") or ""))
            if identity not in identities:
                returned.append(row)
                identities.add(identity)
                handoff_ids.add(identity)
                handoff_symbols.add(symbol)

        returned.sort(key=lambda item: _utc(item.get("created_at")) or datetime.min.replace(tzinfo=UTC), reverse=True)
        selected = news_module.index_news(returned)
        trace = {}
        for symbol in requested:
            item = selected.get(symbol)
            if not item:
                trace[symbol] = {
                    "symbol": symbol, "article_found": False,
                    "marketwide_handoff": symbol in handoff_symbols,
                }
                continue
            created = _utc(item.get("created_at"))
            identity = (str(item.get("provider") or "").casefold(), str(item.get("article_id") or ""))
            trace[symbol] = {
                "symbol": symbol,
                "article_found": True,
                "headline": str(item.get("headline") or "")[:500],
                "created_at": created.isoformat() if created else None,
                "age_seconds_at_scan": round(max(0.0, (now - created).total_seconds()), 1) if created else None,
                "source": item.get("source"),
                "provider": item.get("provider"),
                "catalyst_score": item.get("catalyst_score"),
                "flags": list(item.get("flags") or []),
                "explicit_symbols": list(item.get("explicit_symbols") or []),
                "story_context": deepcopy(item.get("story_context") or {}),
                "marketwide_handoff": identity in handoff_ids,
            }
        _LATEST_TARGETED_TRACE.clear()
        _LATEST_TARGETED_TRACE.update(deepcopy(trace))
        self.metrics["gs480_story_intelligence"] = {
            "authority": AUTHORITY,
            "requested_symbols": requested,
            "marketwide_handoff_symbols": sorted(handoff_symbols),
            "article_found_symbols": sorted(symbol for symbol, item in trace.items() if item.get("article_found")),
            "article_missing_symbols": sorted(symbol for symbol, item in trace.items() if not item.get("article_found")),
            "additional_provider_requests": 0,
        }
        return returned

    _inherit(fetch, current_fetch)
    setattr(fetch, _SERVICE_FETCH_OWNER, True)
    fetch._gs480_original = current_fetch
    NewsService.fetch = fetch


def _install_index_and_records() -> None:
    from mide import news as news_module
    from mide import discovery

    current_index = news_module.index_news
    if not getattr(current_index, _INDEX_OWNER, False):
        @wraps(current_index)
        def index(news_items):
            items = list(news_items or [])
            result = current_index(items)
            for symbol, chosen in result.items():
                headline = str(chosen.get("headline") or "")
                matches = [
                    item for item in items
                    if symbol in {str(raw or "").strip().upper() for raw in item.get("symbols") or []}
                    and str(item.get("headline") or "") == headline
                ]
                if not matches:
                    continue
                source = max(matches, key=lambda item: _utc(item.get("created_at")) or datetime.min.replace(tzinfo=UTC))
                text = str(source.get("text") or "")[:STORY_TEXT_LIMIT]
                chosen["article_id"] = source.get("id")
                chosen["story_text"] = text
                chosen["explicit_symbols"] = list(source.get("explicit_symbols") or [])
                chosen["story_context"] = deepcopy(source.get("story_context") or story_intelligence(headline, text))
                chosen["news_created_at"] = chosen.get("created_at")
            return result

        _inherit(index, current_index)
        setattr(index, _INDEX_OWNER, True)
        index._gs480_original = current_index
        news_module.index_news = index

    current_analyze = discovery.analyze_candidates
    if not getattr(current_analyze, _ANALYZE_OWNER, False):
        @wraps(current_analyze)
        def analyze(client, candidates, news_index, discovery_reasons):
            records = current_analyze(client, candidates, news_index, discovery_reasons)
            enriched = []
            for record in records or []:
                symbol = str(record.get("symbol") or "").strip().upper()
                selected = (news_index or {}).get(symbol) or {}
                if not selected:
                    enriched.append(record)
                    continue
                row = dict(record)
                row.update({
                    "news_source": selected.get("source"),
                    "news_provider": selected.get("provider"),
                    "news_created_at": (
                        selected.get("created_at").isoformat()
                        if isinstance(selected.get("created_at"), datetime)
                        else selected.get("created_at")
                    ),
                    "news_explicit_symbols": list(selected.get("explicit_symbols") or []),
                    "catalyst_story": deepcopy(selected.get("story_context") or {}),
                })
                targeted = _LATEST_TARGETED_TRACE.get(symbol) or {}
                if targeted:
                    row["news_age_seconds_at_scan"] = targeted.get("age_seconds_at_scan")
                    row["news_marketwide_handoff"] = bool(targeted.get("marketwide_handoff"))
                enriched.append(row)
            diagnostics = getattr(client, "diagnostics", None)
            if isinstance(diagnostics, dict):
                diagnostics["gs480_catalyst_story_intelligence"] = {
                    "authority": AUTHORITY,
                    "records_with_story": sum(bool(item.get("catalyst_story")) for item in enriched),
                    "targeted_trace_symbols": sorted(_LATEST_TARGETED_TRACE),
                    "additional_provider_requests": 0,
                    "catalyst_score_changed": False,
                    "trading_logic_changed": False,
                }
            return enriched

        _inherit(analyze, current_analyze)
        setattr(analyze, _ANALYZE_OWNER, True)
        analyze._gs480_original = current_analyze
        discovery.analyze_candidates = analyze



def install_catalyst_story_news() -> None:
    """Install GS480's Discovery + News responsibilities in historical order."""
    _install_article_transport()
    _install_marketwide_selection()
    _install_discovery_diagnostics()
    _install_index_and_records()
    _install_targeted_handoff()


# ---------------------------------------------------------------------------
# GS502 direct Benzinga breaking-news discovery
# ---------------------------------------------------------------------------

BENZINGA_AUTHORITY = "DISCOVERY_IDENTITY_AND_NEWS_CONTEXT_ONLY"
BENZINGA_ENDPOINT = "https://api.benzinga.com/api/v2/news"
BENZINGA_INITIAL_LOOKBACK = timedelta(minutes=10)
BENZINGA_POLL_OVERLAP = timedelta(minutes=2)
BENZINGA_CACHE_FRESHNESS = timedelta(minutes=90)
BENZINGA_MAX_CACHE_ARTICLES = 300
BENZINGA_PAGE_SIZE = 100
BENZINGA_HTTP_TIMEOUT_SECONDS = 3.0

_BENZINGA_DISCOVERY_OWNER = "_walter_gs502_benzinga_breaking_discovery_owner"
_BENZINGA_ARTICLE_CACHE: dict[str, Any] = {}


def benzinga_utc_now(now=None) -> datetime:
    value = now() if callable(now) else now
    value = value or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def benzinga_configured_token() -> str:
    """Resolve Benzinga API credentials without logging or exposing the value."""
    for name in ("BENZINGA_API_KEY", "BENZINGA_TOKEN"):
        value = str(os.getenv(name, "") or "").strip()
        if value:
            return value
    try:
        import streamlit as st
        for name in ("BENZINGA_API_KEY", "BENZINGA_TOKEN"):
            try:
                value = str(st.secrets.get(name, "") or "").strip()
            except Exception:
                value = ""
            if value:
                return value
    except Exception:
        pass
    return ""


def benzinga_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        stamp = value
    else:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            stamp = parsedate_to_datetime(raw)
        except (TypeError, ValueError, OverflowError):
            try:
                stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except (TypeError, ValueError):
                return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return stamp.astimezone(UTC)


def benzinga_plain_text(value: Any, *, limit: int = 2400) -> str:
    text = str(value or "")
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(unescape(text).split())[:limit]


def benzinga_stock_symbols(item: dict) -> list[str]:
    from mide import discovery

    values: list[str] = []
    for stock in item.get("stocks") or []:
        if isinstance(stock, dict):
            raw = stock.get("name") or stock.get("symbol") or stock.get("ticker")
        else:
            raw = stock
        symbol = str(raw or "").strip().upper()
        if symbol and discovery.is_valid_us_symbol(symbol) and symbol not in values:
            values.append(symbol)

    raw_tickers = item.get("tickers") or item.get("symbols") or []
    if isinstance(raw_tickers, str):
        raw_tickers = re.split(r"[,\s]+", raw_tickers)
    for raw in raw_tickers if isinstance(raw_tickers, (list, tuple, set)) else []:
        symbol = str(raw or "").strip().upper()
        if symbol and discovery.is_valid_us_symbol(symbol) and symbol not in values:
            values.append(symbol)
    return values[:20]


def normalize_benzinga_article(item: dict):
    """Normalize one Benzinga Newsfeed row into Walter's provider-neutral contract."""
    from mide.news_provider import NewsArticle

    if not isinstance(item, dict):
        return None
    headline = str(item.get("title") or item.get("headline") or "").strip()
    created = benzinga_timestamp(item.get("created") or item.get("created_at"))
    if not headline or created is None:
        return None

    body = benzinga_plain_text(item.get("body") or item.get("teaser") or "")
    symbols = benzinga_stock_symbols(item)
    explicit = explicit_ticker_mentions(" ".join((headline, body)))
    symbols = list(dict.fromkeys([*symbols, *explicit]))
    if not symbols:
        return None

    updated = benzinga_timestamp(item.get("updated") or item.get("updated_at"))
    article_id = str(item.get("id") or f"{created.isoformat()}:{headline.casefold()[:160]}")
    article = NewsArticle(
        id=f"benzinga:{article_id}",
        headline=headline,
        created_at=created,
        updated_at=updated,
        symbols=sorted(symbols),
        source="Benzinga",
        url=str(item.get("url") or "") or None,
        provider="Benzinga Newsfeed",
    )
    object.__setattr__(article, "_walter_story_text", body[:STORY_TEXT_LIMIT])
    object.__setattr__(article, "_walter_explicit_symbols", explicit)
    object.__setattr__(
        article,
        "_walter_story_context",
        story_intelligence(headline, body),
    )
    return article


def fetch_benzinga_delta(
    token: str,
    *,
    since: datetime,
    now=None,
    session=None,
    timeout: float = BENZINGA_HTTP_TIMEOUT_SECONDS,
    page_size: int = BENZINGA_PAGE_SIZE,
) -> list:
    """Fetch one bounded market-wide Benzinga Newsfeed delta."""
    import requests

    key = str(token or "").strip()
    if not key:
        return []
    current = benzinga_utc_now(now)
    since = since.astimezone(UTC)
    client = session or requests.Session()
    params = {
        "updatedSince": int(since.timestamp()),
        "page": 0,
        "pageSize": max(1, min(int(page_size), BENZINGA_PAGE_SIZE)),
        "displayOutput": "full",
    }
    headers = {
        "accept": "application/json",
        "Authorization": f"token {key}",
    }
    response = client.get(
        BENZINGA_ENDPOINT,
        params=params,
        headers=headers,
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    rows = payload if isinstance(payload, list) else (
        payload.get("articles", payload.get("data", []))
        if isinstance(payload, dict)
        else []
    )

    articles = []
    for item in rows or []:
        article = normalize_benzinga_article(item)
        if article is None:
            continue
        updated = article.updated_at or article.created_at
        if (
            updated >= since - timedelta(seconds=2)
            and article.created_at <= current + timedelta(minutes=5)
        ):
            articles.append(article)
    return articles


def cache_benzinga_articles(
    articles: list,
    *,
    now: datetime,
    article_cache: dict[str, Any] | None = None,
) -> list:
    cache = _BENZINGA_ARTICLE_CACHE if article_cache is None else article_cache
    cutoff = now - BENZINGA_CACHE_FRESHNESS
    for article in articles or []:
        if article.created_at < cutoff:
            continue
        prior = cache.get(article.id)
        prior_stamp = (prior.updated_at or prior.created_at) if prior else None
        stamp = article.updated_at or article.created_at
        if prior is None or prior_stamp is None or stamp >= prior_stamp:
            cache[article.id] = article

    stale = [
        key for key, article in cache.items()
        if article.created_at < cutoff
    ]
    for key in stale:
        cache.pop(key, None)

    ordered = sorted(
        cache.values(),
        key=lambda article: article.updated_at or article.created_at,
        reverse=True,
    )
    for article in ordered[BENZINGA_MAX_CACHE_ARTICLES:]:
        cache.pop(article.id, None)
    return ordered[:BENZINGA_MAX_CACHE_ARTICLES]


def benzinga_safe_status(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    try:
        return int(getattr(response, "status_code"))
    except (TypeError, ValueError):
        return None


def poll_benzinga_breaking_news(
    *,
    token: str,
    now=None,
    session=None,
    last_successful_poll: datetime | None = None,
    article_cache: dict[str, Any] | None = None,
    fetcher=None,
) -> tuple[list, dict, datetime | None]:
    """Fetch one delta while leaving historical scalar state to the GS502 facade."""
    current = benzinga_utc_now(now)
    since = (
        max(
            current - BENZINGA_INITIAL_LOOKBACK,
            last_successful_poll - BENZINGA_POLL_OVERLAP,
        )
        if last_successful_poll is not None
        else current - BENZINGA_INITIAL_LOOKBACK
    )
    fetch = fetcher or fetch_benzinga_delta
    started = perf_counter()
    try:
        fresh = fetch(
            token,
            since=since,
            now=current,
            session=session,
        )
    except Exception as exc:
        cached = cache_benzinga_articles(
            [],
            now=current,
            article_cache=article_cache,
        )
        return cached, {
            "authority": BENZINGA_AUTHORITY,
            "configured": bool(token),
            "request_made": True,
            "endpoint": "/api/v2/news",
            "updated_since": int(since.timestamp()),
            "request_latency_ms": round((perf_counter() - started) * 1000, 1),
            "transport_disposition": "PROVIDER_FAILURE",
            "exception_type": type(exc).__name__,
            "http_status": benzinga_safe_status(exc),
            "articles_received": 0,
            "cached_articles": len(cached),
            "credential_persisted": False,
            "raw_exception_persisted": False,
            "trading_authority_changed": False,
        }, last_successful_poll

    cached = cache_benzinga_articles(
        fresh,
        now=current,
        article_cache=article_cache,
    )
    return cached, {
        "authority": BENZINGA_AUTHORITY,
        "configured": True,
        "request_made": True,
        "endpoint": "/api/v2/news",
        "updated_since": int(since.timestamp()),
        "request_latency_ms": round((perf_counter() - started) * 1000, 1),
        "transport_disposition": (
            "SUCCESS_WITH_ARTICLES" if fresh else "SUCCESS_EMPTY"
        ),
        "articles_received": len(fresh),
        "cached_articles": len(cached),
        "credential_persisted": False,
        "raw_exception_persisted": False,
        "trading_authority_changed": False,
    }, current


def merge_benzinga_breaking_news_discovery(
    client,
    seeds: list[str],
    reasons: dict[str, list[str]],
    *,
    now=None,
    token_resolver=None,
    poller=None,
    article_cache: dict[str, Any] | None = None,
) -> tuple[list[str], dict[str, list[str]], dict]:
    """Return discovery identity/reasons plus the bounded GS502 trace."""
    provider = str(
        getattr(client, "provider_name", "") or client.__class__.__name__
    )
    is_webull = (
        "WEBULL" in provider.upper()
        or "WEBULL" in client.__class__.__name__.upper()
    )
    resolve_token = token_resolver or benzinga_configured_token
    token = resolve_token()
    cache = _BENZINGA_ARTICLE_CACHE if article_cache is None else article_cache
    if not is_webull or not token:
        trace = {
            "authority": BENZINGA_AUTHORITY,
            "configured": bool(token),
            "request_made": False,
            "reason": (
                "non-Webull provider"
                if not is_webull
                else "Benzinga credential unavailable"
            ),
            "articles_received": 0,
            "cached_articles": len(cache),
            "selected_symbols": [],
            "symbols_added": [],
            "trading_authority_changed": False,
        }
        diagnostics = getattr(client, "diagnostics", None)
        if isinstance(diagnostics, dict):
            diagnostics["benzinga_breaking_news"] = deepcopy(trace)
        return list(seeds), reasons, trace

    current = benzinga_utc_now(now)
    active_poller = poller
    if active_poller is None:
        articles, transport, _next_poll = poll_benzinga_breaking_news(
            token=token,
            now=current,
            article_cache=cache,
        )
    else:
        result = active_poller(token=token, now=current)
        articles, transport = result[0], result[1]

    from mide import gs298_news_seeded_discovery as gs298
    selected = gs298.select_material_news_seeds(
        articles,
        now=current,
        limit=gs298.NEWS_SEED_LIMIT,
    )
    output = list(seeds)
    updated_reasons = {
        str(symbol): list(values)
        for symbol, values in (reasons or {}).items()
    }
    existing = {str(symbol or "").strip().upper() for symbol in output}
    added = []
    for item in selected:
        symbol = str(item.get("symbol") or "").strip().upper()
        if not symbol or symbol in existing:
            continue
        seed_type = str(item.get("seed_type") or "")
        if seed_type == "morning_mover_attention":
            label = "Benzinga breaking mover attention seed"
        elif seed_type == "story_material_attention":
            label = "Benzinga story material attention seed"
        else:
            label = "Benzinga breaking material news seed"
        output.append(symbol)
        existing.add(symbol)
        updated_reasons.setdefault(symbol, []).append(
            f"{label}: {str(item.get('source') or 'Benzinga').strip()}"
        )
        added.append(dict(item))

    selected_symbols = [
        str(item.get("symbol") or "").strip().upper()
        for item in selected
        if str(item.get("symbol") or "").strip()
    ]
    added_symbols = [
        str(item.get("symbol") or "").strip().upper()
        for item in added
        if str(item.get("symbol") or "").strip()
    ]
    trace = {
        **transport,
        "selected_symbol_count": len(selected_symbols),
        "selected_symbols": selected_symbols[:40],
        "symbols_added_count": len(added_symbols),
        "symbols_added": added_symbols[:40],
        "material_selected": sum(
            item.get("seed_type") == "material_catalyst"
            for item in selected
        ),
        "attention_selected": sum(
            item.get("seed_type") == "morning_mover_attention"
            for item in selected
        ),
        "headlines": [
            {
                "symbol": str(item.get("symbol") or "").upper(),
                "headline": str(item.get("headline") or "")[:300],
                "created_at": (
                    item.get("created_at").isoformat()
                    if isinstance(item.get("created_at"), datetime)
                    else item.get("created_at")
                ),
                "seed_type": item.get("seed_type"),
                "story_derived": bool(item.get("story_derived")),
            }
            for item in selected[:20]
        ],
        "trading_authority_changed": False,
    }
    diagnostics = getattr(client, "diagnostics", None)
    if isinstance(diagnostics, dict):
        diagnostics["benzinga_breaking_news"] = deepcopy(trace)
    return output, updated_reasons, trace


def install_benzinga_breaking_news_discovery() -> None:
    """Install GS502's Discovery + News wrapper at its historical position."""
    from mide import discovery

    current = discovery.build_seed_symbols
    if getattr(current, _BENZINGA_DISCOVERY_OWNER, False):
        return

    @wraps(current)
    def build_seed_symbols(
        client,
        settings,
        news_items,
        *,
        universe_verification=None,
    ):
        if universe_verification is None:
            seeds, reasons = current(client, settings, news_items)
        else:
            seeds, reasons = current(
                client,
                settings,
                news_items,
                universe_verification=universe_verification,
            )
        from mide import gs502_benzinga_breaking_news as gs502
        return gs502.merge_breaking_news_discovery(client, seeds, reasons)

    _inherit(build_seed_symbols, current)
    setattr(build_seed_symbols, _BENZINGA_DISCOVERY_OWNER, True)
    build_seed_symbols._gs502_benzinga_breaking_news = True
    build_seed_symbols._gs502_original = current
    discovery.build_seed_symbols = build_seed_symbols


# ---------------------------------------------------------------------------
# GS455 bounded early-open ignition admission
# ---------------------------------------------------------------------------
#
# Discovery + News owns the narrow 09:30-09:45 admission exception. The historical
# gs455 module retains its calibrated thresholds and mutable clock/helper seam so
# replay tests and retained Streamlit runtimes keep the same observable contract.


def early_open_market_now():
    from mide.time_service import eastern_time

    return eastern_time()


def early_open_inside_window() -> bool:
    from mide import gs455_early_ignition_3m_confirmation as gs455

    now = gs455._market_now()
    current = now.time().replace(tzinfo=None)
    return (
        gs455.EARLY_OPEN_START
        <= current
        < gs455.EARLY_OPEN_END
    )


def early_open_prefilter_decision(
    original,
    symbol: str,
    snapshot: dict,
    settings,
) -> dict:
    """Apply the validated bounded early-open discovery exception."""
    from mide import gs455_early_ignition_3m_confirmation as gs455

    base = original(
        symbol,
        snapshot,
        settings,
    )
    if (
        base.get("passed")
        or not gs455._inside_early_open_window()
    ):
        return base
    if (
        base.get("failed_rule")
        != gs455._PREFILTER_FAILURE
    ):
        return base

    measured = dict(
        base.get("measured_values") or {}
    )
    pct_change = (
        gs455._number(
            measured,
            "pct_change",
            default=0.0,
        )
        or 0.0
    )
    volume = (
        gs455._number(
            measured,
            "volume",
            default=0.0,
        )
        or 0.0
    )
    if (
        pct_change
        < gs455.EARLY_OPEN_MIN_PCT_CHANGE
        or volume
        < gs455.EARLY_OPEN_MIN_VOLUME
    ):
        return base

    decision = deepcopy(base)
    decision["passed"] = True
    decision["failed_rule"] = None
    decision["failed_metrics"] = []
    decision["reason"] = (
        "passed prefilter via early-open ignition "
        f"(>={gs455.EARLY_OPEN_MIN_PCT_CHANGE:g}% "
        f"and >={gs455.EARLY_OPEN_MIN_VOLUME:,.0f} shares)"
    )
    thresholds = dict(
        decision.get("thresholds") or {}
    )
    thresholds["early_open_exception"] = {
        "window_et": "09:30-09:45",
        "min_pct_change": (
            gs455.EARLY_OPEN_MIN_PCT_CHANGE
        ),
        "min_volume": (
            gs455.EARLY_OPEN_MIN_VOLUME
        ),
    }
    decision["thresholds"] = thresholds
    return decision


def install_early_open_ignition_admission() -> None:
    """Bind the existing prefilter boundary at GS455's historical install point."""
    from mide import discovery, flight_recorder
    from mide import gs455_early_ignition_3m_confirmation as gs455

    current = flight_recorder.prefilter_decision
    if getattr(
        current,
        "_gs455_early_open_ignition",
        False,
    ):
        discovery.prefilter_decision = current
        return

    @wraps(current)
    def prefilter_decision(
        symbol: str,
        snapshot: dict,
        settings,
    ) -> dict:
        return gs455._early_open_prefilter_decision(
            current,
            symbol,
            snapshot,
            settings,
        )

    gs455._inherit(
        prefilter_decision,
        current,
    )
    prefilter_decision._gs455_early_open_ignition = True
    prefilter_decision._gs455_original = current
    flight_recorder.prefilter_decision = (
        prefilter_decision
    )
    discovery.prefilter_decision = (
        prefilter_decision
    )


# ---------------------------------------------------------------------------
# GS540 news-corroborated shadow RVOL discovery
# ---------------------------------------------------------------------------

SHADOW_RVOL_AUTHORITY = "DISCOVERY_IDENTITY_ONLY_NEWS_CORROBORATED_SHADOW_RVOL"
SHADOW_RVOL_LIMIT = 20
SHADOW_RVOL_MIN = 2.0
SHADOW_RVOL_NEWS_LOOKBACK = timedelta(hours=6)
_SHADOW_RVOL_OWNER = "_walter_gs540_news_corroborated_shadow_rvol_owner"


def _shadow_rvol_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def shadow_rvol_now_utc(now=None) -> datetime:
    value = now() if callable(now) else now
    value = value or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def shadow_rvol_rows(client) -> list[dict]:
    """Read the already-fetched GS523 page-2 RVOL evidence without a provider call."""
    diagnostics = getattr(client, "diagnostics", None)
    if not isinstance(diagnostics, dict):
        return []
    native = diagnostics.get("webull_native_discovery") or {}
    shadow = native.get("shadow_discovery") or {}
    page = shadow.get("relative_volume_page2") or {}
    rows = page.get("rows") or []
    return [
        dict(row)
        for row in rows
        if isinstance(row, dict)
    ][:SHADOW_RVOL_LIMIT]


def eligible_shadow_rvol_rows(rows: Iterable[dict]) -> list[dict]:
    """Keep positive/neutral page-2 RVOL anomalies with meaningful relative volume."""
    output = []
    seen = set()
    for raw in rows or []:
        row = dict(raw)
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol or symbol in seen:
            continue
        rvol = _shadow_rvol_number(row.get("relative_volume_10d"))
        change = _shadow_rvol_number(row.get("change_ratio"))
        price = _shadow_rvol_number(row.get("price"))
        if rvol is None or rvol < SHADOW_RVOL_MIN:
            continue
        if change is not None and change < 0:
            continue
        if price is not None and price <= 0:
            continue
        seen.add(symbol)
        row["symbol"] = symbol
        output.append(row)
    return output[:SHADOW_RVOL_LIMIT]


def fetch_shadow_rvol_targeted_articles(
    symbols: list[str],
    *,
    now: datetime,
) -> list:
    """Make one bounded entitlement-safe FMP stock-news fetch for shadow symbols."""
    from mide import news_provider

    key = news_provider._configured_fmp_api_key()
    if not key or not symbols:
        return []
    provider = news_provider.FMPNewsProvider(
        key,
        timeout=4,
        now=lambda: now,
    )
    return provider.fetch(
        since=now - SHADOW_RVOL_NEWS_LOOKBACK,
        symbols=symbols,
    )


def merge_news_corroborated_shadow_rvol(
    client,
    seeds: list[str],
    reasons: dict[str, list[str]],
    *,
    now=None,
    fetcher: Callable[[list[str], datetime], list] | None = None,
) -> tuple[list[str], dict[str, list[str]], dict]:
    """Join GS523 shadow RVOL with material news without bypassing downstream gates."""
    current = shadow_rvol_now_utc(now)
    all_shadow_rows = shadow_rvol_rows(client)
    rows = eligible_shadow_rvol_rows(all_shadow_rows)
    shadow_by_symbol = {row["symbol"]: row for row in rows}
    symbols = list(shadow_by_symbol)

    output = list(seeds or [])
    updated_reasons = {
        str(symbol): list(values)
        for symbol, values in (reasons or {}).items()
    }
    existing = {
        str(symbol or "").strip().upper()
        for symbol in output
    }

    trace = {
        "authority": SHADOW_RVOL_AUTHORITY,
        "shadow_rows_seen": len(all_shadow_rows),
        "eligible_shadow_symbols": symbols,
        "request_made": False,
        "articles_received": 0,
        "material_corroborations": [],
        "symbols_added": [],
        "trading_authority_changed": False,
    }
    if not symbols:
        return output, updated_reasons, trace

    try:
        if fetcher is None:
            from mide import news_provider

            configured = bool(news_provider._configured_fmp_api_key())
            trace["configured"] = configured
            if not configured:
                trace["reason"] = "FMP credential unavailable"
                return output, updated_reasons, trace
            trace["request_made"] = True
            articles = fetch_shadow_rvol_targeted_articles(
                symbols,
                now=current,
            )
        else:
            trace["configured"] = True
            trace["request_made"] = True
            articles = list(fetcher(symbols, current) or [])
    except Exception as exc:
        trace.update(
            transport_disposition="PROVIDER_FAILURE",
            exception_type=type(exc).__name__,
            raw_exception_persisted=False,
        )
        return output, updated_reasons, trace

    trace["articles_received"] = len(articles)
    from mide import gs298_news_seeded_discovery as gs298

    selected = gs298.select_material_news_seeds(
        articles,
        now=current,
        limit=SHADOW_RVOL_LIMIT,
    )
    selected = [
        item
        for item in selected
        if str(item.get("symbol") or "").strip().upper() in shadow_by_symbol
        and item.get("seed_type") == "material_catalyst"
    ]

    corroborations = []
    added = []
    for item in selected:
        symbol = str(item.get("symbol") or "").strip().upper()
        row = shadow_by_symbol[symbol]
        published = item.get("created_at")
        published_text = (
            published.astimezone(UTC).isoformat()
            if isinstance(published, datetime)
            else str(published or "")
        )
        evidence = {
            "symbol": symbol,
            "shadow_rvol_rank": row.get("rank"),
            "shadow_rvol_10d": row.get("relative_volume_10d"),
            "shadow_change_ratio": row.get("change_ratio"),
            "shadow_price": row.get("price"),
            "news_source": str(item.get("source") or ""),
            "news_provider": str(item.get("provider") or ""),
            "news_published_at": published_text,
            "headline": str(item.get("headline") or "")[:400],
            "catalyst_score": item.get("catalyst_score"),
            "trusted_source": bool(item.get("trusted_source")),
        }
        corroborations.append(evidence)
        reason = (
            "material news + Webull shadow RVOL corroboration: "
            + (
                evidence["news_source"]
                or evidence["news_provider"]
                or "news provider"
            )
        )
        if reason not in updated_reasons.setdefault(symbol, []):
            updated_reasons[symbol].append(reason)
        if symbol not in existing:
            output.append(symbol)
            existing.add(symbol)
            added.append(symbol)

    trace.update(
        transport_disposition="SUCCESS",
        material_corroborations=corroborations,
        symbols_added=added,
        symbols_added_count=len(added),
    )
    return output, updated_reasons, trace


def install_news_corroborated_shadow_rvol() -> None:
    """Bind GS540 discovery identity at its historical final-news seam."""
    from mide import discovery

    current = discovery.build_seed_symbols
    if getattr(current, _SHADOW_RVOL_OWNER, False):
        return

    @wraps(current)
    def build_seed_symbols(
        client,
        settings,
        news_items,
        *,
        universe_verification=None,
    ):
        if universe_verification is None:
            seeds, reasons = current(client, settings, news_items)
        else:
            seeds, reasons = current(
                client,
                settings,
                news_items,
                universe_verification=universe_verification,
            )

        from mide import gs540_news_corroborated_shadow_rvol as gs540

        seeds, reasons, trace = gs540.merge_news_corroborated_shadow_rvol(
            client,
            seeds,
            reasons,
        )
        diagnostics = getattr(client, "diagnostics", None)
        if isinstance(diagnostics, dict):
            diagnostics["news_corroborated_shadow_rvol"] = deepcopy(trace)
            diagnostics["final_seed_count"] = len(seeds)
        return seeds, reasons

    _inherit(build_seed_symbols, current)
    build_seed_symbols._gs540_news_corroborated_shadow_rvol = True
    build_seed_symbols._gs540_original = current
    setattr(build_seed_symbols, _SHADOW_RVOL_OWNER, True)
    discovery.build_seed_symbols = build_seed_symbols


def build_seed_symbols(*args, **kwargs):
    from mide import discovery
    return discovery.build_seed_symbols(*args, **kwargs)


def is_valid_us_symbol(*args, **kwargs):
    from mide import discovery
    return discovery.is_valid_us_symbol(*args, **kwargs)


def prefilter_snapshots(*args, **kwargs):
    from mide import discovery
    return discovery.prefilter_snapshots(*args, **kwargs)


def snapshot_identity_records(*args, **kwargs):
    from mide import discovery
    return discovery.snapshot_identity_records(*args, **kwargs)


def index_news(*args, **kwargs):
    from mide import news
    return news.index_news(*args, **kwargs)


def symbol_news_evidence(*args, **kwargs):
    from mide import news_provider
    return news_provider.symbol_news_evidence(*args, **kwargs)


def ticker_inspection(*args, **kwargs):
    from mide import news_provider
    return news_provider.ticker_inspection(*args, **kwargs)


__all__ = [
    "early_open_market_now",
    "early_open_inside_window",
    "early_open_prefilter_decision",
    "install_early_open_ignition_admission",
    "install_news_corroborated_shadow_rvol",
    "merge_news_corroborated_shadow_rvol",
    "eligible_shadow_rvol_rows",
    "shadow_rvol_rows",
    "fetch_shadow_rvol_targeted_articles",
    "SHADOW_RVOL_AUTHORITY",
    "SHADOW_RVOL_LIMIT",
    "SHADOW_RVOL_MIN",
    "install_benzinga_breaking_news_discovery",
    "merge_benzinga_breaking_news_discovery",
    "poll_benzinga_breaking_news",
    "fetch_benzinga_delta",
    "normalize_benzinga_article",
    "benzinga_configured_token",
    "BENZINGA_AUTHORITY",
    "BENZINGA_ENDPOINT",
    "BENZINGA_HTTP_TIMEOUT_SECONDS",
    "MarketDataNewsProvider",
    "install_catalyst_story_news",
    "story_intelligence",
    "explicit_ticker_mentions",
    "STORY_FRESHNESS",
    "STORY_SEED_REASON",
    "STORY_SEED_TYPE",
    "STORY_TEXT_LIMIT",
    "AUTHORITY",
    "NewsService",
    "UnavailableNewsProvider",
    "build_seed_symbols",
    "index_news",
    "is_valid_us_symbol",
    "prefilter_snapshots",
    "snapshot_identity_records",
    "symbol_news_evidence",
    "ticker_inspection",
]
