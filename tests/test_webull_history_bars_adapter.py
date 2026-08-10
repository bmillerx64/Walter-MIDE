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
        "trading_sessions": "PRE,RTH,ATH,OVN",
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


def test_webull_30_second_history_is_explicitly_unsupported():
    class SDK:
        def get_history_bar(self, *args, **kwargs):
            raise AssertionError("30-second request must fail before SDK invocation")

    client = WebullOpenAPIClient("key", "secret", sdk_client=SDK())
    with pytest.raises(ValueError, match="do not support 30-second"):
        client.bars(
            ["TEST"],
            start=datetime(2026, 8, 1, tzinfo=timezone.utc),
            timeframe="30Sec",
        )
