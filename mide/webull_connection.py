"""Deployed, credentialed Webull validation used by Diagnostics.

This module is imported immediately after ``mide.webull_live`` by the deployed
Streamlit app. Live Webull currently runs in snapshot-only mode, so an explicit
scan must refresh the REST snapshot instead of reusing the prior scan's cached
price/volume data. The compatibility patch also preserves last-known snapshot
fields when a later REST response is temporarily sparse.
"""

from __future__ import annotations

from time import perf_counter
from typing import Callable, Iterable

from .webull_sdk import SNAPSHOT_OPERATION
from .webull_live import LiveWebullProvider
from .webull_native_radar import fetch_native_radar, radar_probe_rows


_ORIGINAL_LIVE_WEBULL_SNAPSHOTS = LiveWebullProvider.snapshots


def _merge_snapshot_continuity(previous: dict, current: dict) -> dict:
    """Keep last-known values only where a fresh snapshot omitted them."""
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
    """Refresh every manual scan without letting sparse refreshes erase evidence.

    Webull can return a complete snapshot on one request and omit volume,
    previous-close, or quote fields on a later request. ``initialize_quotes``
    correctly refreshes live values, but replacing the whole snapshot with that
    sparse response can make every symbol fail the broad prefilter on the next
    scan. Preserve prior values only for fields the fresh response omitted; a
    real fresh value (including zero) always wins.
    """
    wanted = list(dict.fromkeys(
        str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()
    ))
    if wanted and not getattr(self, "_enable_streaming", False):
        with self._lock:
            previous = {
                symbol: dict(self._snapshot_cache.get(symbol, {}))
                for symbol in wanted
            }
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


def run_connection_test(*, app_key: str, app_secret: str,
                        eligible_symbols: Iterable[str], client_factory: Callable) -> list[dict]:
    """Exercise SDK initialization, snapshots, and Webull native-radar access."""
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

    # GS252: credentialed proof of the replacement discovery source. These four
    # calls are read-only and do not feed the current production funnel yet.
    radar_started = perf_counter()
    radar_report = fetch_native_radar(client)
    radar_rows = radar_probe_rows(radar_report)
    elapsed_ms = round((perf_counter() - radar_started) * 1000, 2)
    for radar_row in radar_rows:
        radar_row["Latency ms"] = elapsed_ms
        rows.append(radar_row)
    return rows
