from __future__ import annotations

from copy import deepcopy

from mide import flight_recorder, runtime_evidence
from mide import gs386_30s_observational_recorder as gs386


class _Provider:
    def __init__(self, bars):
        self._bars = bars
        self.diagnostics = {"webull_stream": {}}

    def stream_30s_bars(self, symbol):
        return [dict(row) for row in self._bars.get(symbol, [])]


def _bars(count=12, *, start=1_780_000_000_000):
    rows = []
    price = 1.0
    for index in range(count):
        price += 0.01
        rows.append(
            {
                "t": start + index * 30_000,
                "o": price - 0.004,
                "h": price + 0.006,
                "l": price - 0.008,
                "c": price,
                "v": 100 + index,
                "trade_count": 3 + index,
            }
        )
    return rows


def test_observational_export_records_closed_bars_and_existing_supertrend_only():
    provider = _Provider({"TEST": _bars(12)})

    payload = gs386.build_observational_30s(provider, ["TEST"])

    assert payload["authority"] == "OBSERVATIONAL_ONLY"
    assert payload["source"] == "Webull OpenAPI TICK"
    assert payload["bar_interval_seconds"] == 30
    assert payload["supertrend"] == {"period": 10, "multiplier": 3.0}
    assert payload["new_bar_count"] == 12
    assert payload["symbol_count"] == 1
    rows = payload["symbols"][0]["bars"]
    assert len(rows) == 12
    assert rows[-1]["supertrend_ready"] is True
    assert rows[-1]["supertrend_state"] in {"bullish", "bearish"}
    assert rows[-1]["supertrend_10_3"] is not None


def test_observational_export_is_incremental_and_does_not_duplicate_old_bars():
    bars = _bars(12)
    provider = _Provider({"TEST": bars})

    first = gs386.build_observational_30s(provider, ["TEST"])
    second = gs386.build_observational_30s(provider, ["TEST"])
    provider._bars["TEST"].append(
        {
            "t": bars[-1]["t"] + 30_000,
            "o": 1.12,
            "h": 1.14,
            "l": 1.11,
            "c": 1.13,
            "v": 250,
            "trade_count": 9,
        }
    )
    third = gs386.build_observational_30s(provider, ["TEST"])

    assert first["new_bar_count"] == 12
    assert second["new_bar_count"] == 0
    assert third["new_bar_count"] == 1
    assert third["symbols"][0]["bars"][0]["timestamp_ms"] == bars[-1]["t"] + 30_000


def test_current_scan_download_retains_observational_30s_payload():
    observational = {
        "authority": "OBSERVATIONAL_ONLY",
        "source": "Webull OpenAPI TICK",
        "new_bar_count": 1,
        "symbols": [{"symbol": "TEST", "bars": [{"timestamp_ms": 123}]}],
    }
    scan = {
        "scan_id": "scan-1",
        "timestamp": "2026-09-08T14:30:00+00:00",
        "symbols": [{"symbol": "TEST", "evidence": {"symbol": "TEST"}}],
        "observational_30s": observational,
    }

    exported = runtime_evidence.current_scan_export(scan)

    assert exported["observational_30s"] == observational
    assert exported["records"] == [{"symbol": "TEST"}]


def test_gs386_installs_only_recorder_export_wrappers():
    assert getattr(
        flight_recorder.persist_replayable_scan,
        "_gs386_30s_observational",
        False,
    ) is True
    assert getattr(
        runtime_evidence.current_scan_export,
        "_gs386_30s_observational",
        False,
    ) is True


def test_build_does_not_mutate_provider_closed_bar_rows():
    original = _bars(12)
    provider = _Provider({"TEST": deepcopy(original)})

    gs386.build_observational_30s(provider, ["TEST"])

    assert provider._bars["TEST"] == original
