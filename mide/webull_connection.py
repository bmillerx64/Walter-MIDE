"""Deployed, credentialed Webull validation used by Diagnostics.

Live Webull refreshes REST snapshots on every explicit scan and obtains its live
symbol universe from Webull's native market-attention feeds. There is no runtime
fallback to an Alpaca symbol master in the Live Webull discovery operation.
"""

from __future__ import annotations

from time import perf_counter
from typing import Callable, Iterable

from .webull_sdk import SNAPSHOT_OPERATION
from .webull_live import LiveWebullProvider
from .webull_native_radar import RADAR_FEEDS, fetch_native_radar, radar_probe_rows


_ORIGINAL_LIVE_WEBULL_SNAPSHOTS = LiveWebullProvider.snapshots
_ORIGINAL_LIVE_WEBULL_PIPELINE_SOURCES = LiveWebullProvider.pipeline_sources


def _merge_snapshot_continuity(previous: dict, current: dict) -> dict:
    merged = dict(previous or {})
    merged.update(current or {})
    for section in ("latestTrade", "latestQuote", "dailyBar", "prevDailyBar"):
        old_values = (previous or {}).get(section) or {}
        new_values = (current or {}).get(section) or {}
        values = dict(old_values)
        for key, value in new_values.items():
            if value is not None:
                values[key] = value
        if values:
            merged[section] = values
    return merged


def _fresh_live_webull_snapshots(self: LiveWebullProvider, symbols: Iterable[str]) -> dict:
    wanted = list(dict.fromkeys(
        str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()
    ))
    if wanted and not getattr(self, "_enable_streaming", False):
        with self._lock:
            previous = {symbol: dict(self._snapshot_cache.get(symbol, {})) for symbol in wanted}
        self.initialize_quotes(wanted)
        preserved = 0
        with self._lock:
            for symbol in wanted:
                old = previous.get(symbol) or {}
                fresh = self._snapshot_cache.get(symbol) or {}
                if not old or not fresh:
                    continue
                merged = _merge_snapshot_continuity(old, fresh)
                if merged != fresh:
                    preserved += 1
                    self._snapshot_cache[symbol] = merged
        diagnostics = self.diagnostics.setdefault("webull_stream", {})
        diagnostics["snapshot_refresh_mode"] = "rest_each_scan_with_continuity"
        diagnostics["snapshot_refresh_symbols"] = len(wanted)
        diagnostics["snapshot_continuity_preserved_symbols"] = preserved
    return _ORIGINAL_LIVE_WEBULL_SNAPSHOTS(self, wanted)


if not getattr(LiveWebullProvider.snapshots, "_walter_fresh_each_scan", False):
    _fresh_live_webull_snapshots._walter_fresh_each_scan = True
    LiveWebullProvider.snapshots = _fresh_live_webull_snapshots


