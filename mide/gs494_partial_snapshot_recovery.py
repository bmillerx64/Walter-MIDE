"""GS494: bounded recovery for partial Webull snapshot responses.

Sep. 18 FR #99 showed a broad live-data seam: Webull-native discovery could continue
finding active leaders (notably IMCC) while the snapshot stage later reported
"snapshot unavailable". Walter already batches official snapshot requests and already
falls back to current native-radar prices where available, but a partially successful
snapshot response is accepted as success and omitted symbols receive no dedicated
second chance.

GS494 wraps the exact retained LiveWebullProvider instance at app runtime. After the
existing initialize_quotes call succeeds, it compares requested supported symbols
with the prices actually returned. If any are absent, it makes exactly one bounded
retry through the *original* initialize_quotes method for only those omitted symbols.
Recovered live Webull snapshots are merged into the returned price map. Persistent
omissions remain unavailable and fail closed exactly as before.

No cached/stale price is manufactured here, no synthetic 30s source is added, and no
discovery, indicator, score, ranking, qualification, readiness, anti-chase, alert,
execution or order rule changes.
"""
from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Iterable

from .webull_live import webull_snapshot_symbol_supported

_OWNER = "_walter_gs494_partial_snapshot_recovery"
REVISION = 1


def _symbols(values: Iterable[str]) -> list[str]:
    return list(
        dict.fromkeys(
            str(value or "").strip().upper()
            for value in values or []
            if str(value or "").strip()
        )
    )


def initialize_quotes_with_partial_retry(
    original: Callable,
    provider,
    symbols: Iterable[str],
    *,
    batch_size: int,
):
    submitted = _symbols(symbols)
    wanted = [
        symbol for symbol in submitted if webull_snapshot_symbol_supported(symbol)
    ]

    first = original(submitted, batch_size=batch_size)
    if not isinstance(first, dict):
        return first

    missing = [symbol for symbol in wanted if symbol not in first]
    diagnostics = getattr(provider, "diagnostics", None)
    if not isinstance(diagnostics, dict):
        diagnostics = {}
        try:
            provider.diagnostics = diagnostics
        except Exception:
            pass
    stream = diagnostics.setdefault("webull_stream", {})
    trace = {
        "authority": "WEBULL_OFFICIAL_SNAPSHOT_PARTIAL_RETRY",
        "requested_symbols": len(wanted),
        "first_pass_returned": len([s for s in wanted if s in first]),
        "retry_attempted": bool(missing),
        "retry_requested": len(missing),
        "retry_recovered": 0,
        "unresolved_count": len(missing),
        "unresolved_symbols": list(missing),
        "extra_provider_requests_max": 1 if missing else 0,
        "stale_price_substitution": False,
        "trading_authority_changed": False,
    }
    stream["snapshot_partial_retry"] = trace

    if not missing:
        return first

    # The nested call deliberately targets the captured pre-GS494 method so this is
    # one retry only. It may use Walter's existing official REST + native-radar
    # completion logic, but can never recurse through this wrapper.
    previous_discovered = stream.get("discovered_symbols")
    try:
        retry = original(missing, batch_size=min(max(1, int(batch_size)), len(missing)))
    except Exception as exc:
        trace["retry_error_type"] = type(exc).__name__
        trace["unresolved_count"] = len(missing)
        trace["unresolved_symbols"] = list(missing)
        if previous_discovered is not None:
            stream["discovered_symbols"] = previous_discovered
        return first
    finally:
        if previous_discovered is not None:
            stream["discovered_symbols"] = previous_discovered

    retry = retry if isinstance(retry, dict) else {}
    recovered = {symbol: retry[symbol] for symbol in missing if symbol in retry}
    combined = dict(first)
    combined.update(recovered)
    unresolved = [symbol for symbol in missing if symbol not in recovered]
    trace.update(
        retry_recovered=len(recovered),
        unresolved_count=len(unresolved),
        unresolved_symbols=unresolved,
    )
    return combined


def install_for_provider(provider) -> bool:
    """Patch the exact retained provider instance used by this Streamlit session."""
    if provider is None:
        return False
    current = getattr(provider, "initialize_quotes", None)
    if not callable(current):
        return False
    function = getattr(current, "__func__", current)
    if (
        getattr(function, _OWNER, None) == REVISION
        or getattr(current, _OWNER, None) == REVISION
    ):
        return False

    @wraps(current)
    def initialize_quotes(symbols, *, batch_size=100):
        return initialize_quotes_with_partial_retry(
            current,
            provider,
            symbols,
            batch_size=batch_size,
        )

    setattr(initialize_quotes, _OWNER, REVISION)
    initialize_quotes._gs494_original = current
    try:
        provider.initialize_quotes = initialize_quotes
    except (AttributeError, TypeError):
        return False
    return True
