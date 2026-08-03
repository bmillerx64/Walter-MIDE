"""Deployed, credentialed Webull validation used by Diagnostics."""

from __future__ import annotations

from time import perf_counter
from typing import Callable, Iterable

from .webull_sdk import SNAPSHOT_OPERATION


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