def _webull_native_assets(self: LiveWebullProvider) -> list[dict]:
    """Return Webull's rotating native attention universe, fail-closed."""
    report = fetch_native_radar(self)
    feeds = report.get("feeds", {})
    failed = [
        f"{name}: {feed.get('error') or 'unavailable'}"
        for name, feed in feeds.items()
        if feed.get("status") != "PASS"
    ]
    if failed:
        raise RuntimeError("Webull native discovery unavailable — " + "; ".join(failed))

    assets = []
    for item in report.get("symbols", []):
        symbol = str(item.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        assets.append({
            "symbol": symbol,
            "name": item.get("name") or "",
            "tradable": True,
            "status": "active",
            "exchange": item.get("exchange") or "",
            "otc": False,
            "webull_native_sources": list(item.get("sources") or []),
            "webull_native_ranks": dict(item.get("ranks") or {}),
        })
    if not assets:
        raise RuntimeError("Webull native discovery returned zero symbols after deduplication")

    diagnostics = self.diagnostics.setdefault("webull_native_discovery", {})
    diagnostics.update({
        "provider": "Webull OpenAPI SDK",
        "mode": "native_market_attention",
        "alpaca_universe_used": False,
        "feed_count": len(feeds),
        "unique_symbols": len(assets),
        "feed_status": {
            name: {"status": feed.get("status"), "returned": len(feed.get("rows") or []),
                   "error": feed.get("error") or ""}
            for name, feed in feeds.items()
        },
    })
    self.diagnostics["broad_source"] = "Webull native market attention"
    self.diagnostics.setdefault("market_data_sources", {})["universe_provider"] = (
        "Webull OpenAPI SDK native radar"
    )
    self._walter_native_universe_active = True
    return assets


_webull_native_assets._walter_webull_native_discovery = True
LiveWebullProvider.assets = _webull_native_assets


def _native_pipeline_rows() -> list[dict[str, str]]:
    return [
        {
            "Stage": "Universe (market attention)",
            "Actual provider": "Webull OpenAPI SDK",
            "Endpoint / operation": "screener.get_gainers_losers + screener.get_most_active",
            "Code path": "build_seed_symbols → LiveWebullProvider.assets → Webull native radar",
            "Alpaca used": "No",
        },
        {
            "Stage": "Quote / snapshot retrieval",
            "Actual provider": "Webull OpenAPI SDK",
            "Endpoint / operation": SNAPSHOT_OPERATION + " (≤100 symbols; US_STOCK)",
            "Code path": "LiveWebullProvider.initialize_quotes → WebullOpenAPIClient.snapshots",
            "Alpaca used": "No",
        },
        {
            "Stage": "Streaming quotes", "Actual provider": "Webull OpenAPI SDK",
            "Endpoint / operation": "Official SDK market-data stream",
            "Code path": "LiveWebullProvider.ensure_stream → official SDK stream", "Alpaca used": "No",
        },
        {
            "Stage": "News", "Actual provider": "None (provider abstraction)",
            "Endpoint / operation": "No raw Webull article feed in current pipeline",
            "Code path": "NewsService → provider abstraction", "Alpaca used": "No",
        },
        {
            "Stage": "VWAP / volume calculations",
            "Actual provider": "Webull OpenAPI SDK + Walter local calculations",
            "Endpoint / operation": "SDK stock bars; Walter session calculations",
            "Code path": "analyze_candidates → LiveWebullProvider.bars", "Alpaca used": "No",
        },
        {
            "Stage": "Scanning / filtering", "Actual provider": "Walter local pipeline",
            "Endpoint / operation": "In-process gates, scoring, ranking, and filtering",
            "Code path": "WalterArchitectureV1.run → Walter analysis", "Alpaca used": "No",
        },
    ]


def _webull_native_pipeline_sources(self: LiveWebullProvider) -> list[dict[str, str]]:
    """Show native provenance after the native discovery call has actually run."""
    if not getattr(self, "_walter_native_universe_active", False):
        return _ORIGINAL_LIVE_WEBULL_PIPELINE_SOURCES(self)
    return _native_pipeline_rows()


LiveWebullProvider.pipeline_sources = _webull_native_pipeline_sources


def _radar_failure_rows(error: str, latency_ms: float) -> list[dict]:
    return [
        {"Test": f"Native radar — {feed.label}", "Status": "FAIL",
         "Provider": "Webull OpenAPI SDK", "Endpoint / SDK operation": f"screener.{feed.operation}",
         "Request count": 0, "Returned symbol count": 0, "First 10 returned symbols": "",
         "Latency ms": latency_ms, "Actual exception / API error": error}
        for feed in RADAR_FEEDS
    ]


def run_connection_test(*, app_key: str, app_secret: str,
                        eligible_symbols: Iterable[str], client_factory: Callable) -> list[dict]:
    symbols = list(dict.fromkeys(str(s).strip().upper() for s in eligible_symbols if str(s).strip()))
    rows = []

    def result(name, started, *, requested=0, returned=(), error=""):
        returned = sorted(returned)
        rows.append({
            "Test": name, "Status": "FAIL" if error else "PASS",
            "Provider": "Webull OpenAPI SDK", "Endpoint / SDK operation": SNAPSHOT_OPERATION,
            "Request count": (requested + 99) // 100 if requested else 0,
            "Returned symbol count": len(returned), "First 10 returned symbols": ", ".join(returned[:10]),
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

    cases = [("HYFM snapshot", ["HYFM"]), ("10-symbol batch", symbols[:10]),
             ("100-symbol batch", symbols[:100]), ("Full eligible-universe batching", symbols)]
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

    radar_started = perf_counter()
    try:
        radar_report = fetch_native_radar(client)
        radar_rows = radar_probe_rows(radar_report)
    except Exception as exc:
        latency_ms = round((perf_counter() - radar_started) * 1000, 2)
        radar_rows = _radar_failure_rows(f"{type(exc).__name__}: {exc}", latency_ms)
    else:
        latency_ms = round((perf_counter() - radar_started) * 1000, 2)
        for radar_row in radar_rows:
            radar_row["Latency ms"] = latency_ms
    rows.extend(radar_rows)
    return rows
