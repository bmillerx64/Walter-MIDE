"""GS480: preserve story-level catalyst evidence and explicit cross-ticker truth.

Sep. 17 PAAI exposed two separate news gaps.  Walter could see PAAI in Webull long
before it had enough one-minute history to analyze it, while the Flight Recorder kept
no article-level news truth.  The FMP stock-news payload also carries a bounded story
text field that Walter previously discarded.  A story can therefore explicitly name a
second listed company (for example ``(NYSE: PAAI)``) while the provider's primary
symbol tag points at the issuer of the release.

GS480 keeps the existing FMP endpoint and request cadence.  It retains a bounded text
excerpt already present in the same response, recognizes only explicit exchange/ticker
forms (never naked capital words), catalogs high-signal corporate-event language and
number roles, and lets a trusted story-body event seed *attention identity only* when
the headline classifier is neutral.  Catalyst score, ranking, qualification, readiness,
anti-chase, alerts, execution and orders remain unchanged.

It also carries market-wide news into the later symbol-targeted catalyst stage when the
same already-fetched story explicitly names that symbol, and hard-binds news timing and
semantics into Flight Recorder so future runner studies can measure publication ->
Walter awareness -> usable market evidence.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from functools import wraps
import re
from typing import Any, Iterable

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
_WHY_OWNER = "_walter_gs480_story_why_owner"
_RECORDER_OWNER = "_walter_gs480_story_recorder_owner"

# Explicit forms only.  Do not treat arbitrary ALL-CAPS words as tickers.
_EXCHANGE_TICKER_RE = re.compile(
    r"(?:\(|\b)(?:NYSE(?:\s+American)?|NASDAQ|Nasdaq|NYSEAMERICAN|AMEX)\s*:\s*"
    r"(?P<symbol>[A-Z][A-Z0-9.-]{0,9})(?:\)|\b)",
)
_TICKER_LABEL_RE = re.compile(
    r"\b(?:ticker|ticker\s+symbol|symbol)\s*[:#-]?\s*(?P<symbol>[A-Z][A-Z0-9.-]{0,9})\b",
    re.IGNORECASE,
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
    from .discovery import is_valid_us_symbol

    value = str(text or "")
    found = []
    for pattern in (_EXCHANGE_TICKER_RE, _TICKER_LABEL_RE, _CASHTAG_RE):
        for match in pattern.finditer(value):
            symbol = str(match.group("symbol") or "").strip().upper()
            if is_valid_us_symbol(symbol) and symbol not in found:
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
    from .news_provider import FMPNewsProvider, NewsArticle, NewsService

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
    from . import gs298_news_seeded_discovery as gs298
    from .news import classify_headline, trusted_catalyst_source

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
            _LAST_SELECTED = deepcopy(selected[: max(0, int(limit))])
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
    from . import discovery

    current_build = discovery.build_seed_symbols
    if getattr(current_build, _BUILD_OWNER, False):
        return

    @wraps(current_build)
    def build(client, settings, news_items, *, universe_verification=None):
        global _LAST_SELECTED, _LATEST_MARKETWIDE_TRACE
        _LAST_SELECTED = []
        if universe_verification is None:
            result = current_build(client, settings, news_items)
        else:
            result = current_build(client, settings, news_items, universe_verification=universe_verification)
        seeds, _reasons = result
        diagnostics = getattr(client, "diagnostics", None)
        news_diag = diagnostics.get("news_seeded_discovery") if isinstance(diagnostics, dict) else None
        added = set(news_diag.get("symbols_added") or []) if isinstance(news_diag, dict) else set()
        trace = [_safe_selected(item, added=added) for item in _LAST_SELECTED]
        _LATEST_MARKETWIDE_TRACE = deepcopy(trace)
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
    from .news_provider import NewsService
    from . import news as news_module

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
                "marketwide_handoff": symbol in handoff_symbols or identity in handoff_ids,
            }
        _LATEST_TARGETED_TRACE = deepcopy(trace)
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
    from . import news as news_module
    from . import discovery

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


def _install_presentation() -> None:
    from . import ui

    current = ui._why_sections
    if getattr(current, _WHY_OWNER, False):
        return

    @wraps(current)
    def why_sections(record):
        sections = dict(current(record))
        context = record.get("catalyst_story") or {}
        categories = list(context.get("categories") or [])
        quantities = list(context.get("quantities") or [])
        facts = []
        if categories:
            readable = [category.replace("_", " ").title() for category in categories[:3]]
            facts.append("Story: " + " · ".join(readable))
        role_facts = []
        for item in quantities:
            role = str(item.get("role") or "")
            if role in {"DEAL_OR_BACKLOG", "REVENUE", "INVESTMENT_OR_FUNDING", "DILUTION_OR_FINANCING"}:
                role_facts.append(f"{item.get('text')} {role.replace('_', ' ').lower()}")
            if len(role_facts) >= 3:
                break
        if role_facts:
            facts.append(" · ".join(role_facts))
        if facts:
            existing = str(sections.get("Catalyst") or "").strip()
            addition = " · ".join(facts)
            if addition not in existing:
                sections["Catalyst"] = f"{existing} · {addition}" if existing else addition
        return sections

    _inherit(why_sections, current)
    setattr(why_sections, _WHY_OWNER, True)
    why_sections._gs480_original = current
    ui._why_sections = why_sections


def _recorder_wrapper(current):
    if not callable(current) or getattr(current, _RECORDER_OWNER, False):
        return current

    @wraps(current)
    def persist(self, scan, records):
        record_by_symbol = {
            str(item.get("symbol") or "").strip().upper(): item
            for item in records or [] if item.get("symbol")
        }
        for path in scan.get("symbols", []) if isinstance(scan, dict) else []:
            symbol = str(path.get("symbol") or "").strip().upper()
            evidence = path.setdefault("evidence", {})
            record = record_by_symbol.get(symbol) or {}
            targeted = _LATEST_TARGETED_TRACE.get(symbol) or {}
            headline = record.get("headline") or targeted.get("headline")
            if headline:
                evidence.update({
                    "news_headline": str(headline)[:500],
                    "news_created_at": record.get("news_created_at") or targeted.get("created_at"),
                    "news_age_seconds_at_scan": record.get("news_age_seconds_at_scan", targeted.get("age_seconds_at_scan")),
                    "news_source": record.get("news_source") or targeted.get("source"),
                    "news_provider": record.get("news_provider") or targeted.get("provider"),
                    "news_catalyst_score": record.get("catalyst_score", targeted.get("catalyst_score")),
                    "news_explicit_symbols": list(record.get("news_explicit_symbols") or targeted.get("explicit_symbols") or []),
                    "catalyst_story": deepcopy(record.get("catalyst_story") or targeted.get("story_context") or {}),
                    "news_marketwide_handoff": bool(record.get("news_marketwide_handoff", targeted.get("marketwide_handoff"))),
                })
        if isinstance(scan, dict):
            scan["news_trace"] = {
                "authority": AUTHORITY,
                "marketwide_selected": deepcopy(_LATEST_MARKETWIDE_TRACE),
                "targeted": deepcopy(list(_LATEST_TARGETED_TRACE.values())),
                "additional_provider_requests": 0,
            }
        return current(self, scan, records)

    setattr(persist, _RECORDER_OWNER, True)
    persist._gs480_original = current
    return persist


def _install_recorder_truth() -> None:
    from . import flight_recorder

    flight_recorder.persist_replayable_scan = _recorder_wrapper(
        flight_recorder.persist_replayable_scan
    )
    try:
        from . import gs427_flight_recorder_latency_hard_bind as gs427
        globals_dict = gs427._active_recorder_globals()
    except Exception:
        globals_dict = {}
    if isinstance(globals_dict, dict):
        active = globals_dict.get("persist_replayable_scan")
        wrapped = _recorder_wrapper(active)
        if callable(wrapped):
            globals_dict["persist_replayable_scan"] = wrapped


def install() -> None:
    """Install story intelligence after existing news/history and recorder hard binds."""
    _install_article_transport()
    _install_marketwide_selection()
    _install_discovery_diagnostics()
    _install_index_and_records()
    _install_targeted_handoff()
    _install_presentation()
    _install_recorder_truth()
