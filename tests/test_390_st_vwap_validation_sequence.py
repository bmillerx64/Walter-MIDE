from copy import deepcopy
from datetime import datetime, timezone

from mide import flight_recorder, runtime_evidence
from mide import gs390_st_vwap_validation_sequence as gs390


class _Provider:
    def __init__(self, rows):
        self.rows = rows
        self.calls = 0

    def stream_30s_bars(self, symbol):
        assert symbol == "TEST"
        self.calls += 1
        return deepcopy(self.rows)


def _bars(start_ms: int, count: int = 14):
    rows = []
    for index in range(count):
        price = 0.90 + index * 0.01
        rows.append(
            {
                "t": start_ms + index * 30_000,
                "o": price,
                "h": price + 0.01,
                "l": price - 0.01,
                "c": price + 0.005,
                "v": 1_000 + index * 100,
                "trade_count": 10 + index,
            }
        )
    return rows


def test_validation_sequence_joins_30s_1m_3m_participation_and_price_response():
    start_ms = 1_788_500_000_000
    ignition_ms = start_ms + 10 * 30_000
    confirmation_ms = ignition_ms + 120_000
    ignition = datetime.fromtimestamp(ignition_ms / 1000, timezone.utc).isoformat()
    confirmation = datetime.fromtimestamp(confirmation_ms / 1000, timezone.utc).isoformat()
    provider = _Provider(_bars(start_ms))
    records = [
        {
            "symbol": "TEST",
            "price": 1.20,
            "participation_score": 78,
            "participation_surge_score": 82,
            "volume_pace_ratio": 2.5,
            "participation_gate": {"passed": True, "reason": "participating"},
            "timeframes": {
                "1m": {"above_vwap": True, "supertrend": True},
                "3m": {"above_vwap": True, "supertrend": True},
            },
            "st_vwap_cross_events": {
                "1m": {
                    "crossed": True,
                    "recent": True,
                    "new": True,
                    "timestamp": ignition,
                    "price": 1.00,
                    "vwap_value": 0.98,
                    "supertrend_value": 0.97,
                },
                "3m": {
                    "crossed": True,
                    "recent": True,
                    "new": False,
                    "timestamp": confirmation,
                    "price": 1.08,
                    "vwap_value": 0.99,
                    "supertrend_value": 1.00,
                },
            },
        }
    ]
    original = deepcopy(records)

    result = gs390.build_validation_sequence(
        {"scan_id": "scan-1", "timestamp": "2026-09-08T13:35:00+00:00"},
        records,
        provider,
    )

    assert result["authority"] == "OBSERVATIONAL_ONLY"
    assert result["symbol_count"] == 1
    row = result["symbols"][0]
    assert row["sequence"] == "1m ignition -> 3m confirmation observed"
    assert row["one_minute"]["current_state"] == {
        "above_vwap": True,
        "supertrend_bullish": True,
    }
    assert row["three_minute"]["current_state"]["supertrend_bullish"] is True
    assert row["confirmation_delay_seconds"] == 120.0
    assert row["price_response_since_1m_ignition_pct"] == 20.0
    assert row["participation_score"] == 78.0
    assert row["thirty_second"]["at_or_before_1m_ignition"]["timestamp_ms"] <= ignition_ms
    assert row["thirty_second"]["latest_closed"]["timestamp_ms"] > ignition_ms
    assert provider.calls == 1
    assert records == original


def test_sequence_ignores_symbols_without_recent_cross_event():
    provider = _Provider([])
    result = gs390.build_validation_sequence(
        {"scan_id": "scan-2", "timestamp": "2026-09-08T14:00:00+00:00"},
        [
            {
                "symbol": "TEST",
                "price": 1.0,
                "st_vwap_cross_events": {
                    "1m": {"crossed": True, "recent": False},
                    "3m": {"crossed": False, "recent": False},
                },
            }
        ],
        provider,
    )
    assert result["symbol_count"] == 0
    assert result["symbols"] == []
    assert provider.calls == 0


def test_gs390_installs_only_recorder_and_runtime_export_wrappers():
    gs390.install()
    assert getattr(
        flight_recorder.persist_replayable_scan,
        "_gs390_st_vwap_validation",
        False,
    )
    assert getattr(
        runtime_evidence.current_scan_export,
        "_gs390_st_vwap_validation",
        False,
    )
