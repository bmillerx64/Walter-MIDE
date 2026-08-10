from datetime import datetime, timezone

import pytest

from mide.webull_live import WebullOpenAPIClient


def test_webull_history_bars_translate_to_sdk_2_signature_and_result_rows():
    calls = []

    class SDK:
        def get_history_bar(
            self,
            symbol,
            category,
            timespan,
            count="200",
            real_time_required=None,
            trading_sessions=None,
            start_time=None,
            end_time=None,
        ):
            calls.append({
                "symbol": symbol,
                "category": category,
                "timespan": timespan,
                "count": count,
                "real_time_required": real_time_required,
                "trading_sessions": trading_sessions,
                "start_time": start_time,
                "end_time": end_time,
            })
            return {
                "symbol": symbol,
                "result": [{
                    "time": "2026-08-10T15:30:00+00:00",
                    "open": "0.48",
                    "high": "0.52",
                    "low": "0.47",
                    "close": "0.51",
                    "volume": "250000",
                }],
            }

    client = WebullOpenAPIClient("key", "secret", sdk_client=SDK())
    result = client.bars(
        ["TEST"],
        start=datetime(2026, 8, 1, tzinfo=timezone.utc),
        timeframe="1Min",
        limit=10_000,
    )

    assert calls == [{
        "symbol": "TEST",
        "category": "US_STOCK",
        "timespan": "M1",
        "count": "1200",
        "real_time_required": True,
        "trading_sessions": "PRE,RTH,ATH",
        "start_time": 1785542400000,
        "end_time": None,
    }]
    assert result == {
        "TEST": [{
            "t": "2026-08-10T15:30:00+00:00",
            "o": 0.48,
            "h": 0.52,
            "l": 0.47,
            "c": 0.51,
            "v": 250000.0,
        }]
    }


def test_webull_30_second_history_is_explicitly_unsupported_without_fallback():
    calls = []

    class SDK:
        def get_batch_history_bar(self, *args, **kwargs):
            calls.append("batch")

        def get_history_bar(self, *args, **kwargs):
            calls.append("single")

    client = WebullOpenAPIClient("key", "secret", sdk_client=SDK())
    with pytest.raises(ValueError, match="do not support 30-second"):
        client.bars(
            [f"SYM{index}" for index in range(41)],
            start=datetime(2026, 8, 1, tzinfo=timezone.utc),
            timeframe="30Sec",
        )

    assert calls == []


def test_multiple_symbols_use_batch_history_and_group_rows():
    batch_calls = []

    class SDK:
        def get_batch_history_bar(self, **kwargs):
            batch_calls.append(kwargs)
            return {"data": [
                {"symbol": "AAA", "bars": [{"timestamp": 1, "open": "1", "high": "2",
                                               "low": ".5", "close": "1.5", "volume": "10"}]},
                {"symbol": "BBB", "bars": [{"time": 2, "o": 3, "h": 4, "l": 2,
                                               "c": 3.5, "v": 20}]},
            ]}

        def get_history_bar(self, **kwargs):
            raise AssertionError("successful batch must not make single-symbol calls")

    result = WebullOpenAPIClient("k", "s", sdk_client=SDK()).bars(
        ["aaa", "BBB"], start=datetime(2026, 8, 1, tzinfo=timezone.utc), limit=5000
    )

    assert len(batch_calls) == 1
    assert batch_calls[0]["symbols"] == ["AAA", "BBB"]
    assert batch_calls[0]["trading_sessions"] == "PRE,RTH,ATH"
    assert "OVN" not in batch_calls[0]["trading_sessions"]
    assert batch_calls[0]["count"] == "1200"
    assert result == {
        "AAA": [{"t": 1, "o": 1.0, "h": 2.0, "l": .5, "c": 1.5, "v": 10.0}],
        "BBB": [{"t": 2, "o": 3.0, "h": 4.0, "l": 2.0, "c": 3.5, "v": 20.0}],
    }


def test_invalid_symbol_batch_failure_isolated_without_aborting_good_symbols(monkeypatch):
    single_calls = []
    sleeps = []

    class SDK:
        def get_batch_history_bar(self, symbols, **kwargs):
            if "BAD" in symbols:
                raise RuntimeError("HTTP 417 INVALID_SYMBOL")
            return {"data": [{"symbol": symbol, "bars": [{"time": symbol, "close": 1}]}
                             for symbol in symbols]}

        def get_history_bar(self, **kwargs):
            single_calls.append(kwargs)
            raise RuntimeError("HTTP 417 INVALID_SYMBOL")

    import mide.webull_sdk as sdk_module
    clock = {"now": 100.0}
    monkeypatch.setattr(sdk_module.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(sdk_module.time, "sleep", lambda delay: sleeps.append(delay))
    monkeypatch.setattr(sdk_module, "_HISTORY_BAR_LAST_CALL", 99.5)

    result = WebullOpenAPIClient("k", "s", sdk_client=SDK()).bars(
        ["GOOD", "BAD", "ALSO"], start=datetime(2026, 8, 1, tzinfo=timezone.utc)
    )

    assert set(result) == {"GOOD", "BAD", "ALSO"}
    assert result["GOOD"][0]["t"] == "GOOD"
    assert result["ALSO"][0]["t"] == "ALSO"
    assert result["BAD"] == []
    assert [call["symbol"] for call in single_calls] == ["BAD"]
    assert sleeps == [pytest.approx(.55)]


def test_unavailable_or_undecodable_batch_falls_back_to_single_history():
    calls = []

    class SDK:
        def get_history_bar(self, **kwargs):
            calls.append(kwargs["symbol"])
            return {"result": [{"time": kwargs["symbol"], "close": 1}]}

    result = WebullOpenAPIClient("k", "s", sdk_client=SDK()).bars(
        ["AAA", "BBB"], start=datetime(2026, 8, 1, tzinfo=timezone.utc)
    )

    assert calls == ["AAA", "BBB"]
    assert set(result) == {"AAA", "BBB"}


def test_batch_history_splits_41_symbols_into_legal_consecutive_batches():
    batch_calls = []

    class SDK:
        def get_batch_history_bar(self, symbols, **kwargs):
            batch_calls.append(list(symbols))
            return {"data": [
                {"symbol": symbol, "bars": [{"time": symbol, "close": 1}]}
                for symbol in symbols
            ]}

        def get_history_bar(self, **kwargs):
            raise AssertionError("successful batches must not use single-symbol history")

    symbols = [f"SYM{index:02d}" for index in range(41)]
    result = WebullOpenAPIClient("k", "s", sdk_client=SDK()).bars(
        symbols, start=datetime(2026, 8, 1, tzinfo=timezone.utc)
    )

    assert [len(batch) for batch in batch_calls] == [20, 20, 1]
    assert batch_calls == [symbols[:20], symbols[20:40], symbols[40:]]
    assert max(map(len, batch_calls)) <= 20
    assert set(result) == set(symbols)
