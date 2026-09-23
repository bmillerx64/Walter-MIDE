"""GS540: corroborate Webull shadow-RVOL ignition with already-public material news.

Sept. 23 HCTI exposed a bounded discovery gap. Walter saw HCTI at Webull RVOL rank
37 before the open, but GS523 deliberately kept RVOL page 2 shadow-only. Walter also
had access to a material acquisition article through its entitled FMP stock-news
provider, yet the two independent facts were never joined until price/volume later
pushed HCTI into the production universe.

GS540 joins only those two existing evidence lanes:
* at most the 20 Webull RVOL page-2 shadow symbols already sampled by GS523;
* one targeted, bounded FMP stock-news lookup for those symbols; and
* only an existing GS298 material-positive catalyst may corroborate admission.

The result adds symbol identity to discovery only. Every promoted symbol must still
pass Walter's normal Webull snapshot, validity, float, participation, expansion,
Mission Ranking, readiness, trigger, anti-chase and execution safeguards.

This does not attempt to reproduce Webull Desktop's proprietary article feed or clock.
It records Walter's actual source/provider/published timestamp so source discrepancies
remain visible instead of being silently normalized into "Webull time."
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Callable, Iterable

UTC = timezone.utc
AUTHORITY = "DISCOVERY_IDENTITY_ONLY_NEWS_CORROBORATED_SHADOW_RVOL"
SHADOW_LIMIT = 20
MIN_SHADOW_RVOL = 2.0
NEWS_LOOKBACK = timedelta(hours=6)
_OWNER = "_walter_gs540_news_corroborated_shadow_rvol_owner"


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _now_utc(now=None) -> datetime:
    value = now() if callable(now) else now
    value = value or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def shadow_rvol_rows(client) -> list[dict]:
    """Return the already-fetched GS523 page-2 RVOL evidence; make no provider call."""
    diagnostics = getattr(client, "diagnostics", None)
    if not isinstance(diagnostics, dict):
        return []
    native = diagnostics.get("webull_native_discovery") or {}
    shadow = native.get("shadow_discovery") or {}
    page = shadow.get("relative_volume_page2") or {}
    rows = page.get("rows") or []
    return [dict(row) for row in rows if isinstance(row, dict)][:SHADOW_LIMIT]


def eligible_shadow_rows(rows: Iterable[dict]) -> list[dict]:
    """Keep only positive/neutral directional RVOL anomalies with meaningful RVOL."""
    output = []
    seen = set()
    for raw in rows or []:
        row = dict(raw)
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol or symbol in seen:
            continue
        rvol = _number(row.get("relative_volume_10d"))
        change = _number(row.get("change_ratio"))
        price = _number(row.get("price"))
        if rvol is None or rvol < MIN_SHADOW_RVOL:
            continue
        if change is not None and change < 0:
            continue
        if price is not None and price <= 0:
            continue
        seen.add(symbol)
        row["symbol"] = symbol
        output.append(row)
    return output[:SHADOW_LIMIT]


def _fetch_targeted_articles(symbols: list[str], *, now: datetime) -> list:
    """Make one bounded entitlement-safe FMP stock-news fetch for shadow symbols."""
    from .news_provider import FMPNewsProvider, _configured_fmp_api_key

    key = _configured_fmp_api_key()
    if not key or not symbols:
        return []
    provider = FMPNewsProvider(key, timeout=4, now=lambda: now)
    return provider.fetch(since=now - NEWS_LOOKBACK, symbols=symbols)


def merge_news_corroborated_shadow_rvol(
    client,
    seeds: list[str],
    reasons: dict[str, list[str]],
    *,
    now=None,
    fetcher: Callable[[list[str], datetime], list] | None = None,
) -> tuple[list[str], dict[str, list[str]], dict]:
    """Join shadow RVOL with material news without bypassing downstream gates."""
    current = _now_utc(now)
    rows = eligible_shadow_rows(shadow_rvol_rows(client))
    shadow_by_symbol = {row["symbol"]: row for row in rows}
    symbols = list(shadow_by_symbol)

    output = list(seeds or [])
    updated_reasons = {
        str(symbol): list(values)
        for symbol, values in (reasons or {}).items()
    }
    existing = {str(symbol or "").strip().upper() for symbol in output}

    trace = {
        "authority": AUTHORITY,
        "shadow_rows_seen": len(shadow_rvol_rows(client)),
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
            from .news_provider import _configured_fmp_api_key
            configured = bool(_configured_fmp_api_key())
            trace["configured"] = configured
            if not configured:
                trace["reason"] = "FMP credential unavailable"
                return output, updated_reasons, trace
            trace["request_made"] = True
            articles = _fetch_targeted_articles(symbols, now=current)
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
    from . import gs298_news_seeded_discovery as gs298

    selected = gs298.select_material_news_seeds(
        articles,
        now=current,
        limit=SHADOW_LIMIT,
    )
    selected = [
        item for item in selected
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
            + (evidence["news_source"] or evidence["news_provider"] or "news provider")
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


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Wrap the final discovery seam after GS502/503 news context is installed."""
    from . import discovery

    current = discovery.build_seed_symbols
    if getattr(current, _OWNER, False):
        return

    @wraps(current)
    def build_seed_symbols(client, settings, news_items, *, universe_verification=None):
        if universe_verification is None:
            seeds, reasons = current(client, settings, news_items)
        else:
            seeds, reasons = current(
                client,
                settings,
                news_items,
                universe_verification=universe_verification,
            )

        seeds, reasons, trace = merge_news_corroborated_shadow_rvol(
            client, seeds, reasons
        )
        diagnostics = getattr(client, "diagnostics", None)
        if isinstance(diagnostics, dict):
            diagnostics["news_corroborated_shadow_rvol"] = deepcopy(trace)
            diagnostics["final_seed_count"] = len(seeds)
        return seeds, reasons

    _inherit(build_seed_symbols, current)
    build_seed_symbols._gs540_news_corroborated_shadow_rvol = True
    build_seed_symbols._gs540_original = current
    setattr(build_seed_symbols, _OWNER, True)
    discovery.build_seed_symbols = build_seed_symbols
