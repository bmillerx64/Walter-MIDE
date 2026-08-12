"""Deployed, credentialed Webull validation used by Diagnostics.

This module is imported immediately after ``mide.webull_live`` by the deployed
Streamlit app.  Live Webull currently runs in snapshot-only mode, so an explicit
scan must refresh the REST snapshot instead of reusing the prior scan's cached
price/volume data.  The small compatibility patch below keeps streaming mode's
cache behavior unchanged while making snapshot-only scans genuinely live.
"""

from __future__ import annotations

from time import perf_counter
from typing import Callable, Iterable

from .webull_sdk import SNAPSHOT_OPERATION
from .webull_live import LiveWebullProvider


_ORIGINAL_LIVE_WEBULL_SNAPSHOTS = LiveWebullProvider.snapshots


def _fresh_live_webull_snapshots(self: LiveWebullProvider, symbols: Iterable[str]) -> dict:
    """Refresh REST market data for every manual scan in snapshot-only mode.

    ``LiveWebullProvider.snapshots`` historically refreshed only when a symbol
    was missing from the cache.  With streaming deliberately disabled in the
    deployed app, that made later scans reuse the first scan's intraday volume,
    price, bid/ask, and previous-close snapshot.  A cached 08:30 scan could
    therefore drive a 10:30 prefilter and collapse Walter's live funnel.

    Streaming mode is intentionally untouched: its cache is updated by live
    events and the original snapshot method remains authoritative there.
    """
    wanted = list(dict.fromkeys(
        str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()
    ))
    if wanted and not getattr(self, "_enable_streaming", False):
        self.initialize_quotes(wanted)
        diagnostics = self.diagnostics.setdefault("webull_stream", {})
        diagnostics["snapshot_refresh_mode"] = "rest_each_scan"
        diagnostics["snapshot_refresh_symbols"] = len(wanted)
    return _ORIGINAL_LIVE_WEBULL_SNAPSHOTS(self, wanted)


# Apply exactly once.  Streamlit hot reloads modules during deploys, and a guard
# avoids wrapping the method repeatedly inside the same process.
if not getattr(LiveWebullProvider.snapshots, "_walter_fresh_each_scan", False):
    _fresh_live_webull_snapshots._walter_fresh_each_scan = True
    LiveWebullProvider.snapshots = _fresh_live_webull_snapshots


def run_connection_test(*, app_key: str, app_secret: str,
                        eligible_symbols: Iterable[str], client_factory: Callable) -> list[dict]:
    """Exercise SDK initialization and all required snapshot batch shapes."""
    symbols = list(dict.fromkeys(str(s).strip().upper() for s in eligible_symbols if str(s).strip()))
    rows = []

    def result(name, started, *, requested=0, returned=(), error=""):
        returned = sorted(returned)
        rows.append({
            "Test": name, "Status": "FAIL" if error else "PASS",
            "Provider": "Webull OpenAPI SDK",
            "Endpoint / SDK operation": SNAPSHOT_OPERATION,
            "Request count": (requested + 99) // 100 if requested else 0,
            "Returned symbol count": len(returned),
            "First 10 returned symbols": ", ".join(returned[:10]),
            "Latency ms": round((perf_counter() - started) * 1000, 2),
            "Actual exception / API error": error,
        })

    started = perf_counter()
    if not app_key or not app_secret:
        result("Credential loading", started, error="WEBULL_APP_KEY or WEBULL_APP_SECRET is missing")
        return rows
    result("Credential loading", started)
    started = perf_counter()
    try:
        client = client_factory(app_key, app_secret)
        result("SDK client initialization", started)
    except Exception as exc:
        result("SDK client initialization", started, error=f"{type(exc).__name__}: {exc}")
        return rows

    cases = [("HYFM snapshot", ["HYFM"]),
             ("10-symbol batch", symbols[:10]),
             ("100-symbol batch", symbols[:100]),
             ("Full eligible-universe batching", symbols)]
    for name, requested_symbols in cases:
        started = perf_counter()
        returned = {}
        try:
            for offset in range(0, len(requested_symbols), 100):
                returned.update(client.snapshots(requested_symbols[offset:offset + 100]))
            result(name, started, requested=len(requested_symbols), returned=returned)
        except Exception as exc:
            result(name, started, requested=len(requested_symbols), returned=returned,
                   error=f"{type(exc).__name__}: {exc}")
    return rows
