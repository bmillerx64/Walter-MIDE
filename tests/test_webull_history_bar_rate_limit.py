import pytest

import mide.webull_sdk as sdk_module
from mide.webull_sdk import WebullSDKClient


def test_history_bar_requests_are_rate_limited(monkeypatch):
    calls = []
    sleeps = []
    ticks = iter([100.0, 100.0, 100.0, 100.2, 100.2, 101.25])

    class SDK:
        def get_history_bar(self, **kwargs):
            calls.append(kwargs)
            return {"result": []}

    monkeypatch.setattr(sdk_module.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(sdk_module.time, "sleep", sleeps.append)
    monkeypatch.setattr(sdk_module, "_HISTORY_BAR_LAST_CALL", 0.0)

    client = WebullSDKClient("k", "s", sdk_client=SDK())
    client.bars(symbol="AAA", category="US_STOCK", interval="m1", count=200)
    client.bars(symbol="BBB", category="US_STOCK", interval="m1", count=200)

    assert calls[0]["timespan"] == "M1"
    assert calls[1]["timespan"] == "M1"
    assert sleeps == [pytest.approx(0.85)]


def test_invalid_history_symbol_does_not_abort_other_symbol_processing(caplog):
    class SDK:
        def get_history_bar(self, **kwargs):
            raise RuntimeError("HTTP 417 INVALID_SYMBOL")

    client = WebullSDKClient("k", "s", sdk_client=SDK())
    result = client.bars(
        symbol="BADADR", category="US_STOCK", interval="m1", count=200
    )

    assert result == {"data": []}
    assert "skipped invalid symbol symbol=BADADR" in caplog.text
