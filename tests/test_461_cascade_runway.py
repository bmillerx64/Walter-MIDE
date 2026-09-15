from pathlib import Path

import pandas as pd

from mide import gs310_unified_opportunity_state as unified
from mide import gs378_live_vwap_st_crossover as gs378
from mide import gs460_st_flip_compression_ignition as gs460
from mide import gs461_cascade_runway as gs461


def _status(label, *, bullish=False, gap=None, available=True):
    close = 2.0 if available else None
    st = None
    if available:
        if bullish:
            st = 1.8
        elif gap is not None:
            st = close * (1.0 + gap / 100.0)
    return gs461._status_payload(
        label,
        available=available,
        bullish=bullish,
        close=close,
        supertrend_value=st,
        source="test",
    )


def _compression(active=True, depth=4):
    return {
        "active": active,
        "stage": "IGNITION CASCADE" if depth == 4 else "IGNITION BUILDING",
        "depth": depth,
        "sequence": "30s -> 1m -> 3m -> 5m" if depth == 4 else "30s -> 1m -> 3m",
    }


def test_reto_like_runway_keeps_first_barrier_and_later_one_hour_support():
    runway = gs461.summarize_runway(
        _compression(),
        {
            "10m": _status("10m", bullish=True),
            "15m": _status("15m", gap=1.8),
            "30m": _status("30m", gap=4.2),
            "1h": _status("1h", bullish=True),
        },
    )

    assert runway["active"] is True
    assert runway["contiguous_slower_bullish"] == ["10m"]
    assert runway["next_barrier"]["timeframe"] == "15m"
    assert abs(runway["next_barrier"]["barrier_gap_pct"] - 1.8) < 0.01
    assert runway["future_bullish_support"] == ["1h"]
    assert runway["authority"] == "OPERATOR_ATTENTION_ONLY"
    assert runway["entry_authority_changed"] is False


def test_unavailable_intermediate_frame_blocks_forward_inference():
    runway = gs461.summarize_runway(
        _compression(),
        {
            "10m": _status("10m", bullish=True),
            "15m": _status("15m", available=False),
            "30m": _status("30m", gap=2.0),
            "1h": _status("1h", bullish=True),
        },
    )

    assert runway["contiguous_slower_bullish"] == ["10m"]
    assert runway["next_barrier"] is None
    assert runway["blocked_by_unavailable"] == "15m"
    assert runway["future_bullish_support"] == ["1h"]


def test_runway_never_activates_without_gs460_compression():
    runway = gs461.summarize_runway(
        _compression(active=False),
        {label: _status(label, bullish=True) for label in gs461.RUNWAY_ORDER},
    )
    assert runway["active"] is False


def test_build_runway_short_circuits_before_touching_history_without_compression(monkeypatch):
    monkeypatch.setattr(gs460, "st_flip_compression", lambda _record: _compression(active=False))

    class Client:
        def bars_frame(self, _rows):
            raise AssertionError("history should not be touched")

    result = gs461.build_cascade_runway({"symbol": "NOPE"}, [], Client())
    assert result["active"] is False
    assert result["reason"] == "no_active_gs460_compression"
    assert result["additional_history_requests"] == 0


def test_local_status_reports_current_line_gap_not_predicted_flip(monkeypatch):
    index = pd.date_range("2026-09-15 13:00", periods=40, freq="1min", tz="America/New_York")
    day = pd.DataFrame(
        {
            "open": [2.0] * 40,
            "high": [2.02] * 40,
            "low": [1.98] * 40,
            "close": [2.0] * 40,
            "volume": [100_000.0] * 40,
        },
        index=index,
    )

    monkeypatch.setattr(gs461, "resample_ohlcv", lambda _day, _rule: day.tail(12))
    monkeypatch.setattr(
        gs461,
        "supertrend",
        lambda frame, _period, _mult: (
            pd.Series([2.06] * len(frame), index=frame.index),
            pd.Series([False] * len(frame), index=frame.index),
        ),
    )

    status = gs461._local_status(day, "30m")
    assert status["available"] is True
    assert status["bullish"] is False
    assert abs(status["barrier_gap_pct"] - 3.0) < 0.01
    assert status["relation"] == "overhead_barrier"


