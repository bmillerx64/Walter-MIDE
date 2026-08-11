from datetime import datetime, timedelta, timezone

import pandas as pd

from mide.discovery import (
    CURRENT_SESSION_HISTORY_BARS,
    HISTORICAL_PROFILE_HISTORY_BARS,
    analyze_candidates,
    clear_history_profile_cache,
)
from mide.volume_pace import historical_volume_profile, volume_pace_metrics
from mide.webull_live import WebullOpenAPIClient


def _rows(day, count, *, close=2.0, volume=1_000):
    start = datetime(day.year, day.month, day.day, 13, 30, tzinfo=timezone.utc)
    return [
        {"t": start + timedelta(minutes=i), "o": close, "h": close + .02,
         "l": close - .02, "c": close + i / 10_000, "v": volume + i}
        for i in range(count)
    ]


class HistoryClient:
    provider_name = "test"

    def __init__(self):
        today = datetime.now(timezone.utc)
        self.history = sum((_rows(today - timedelta(days=day), 100)
                            for day in (8, 7, 6, 5, 4)), [])
        self.current = _rows(today, 100)
        self.calls = []

    def bars(self, symbols, *, start, timeframe, limit, **kwargs):
        self.calls.append((tuple(symbols), timeframe, limit, kwargs.get("end")))
        if timeframe == "30Sec":
            raise ValueError("unsupported")
        rows = self.history if kwargs.get("end") else self.current
        return {symbol: list(rows) for symbol in symbols}

    @staticmethod
    def bars_frame(rows):
        frame = pd.DataFrame(rows).rename(columns={
            "t": "timestamp", "o": "open", "h": "high", "l": "low",
            "c": "close", "v": "volume",
        })
        if frame.empty:
            return frame
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        return frame.set_index("timestamp")


def _candidate():
    return {"symbol": "AAA", "day_high": 3.0, "prev_volume": 500_000,
            "volume": 1_000_000, "price": 2.0, "pct_change": 8.0,
            "dollar_volume": 2_000_000, "spread_pct": .5}


def test_split_profile_is_equivalent_to_full_multi_session_frame():
    client = HistoryClient()
    history = client.bars_frame(client.history)
    current = client.bars_frame(client.current)
    full = pd.concat([history, current])
    expected = volume_pace_metrics("AAA", full)
    profile = historical_volume_profile("AAA", history, current.index[-1].date())
    actual = volume_pace_metrics("AAA", current, historical_profile=profile)

    assert actual == expected
    assert len({stamp.date() for stamp in history.index}) == 5


def test_analyze_reuses_bounded_profile_but_refreshes_current_session():
    client = HistoryClient()
    first = analyze_candidates(client, [_candidate()], {}, {})[0]
    historical_calls = [call for call in client.calls if call[3] is not None]
    assert len(historical_calls) == 1
    assert historical_calls[0][2] == HISTORICAL_PROFILE_HISTORY_BARS
    assert client.calls[0][2] == CURRENT_SESSION_HISTORY_BARS

    second = analyze_candidates(client, [_candidate()], {}, {})[0]

    assert len([call for call in client.calls if call[3] is not None]) == 1
    volatile = {"timestamp", "bar_age_seconds"}
    assert {key: value for key, value in second.items() if key not in volatile} == {
        key: value for key, value in first.items() if key not in volatile
    }

    client.current[-1]["c"] += .25
    client.current[-1]["h"] += .25
    refreshed = analyze_candidates(client, [_candidate()], {}, {})[0]
    assert refreshed["price"] != first["price"]
    assert len([call for call in client.calls if call[3] is not None]) == 1
    assert refreshed["expected_volume_by_time"] == first["expected_volume_by_time"]
    clear_history_profile_cache(client)
    assert not client._walter_history_profile_cache


def test_completed_profile_cache_has_a_hard_population_bound(monkeypatch):
    monkeypatch.setattr("mide.discovery.MAX_HISTORY_PROFILE_CACHE_ENTRIES", 2)
    client = HistoryClient()
    candidates = [
        {**_candidate(), "symbol": symbol} for symbol in ("AAA", "BBB", "CCC")
    ]

    analyze_candidates(client, candidates, {}, {})

    assert len(client._walter_history_profile_cache) == 2
    assert {key[1] for key in client._walter_history_profile_cache} == {"BBB", "CCC"}


def test_41_profile_misses_use_legal_batches_without_single_symbol_history():
    batch_calls = []
    single_calls = []
    today = datetime.now(timezone.utc)
    current_rows = _rows(today, 100)
    historical_rows = sum(
        (_rows(today - timedelta(days=day), 100) for day in (8, 7, 6, 5, 4)),
        [],
    )

    class SDK:
        def get_batch_history_bar(self, symbols, end_time=None, **kwargs):
            batch_calls.append((list(symbols), end_time))
            rows = historical_rows if end_time is not None else current_rows
            return {"data": [{"symbol": symbol, "bars": rows} for symbol in symbols]}

        def get_history_bar(self, **kwargs):
            single_calls.append(kwargs["symbol"])
            raise AssertionError("normal Stage-6 retrieval must stay on the batch path")

    client = WebullOpenAPIClient("k", "s", sdk_client=SDK())
    client.bars_frame = HistoryClient.bars_frame
    symbols = [f"SYM{index:02d}" for index in range(41)]
    candidates = [{**_candidate(), "symbol": symbol} for symbol in symbols]

    result = analyze_candidates(client, candidates, {}, {})

    historical_batches = [symbols for symbols, end in batch_calls if end is not None]
    assert [len(batch) for batch in historical_batches] == [20, 20, 1]
    assert single_calls == []
    assert client.history_call_diagnostics["single_fallback_calls"] == 0
    assert len(result) == 41
