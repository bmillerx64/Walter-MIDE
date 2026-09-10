from __future__ import annotations

from pathlib import Path

import pandas as pd

from mide import gs421_multitimeframe_convergence_recorder as gs421


def _event(label: str, stamp: str, price: float = 4.40) -> dict:
    return {
        "timeframe": label,
        "data_available": True,
        "current_supertrend_bullish": True,
        "current_above_vwap": True,
        "current_confirmed": True,
        "bullish_flip_timestamp": stamp,
        "bullish_flip_age_seconds": 0.0,
        "price_at_flip": price,
        "vwap_at_flip": 4.30,
    }


def test_tnon_style_cascade_orders_1m_through_15m():
    events = {
        "1m": _event("1m", "2026-09-10T13:17:00-04:00"),
        "3m": _event("3m", "2026-09-10T13:22:00-04:00"),
        "5m": _event("5m", "2026-09-10T13:25:00-04:00"),
        "10m": _event("10m", "2026-09-10T13:30:00-04:00"),
        "15m": _event("15m", "2026-09-10T13:45:00-04:00"),
    }

    assert gs421._cascade(events) == ["1m", "3m", "5m", "10m", "15m"]
    assert gs421._delays_from_1m(events) == {
        "3m": 300.0,
        "5m": 480.0,
        "10m": 780.0,
        "15m": 1680.0,
    }


def test_cascade_stops_when_a_slower_timeframe_has_not_matured():
    events = {
        "1m": _event("1m", "2026-09-10T13:17:00-04:00"),
        "3m": _event("3m", "2026-09-10T13:22:00-04:00"),
        "5m": {"bullish_flip_timestamp": None},
        "10m": _event("10m", "2026-09-10T13:30:00-04:00"),
        "15m": _event("15m", "2026-09-10T13:45:00-04:00"),
    }

    assert gs421._cascade(events) == ["1m", "3m"]


def test_build_evidence_records_convergence_without_creating_authority(monkeypatch):
    index = pd.date_range(
        "2026-09-10 09:30",
        periods=300,
        freq="1min",
        tz="America/New_York",
    )
    frame = pd.DataFrame(
        {
            "open": [4.30] * len(index),
            "high": [4.50] * len(index),
            "low": [4.20] * len(index),
            "close": [4.40] * len(index),
            "volume": [10000.0] * len(index),
        },
        index=index,
    )

    class Client:
        @staticmethod
        def bars_frame(_rows):
            return frame

    times = {
        "1m": "2026-09-10T13:17:00-04:00",
        "3m": "2026-09-10T13:22:00-04:00",
        "5m": "2026-09-10T13:25:00-04:00",
        "10m": "2026-09-10T13:30:00-04:00",
        "15m": "2026-09-10T13:45:00-04:00",
    }

    monkeypatch.setattr(
        gs421,
        "_timeframe_event",
        lambda _day, _primary, label: _event(label, times[label]),
    )

    record = {
        "symbol": "TNON",
        "price": 4.90,
        "vwap_distance_pct": 1.5,
        "participation_score": 72,
        "participation_surge_score": 81,
        "expansion_score": 78,
        "volume_acceleration": 3.2,
        "dollar_flow_acceleration": 4.1,
        "qualified_for_watch": True,
        "qualified_for_entry": False,
        "status": "PASS",
        "operator_investigation_tripwire": True,
        "supertrend_30s_bullish": True,
    }

    evidence = gs421.build_maturation_evidence(record, [{}], Client())

    assert evidence["authority"] == "OBSERVATIONAL_ONLY"
    assert evidence["observed_cascade"] == ["1m", "3m", "5m", "10m", "15m"]
    assert evidence["highest_observed_maturation"] == "15m"
    assert evidence["current_convergence_count"] == 5
    assert evidence["scan_snapshot"]["qualified_for_entry"] is False
    assert evidence["entry_authority_changed"] is False
    assert "240m" in evidence["pre_ignition_context"]


def test_install_only_annotates_and_does_not_change_existing_decisions(monkeypatch):
    def original(records, _raw1m, _raw30s, _client):
        return records

    monkeypatch.setattr(gs421.gs378, "apply_live_vwap_truth", original)
    monkeypatch.setattr(
        gs421,
        "build_maturation_evidence",
        lambda _record, _rows, _client: {
            "authority": "OBSERVATIONAL_ONLY",
            "available": True,
            "observed_cascade": ["1m", "3m"],
        },
    )
    gs421.install()

    class Client:
        def __init__(self):
            self.diagnostics = {}

    client = Client()
    source = {
        "symbol": "TNON",
        "score": 83,
        "status": "PASS",
        "qualified_for_watch": True,
        "qualified_for_entry": False,
        "qualified_for_alert": False,
    }
    result = gs421.gs378.apply_live_vwap_truth(
        [dict(source)], {"TNON": [{}]}, {}, client
    )[0]

    for key, value in source.items():
        assert result[key] == value
    assert result["multitimeframe_maturation_authority"] == "OBSERVATIONAL_ONLY"
    assert result["multitimeframe_maturation"]["observed_cascade"] == ["1m", "3m"]
    assert client.diagnostics["gs421_multitimeframe_convergence"]["additional_history_requests"] == 0
    assert client.diagnostics["gs421_multitimeframe_convergence"]["ranking_changed"] is False
    assert client.diagnostics["gs421_multitimeframe_convergence"]["qualification_changed"] is False


def test_gs421_is_installed_after_gs414_and_does_not_touch_audio():
    chain = Path("mide/gs392_operator_order_audio.py").read_text(encoding="utf-8")
    source = Path("mide/gs421_multitimeframe_convergence_recorder.py").read_text(
        encoding="utf-8"
    )

    assert chain.index("install_gs414()") < chain.index("install_gs421()")
    assert "play_alert" not in source
    assert "TONE_PATTERNS" not in source
    assert "additional_history_requests\": 0" in source
