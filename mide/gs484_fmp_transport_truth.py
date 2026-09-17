"""GS484: persist sanitized news-transport truth beside GS480/481 story evidence.

FR #85 proved GS480/481/482 observability is finally live, but every targeted symbol
(including PAAI) still reported ``article_found=False``.  That result is ambiguous
without the already-produced ``NewsService.metrics`` held in the live provider's
``diagnostics['news_coverage']``: an empty successful FMP response, a provider failure,
or a different provider path all collapse to the same story-level absence.

GS484 adds no provider request and changes no news selection or trading behavior.  It
wraps GS481's observational ``_news_truth`` helper so the active recorder also carries
bounded, credential-safe transport provenance: active provider, endpoints, request and
article counts, latency summary, requested-symbol coverage, newest returned article,
and sanitized failure classes/status codes.  Raw exception text, URLs, headers and
credentials are deliberately excluded.
"""
from __future__ import annotations

from functools import wraps
import re
from typing import Any

AUTHORITY = "OBSERVATIONAL_ONLY"
_OWNER = "_walter_gs484_fmp_transport_truth_owner"
MAX_SYMBOLS = 80
MAX_FAILURES = 5


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_failure(event: Any) -> dict:
    """Return failure classification without persisting raw exception/URL text."""
    item = event if isinstance(event, dict) else {}
    raw = str(item.get("exception") or "")
    exception_type = raw.split(":", 1)[0].strip() if raw else None
    status_match = re.search(r"\b([45]\d\d)\b", raw)
    affected = sorted({
        str(symbol).strip().upper()
        for symbol in item.get("affected_symbols") or []
        if str(symbol or "").strip()
    })
    return {
        "provider": str(item.get("provider") or "Unknown")[:120],
        "operation": str(item.get("operation") or "unknown")[:120],
        "exception_type": exception_type[:80] if exception_type else None,
        "http_status": int(status_match.group(1)) if status_match else None,
        "affected_symbol_count": len(affected),
        "recovery_action": str(item.get("recovery_action") or "")[:160] or None,
        "raw_exception_persisted": False,
    }


def _latest_article_at(metrics: dict) -> str | None:
    newest = None
    for item in (metrics.get("newest_articles_by_symbol") or {}).values():
        if not isinstance(item, dict):
            continue
        stamp = item.get("newest_article_at")
        if stamp and (newest is None or str(stamp) > str(newest)):
            newest = str(stamp)
    return newest


def transport_truth(provider) -> dict:
    diagnostics = getattr(provider, "diagnostics", None)
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    metrics = diagnostics.get("news_coverage")
    metrics = metrics if isinstance(metrics, dict) else {}

    active_provider = str(metrics.get("active_provider") or "None")
    request_latencies = [
        value for raw in metrics.get("request_latency_ms") or []
        if (value := _float(raw)) is not None
    ]
    requested = sorted({
        str(symbol).strip().upper()
        for symbol in metrics.get("requested_symbols") or []
        if str(symbol or "").strip()
    })
    with_articles = sorted({
        str(symbol).strip().upper()
        for symbol in metrics.get("symbols_with_articles") or []
        if str(symbol or "").strip()
    })
    without_articles = sorted({
        str(symbol).strip().upper()
        for symbol in metrics.get("symbols_without_articles") or []
        if str(symbol or "").strip()
    })
    failure_events = list(metrics.get("provider_failure_diagnostics") or [])
    provider_failures = _int(metrics.get("provider_failures"))
    if failure_events:
        provider_failures = max(provider_failures, len(failure_events))

    requests_made = _int(metrics.get("requests_made"))
    articles_received = _int(metrics.get("articles_received"))
    if active_provider != "None":
        disposition = "SUCCESS_WITH_ARTICLES" if articles_received else "SUCCESS_EMPTY"
    elif provider_failures:
        disposition = "PROVIDER_FAILURE"
    elif requests_made:
        disposition = "NO_ACTIVE_PROVIDER"
    else:
        disposition = "NOT_OBSERVED"

    return {
        "authority": AUTHORITY,
        "metrics_present": bool(metrics),
        "active_provider": active_provider,
        "fmp_active": active_provider == "Financial Modeling Prep news",
        "transport_disposition": disposition,
        "query_since": metrics.get("query_since"),
        "effective_provider_since": metrics.get("effective_provider_since"),
        "provider_endpoints": [str(value)[:120] for value in metrics.get("provider_endpoints") or []],
        "requests_made": requests_made,
        "articles_received": articles_received,
        "provider_failure_count": provider_failures,
        "request_latency_last_ms": request_latencies[-1] if request_latencies else None,
        "request_latency_max_ms": max(request_latencies) if request_latencies else None,
        "last_successful_fetch": metrics.get("last_successful_fetch"),
        "newest_returned_article_at": _latest_article_at(metrics),
        "requested_symbol_count": len(requested),
        "requested_symbols": requested[:MAX_SYMBOLS],
        "symbols_with_articles_count": len(with_articles),
        "symbols_with_articles": with_articles[:MAX_SYMBOLS],
        "symbols_without_articles_count": len(without_articles),
        "symbols_without_articles": without_articles[:MAX_SYMBOLS],
        "failure_tail": [_safe_failure(item) for item in failure_events[-MAX_FAILURES:]],
        "raw_failure_text_persisted": False,
        "extra_provider_calls": 0,
        "trading_authority_changed": False,
    }


def install() -> None:
    """Enrich GS481's already-hard-bound news trace with transport provenance."""
    from . import gs427_flight_recorder_latency_hard_bind as gs427
    from . import gs481_live_evidence_hard_bind as gs481

    current = gs481._news_truth
    if getattr(current, _OWNER, False):
        return

    @wraps(current)
    def news_truth_with_transport(*args, **kwargs):
        truth = dict(current(*args, **kwargs) or {})
        provider, provider_source = gs427._active_provider()
        transport = transport_truth(provider)
        transport["provider_source"] = provider_source
        truth["transport"] = transport
        truth["gs484_transport_truth"] = True
        return truth

    setattr(news_truth_with_transport, _OWNER, True)
    news_truth_with_transport._gs484_fmp_transport_truth = True
    news_truth_with_transport._gs484_original = current
    gs481._news_truth = news_truth_with_transport
