from __future__ import annotations

from datetime import datetime, timezone

from mide import gs424_warm_scan_history_cache as gs424


class _Provider:
    def __init__(self):
        self.diagnostics = {}


def test_cache_diagnostics_report_seed_then_hit_without_trading_changes():
    provider = _Provider()
    anchor = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)
    rows = [{"t": "2026-09-10T14:00:00+00:00", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}]

    def original(_provider, symbols, **kwargs):
        return {symbol: rows for symbol in symbols}

    kwargs = {"start": anchor, "timeframe": "1Min", "limit": 960,
              "force_batch": True, "history_reason": "stage6_current_session"}
    gs424.cached_current_session_bars(provider, original, ["AAA"], **kwargs)
    gs424.cached_current_session_bars(provider, original, ["AAA"], **kwargs)

    diagnostic = provider.diagnostics["gs424_warm_scan_history_cache"]
    assert diagnostic["cache_hits"] == 1
    assert diagnostic["full_seed_symbols"] == 0
    assert diagnostic["market_data_values_changed"] is False
    assert diagnostic["trading_logic_changed"] is False
