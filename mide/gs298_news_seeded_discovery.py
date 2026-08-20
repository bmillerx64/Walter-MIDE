"""GS298/GS306: let fresh FMP Stock News seed bounded Webull discovery.

Walter historically used news only after Webull had already surfaced a symbol. This
layer adds one entitlement-safe, market-wide FMP ``news/stock`` read before the
normal Webull pipeline finishes discovery.

There are deliberately two news-seed classes:

* material catalyst seeds: fresh positive company-specific news;
* morning-attention seeds: fresh roundup/watch-list/mover headlines that explicitly
  identify a symbol as already attracting market attention.

Morning-attention seeds receive no catalyst credit. Both seed classes add symbol
identity only: every symbol must still earn fresh Webull market-data evidence and
pass the same downstream price, validity, float, participation, expansion, ranking,
readiness, trigger, and execution rules as native discovery.

Reuters, Benzinga, and other publisher/source labels returned by FMP are preserved
verbatim on normalized articles and in discovery diagnostics.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

import requests

NEWS_SEED_REASON = "FMP material news seed"
MORNING_MOVER_SEED_REASON = "FMP morning mover attention seed"
NEWS_SEED_LIMIT = 20
NEWS_SEED_FRESHNESS = timedelta(hours=6)
NEWS_FEED_LIMIT = 100
UTC = timezone.utc

# These phrases are intentionally about *attention*, not catalyst quality. They
# cover the premarket/morning roundup language visible in feeds such as Benzinga,
# Reuters syndication, and TipRanks-style mover/watch-list stories. Matching one
# of these patterns only allows a symbol into discovery; it never awards catalyst
# points or bypasses downstream scanner gates.
_MORNING_MOVER_PHRASES = (
    "stocks moving in",
    "stocks moving premarket",
    "stocks moving pre-market",
    "stocks on the move",
    "stocks to watch",
    "stocks on investors' radar",
    "stocks on investors radar",
    "penny stocks on investors' radar",
    "penny stocks on investors radar",
    "shares are trading higher",
    "stock is trading higher",
    "stocks are trading higher",
    "premarket gainers",
    "pre-market gainers",
    "after-hours gainers",
    "after hours gainers",
)


def _now_utc(now=None) -> datetime:
    value = now() if callable(now) else now
    value = value or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def morning_mover_attention_headline(headline: str) -> bool:
    """Return whether a headline is useful as a discovery/watch-list seed.

    This is intentionally broader than material catalyst classification and must
    never be interpreted as a positive catalyst score.
    """
    text = " ".join(str(headline or "").lower().split())
    if not text:
        return False
    if any(phrase in text for phrase in _MORNING_MOVER_PHRASES):
        return True
    # Common roundup constructions do not always use the exact phrases above.
    if "stocks" in text and ("premarket" in text or "pre-market" in text):
        if any(token in text for token in ("moving", "higher", "gainers", "watch")):
            return True
    if "why" in text and "trading higher" in text:
        return True
    return False


def fetch_marketwide_stock_news(
    api_key: str,
    *,
    now=None,
    session=None,
    timeout: int = 4,
    limit: int = NEWS_FEED_LIMIT,
):
    """Fetch the entitled FMP Stock News feed without a symbol restriction.

    This deliberately uses only ``news/stock``. It does not request Press
    Releases or any other endpoint outside the configured FMP entitlement.
    """
    from .news_provider import FMPNewsProvider

    key = str(api_key or "").strip()
    if not key:
        return []

    entitled = tuple(getattr(FMPNewsProvider, "ENTITLED_ENDPOINTS", ("news/stock",)))
    endpoint = "news/stock"
    if endpoint not in entitled:
        return []

    current = _now_utc(now)
    since = current - NEWS_SEED_FRESHNESS
    client = session or requests.Session()
    params = {
        "from": since.date().isoformat(),
        "to": current.date().isoformat(),
        "page": 0,
        "limit": max(1, min(int(limit), NEWS_FEED_LIMIT)),
        "apikey": key,
    }
    response = client.get(
        f"{FMPNewsProvider.BASE_URL}/{endpoint}",
        params=params,
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    rows = payload if isinstance(payload, list) else (
        payload.get("data", []) if isinstance(payload, dict) else []
    )

    articles = []
    for row in rows:
        article = FMPNewsProvider._normalize(row, endpoint=endpoint)
        if article is None:
            continue
        if since <= article.created_at <= current + timedelta(minutes=5):
            articles.append(article)
    return articles


def select_material_news_seeds(
    articles: Iterable,
    *,
    now=None,
    limit: int = NEWS_SEED_LIMIT,
) -> list[dict]:
    """Choose fresh material or morning-attention discovery seeds.

    The historical function name is retained for compatibility. ``seed_type``
    distinguishes company-specific material catalysts from roundup/watch-list
    attention. Morning-attention rows keep their real classifier score (usually
    zero) and therefore cannot masquerade as material catalyst evidence.
    """
    from .discovery import is_valid_us_symbol
    from .news import MATERIAL_CATALYST_SCORE, classify_headline, trusted_catalyst_source

    current = _now_utc(now)
    cutoff = current - NEWS_SEED_FRESHNESS
    by_symbol: dict[str, dict] = {}

    for article in articles or []:
        created = getattr(article, "created_at", None)
        if not isinstance(created, datetime):
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        created = created.astimezone(UTC)
        if created < cutoff or created > current + timedelta(minutes=5):
            continue

        headline = str(getattr(article, "headline", "") or "").strip()
        source = str(getattr(article, "source", "") or "").strip() or "FMP"
        score, flags = classify_headline(headline)
        material = float(score or 0) >= MATERIAL_CATALYST_SCORE
        attention = morning_mover_attention_headline(headline)
        if not material and not attention:
            continue
        seed_type = "material_catalyst" if material else "morning_mover_attention"

        for raw_symbol in getattr(article, "symbols", []) or []:
            symbol = str(raw_symbol or "").strip().upper()
            if not is_valid_us_symbol(symbol):
                continue
            candidate = {
                "symbol": symbol,
                "headline": headline,
                "source": source,
                "provider": str(getattr(article, "provider", "") or "Financial Modeling Prep"),
                "created_at": created,
                "age_minutes": round(max(0.0, (current - created).total_seconds()) / 60, 1),
                "catalyst_score": float(score or 0),
                "catalyst_flags": list(flags),
                "trusted_source": trusted_catalyst_source(source),
                "seed_type": seed_type,
                "attention_only": seed_type == "morning_mover_attention",
            }
            previous = by_symbol.get(symbol)
            # Prefer a material catalyst over an attention-only roundup when both
            # are fresh for the same symbol. Otherwise keep the newest evidence.
            if previous is None:
                by_symbol[symbol] = candidate
            elif candidate["seed_type"] == "material_catalyst" and previous.get("seed_type") != "material_catalyst":
                by_symbol[symbol] = candidate
            elif candidate["seed_type"] == previous.get("seed_type") and created > previous["created_at"]:
                by_symbol[symbol] = candidate

    ordered = sorted(
        by_symbol.values(),
        key=lambda item: (
            item["created_at"],
            item["seed_type"] == "material_catalyst",
            item["catalyst_score"],
            item["symbol"],
        ),
        reverse=True,
    )
    return ordered[: max(0, int(limit))]


def merge_news_seeds(
    seeds: list[str],
    reasons: dict[str, list[str]],
    selected: Iterable[dict],
) -> tuple[list[str], dict[str, list[str]], list[dict]]:
    """Merge symbol identity only; never attach stale market or decision evidence."""
    output = list(seeds)
    existing = {str(symbol or "").strip().upper() for symbol in output}
    added: list[dict] = []

    for item in selected or []:
        symbol = str(item.get("symbol") or "").strip().upper()
        if not symbol or symbol in existing:
            continue
        source = str(item.get("source") or "FMP").strip()
        reason = (
            MORNING_MOVER_SEED_REASON
            if item.get("seed_type") == "morning_mover_attention"
            else NEWS_SEED_REASON
        )
        output.append(symbol)
        existing.add(symbol)
        reasons.setdefault(symbol, []).append(f"{reason}: {source}")
        added.append(dict(item))
    return output, reasons, added


def _is_webull_client(client) -> bool:
    provider = str(getattr(client, "provider_name", "") or "").upper()
    class_name = client.__class__.__name__.upper()
    return "WEBULL" in provider or "WEBULL" in class_name


def install() -> None:
    """Wrap discovery after GS294 so native/recheck behavior remains unchanged."""
    from . import discovery
    from .news_provider import _configured_fmp_api_key

    original = discovery.build_seed_symbols
    if getattr(original, "_gs298_installed", False):
        return

    def build_seed_symbols(client, settings, news_items, *, universe_verification=None):
        if universe_verification is None:
            seeds, reasons = original(client, settings, news_items)
        else:
            seeds, reasons = original(
                client,
                settings,
                news_items,
                universe_verification=universe_verification,
            )

        if not _is_webull_client(client):
            return seeds, reasons

        diagnostics = getattr(client, "diagnostics", None)
        key = _configured_fmp_api_key()
        if not key:
            if isinstance(diagnostics, dict):
                diagnostics["news_seeded_discovery"] = {
                    "active": False,
                    "reason": "FMP credential unavailable",
                    "endpoint": "news/stock",
                    "symbols_added": [],
                    "count": 0,
                }
            return seeds, reasons

        try:
            articles = fetch_marketwide_stock_news(key)
            selected = select_material_news_seeds(articles)
            seeds, reasons, added = merge_news_seeds(seeds, reasons, selected)
            if isinstance(diagnostics, dict):
                material_added = [item for item in added if item.get("seed_type") == "material_catalyst"]
                attention_added = [item for item in added if item.get("seed_type") == "morning_mover_attention"]
                diagnostics["news_symbols"] = len(added)
                diagnostics["final_seed_count"] = len(seeds)
                diagnostics["news_seeded_discovery"] = {
                    "active": True,
                    "endpoint": "news/stock",
                    "freshness_hours": int(NEWS_SEED_FRESHNESS.total_seconds() // 3600),
                    "feed_articles_received": len(articles),
                    "material_symbols_considered": sum(
                        item.get("seed_type") == "material_catalyst" for item in selected
                    ),
                    "attention_symbols_considered": sum(
                        item.get("seed_type") == "morning_mover_attention" for item in selected
                    ),
                    "symbols_added": [item["symbol"] for item in added],
                    "material_symbols_added": [item["symbol"] for item in material_added],
                    "morning_attention_symbols_added": [item["symbol"] for item in attention_added],
                    "count": len(added),
                    "evidence": [
                        {
                            "symbol": item["symbol"],
                            "source": item["source"],
                            "headline": item["headline"],
                            "age_minutes": item["age_minutes"],
                            "catalyst_score": item["catalyst_score"],
                            "catalyst_flags": list(item["catalyst_flags"]),
                            "trusted_source": item["trusted_source"],
                            "seed_type": item["seed_type"],
                            "attention_only": item["attention_only"],
                        }
                        for item in added
                    ],
                    "safety": "identity seed only; morning mover seeds receive no catalyst credit; all normal Webull/downstream gates still required",
                }
        except Exception as exc:
            # Discovery must remain available even if the auxiliary news seed read
            # fails. Never persist exception text because requests errors can echo
            # query strings containing credentials.
            if isinstance(diagnostics, dict):
                diagnostics["news_seeded_discovery"] = {
                    "active": False,
                    "endpoint": "news/stock",
                    "error_type": type(exc).__name__,
                    "symbols_added": [],
                    "count": 0,
                    "fallback": "native Webull discovery unchanged",
                }
        return seeds, reasons

    build_seed_symbols._gs298_installed = True
    build_seed_symbols._gs298_original = original
    discovery.build_seed_symbols = build_seed_symbols