def test_state_enrichment_preserves_gs460_state_and_authority_fields():
    record = {
        "symbol": "RETO",
        "qualified_for_entry": False,
        "qualified_for_alert": False,
        "st_cascade_runway": gs461.summarize_runway(
            _compression(),
            {
                "10m": _status("10m", bullish=True),
                "15m": _status("15m", gap=1.6),
                "30m": _status("30m", gap=4.0),
                "1h": _status("1h", bullish=True),
            },
        ),
    }

    base = {
        "state": unified.LOOK_NOW,
        "reason": "IGNITION CASCADE: 30s -> 1m -> 3m -> 5m.",
        "next_step": "Open the chart now.",
        "attention_provenance": ["ST_FLIP_PRICE_COMPRESSION"],
    }
    view = gs461._state_with_runway(lambda _row: dict(base), record)

    assert view["state"] == unified.LOOK_NOW
    assert "Cascade runway:" in view["reason"]
    assert "next 15m SuperTrend line 1.6% away" in view["reason"]
    assert "later 1h already bullish" in view["reason"]
    assert record["qualified_for_entry"] is False
    assert record["qualified_for_alert"] is False


def test_state_enrichment_does_not_touch_unrelated_look_now():
    record = {
        "st_cascade_runway": gs461.summarize_runway(
            _compression(),
            {label: _status(label, bullish=True) for label in gs461.RUNWAY_ORDER},
        )
    }
    base = {
        "state": unified.LOOK_NOW,
        "reason": "Unrelated catalyst.",
        "next_step": "Review.",
        "attention_provenance": ["OTHER"],
    }
    assert gs461._state_with_runway(lambda _row: dict(base), record) == base


def test_runway_text_describes_noncontiguous_support_without_claiming_probability():
    runway = gs461.summarize_runway(
        _compression(),
        {
            "10m": _status("10m", bullish=True),
            "15m": _status("15m", gap=2.3),
            "30m": _status("30m", gap=5.0),
            "1h": _status("1h", bullish=True),
        },
    )
    text = gs461._runway_text(runway)
    assert "10m already bullish" in text
    assert "next 15m SuperTrend line 2.3% away" in text
    assert "later 1h already bullish" in text
    assert "odds" not in text.lower()
    assert "probability" not in text.lower()


def test_evidence_wrapper_attaches_runway_without_changing_record_membership(monkeypatch):
    record = {"symbol": "RETO", "qualified_for_entry": False}

    def baseline(records, _raw, _raw30, _client):
        return records

    monkeypatch.setattr(gs378, "apply_live_vwap_truth", baseline)
    monkeypatch.setattr(
        gs461,
        "build_cascade_runway",
        lambda _record, _rows, _client: {
            "active": True,
            "authority": "OPERATOR_ATTENTION_ONLY",
            "additional_history_requests": 0,
            "entry_authority_changed": False,
        },
    )

    class Client:
        diagnostics = {}

    gs461._install_evidence()
    installed = gs378.apply_live_vwap_truth
    result = installed([record], {"RETO": [{"close": 1.0}]}, {}, Client())

    assert result == [record]
    assert record["st_cascade_runway"]["active"] is True
    assert record["qualified_for_entry"] is False
    assert Client.diagnostics["gs461_cascade_runway"]["additional_history_requests"] == 0


def test_gs461_installs_after_gs423_and_before_gs424():
    source = Path("mide/startup.py").read_text(encoding="utf-8")
    assert "gs461_cascade_runway" in source
    assert source.index("install_gs423()") < source.index("install_gs461()")
    assert source.index("install_gs461()") < source.index("install_gs424()")


def test_gs461_scope_lock_is_attention_and_local_history_only():
    source = Path("mide/gs461_cascade_runway.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "place_order(",
        "submit_order(",
        "request_scan(",
        ".get_bars(",
        ".history(",
        "TRIGGER_",
        "PARTICIPATION_MIN_",
    )
    for token in forbidden:
        assert token not in source
    assert "additional_history_requests\": 0" in source
    assert "RUNWAY_ORDER = (\"10m\", \"15m\", \"30m\", \"1h\")" in source
