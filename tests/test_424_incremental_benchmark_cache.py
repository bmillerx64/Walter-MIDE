from __future__ import annotations

from datetime import datetime, timezone

from mide import gs424_warm_scan_history_cache as gs424


class _Provider:
    def __init__(self):
        self.diagnostics = {}


def test_stage6_benchmark_uses_the_same_session_cache_contract():
    provider = _Provider()
    anchor = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)
    rows = [
        {"t": "2026-09-10T14:00:00+00:00", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1},
        {"t": "2026-09-10T14:01:00+00:00", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1},
    ]
    calls = []

    def original(_provider, symbols, **kwargs):
        calls.append(kwargs["start"])
        return {symbol: rows for symbol in symbols}

    kwargs = {
        "start": anchor,
        "timeframe": "1Min",
        "limit": 960,
        "force_batch": True,
        "history_reason": "stage6_benchmark",
    }
    gs424.cached_current_session_bars(provider, original, ["IWM"], **kwargs)
    gs424.cached_current_session_bars(provider, original, ["IWM"], **kwargs)

    assert calls[0] == anchor
    assert calls[1] > anchor
