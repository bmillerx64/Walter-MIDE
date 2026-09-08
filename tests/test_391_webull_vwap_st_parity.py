import pandas as pd

from mide import flight_recorder, indicators, runtime_evidence
from mide import gs378_live_vwap_st_crossover as gs378
from mide import gs391_webull_vwap_st_parity as gs391


def _frame(index, closes, volumes=None):
    volumes = volumes or [1000] * len(closes)
    return pd.DataFrame(
        {
            "open": closes,
            "high": [value + 0.01 for value in closes],
            "low": [value - 0.01 for value in closes],
            "close": closes,
            "volume": volumes,
        },
        index=pd.DatetimeIndex(index),
    )


def test_webull_primary_context_keeps_extended_vwap_authoritative_after_open():
    index = pd.to_datetime(
        [
            "2026-09-08T08:00:00Z",  # 04:00 ET
            "2026-09-08T13:29:00Z",  # 09:29 ET
            "2026-09-08T13:30:00Z",  # 09:30 ET
            "2026-09-08T13:31:00Z",
        ],
        utc=True,
    )
    frame = _frame(index, [1.00, 1.00, 0.80, 0.82], [1_000_000, 1_000_000, 100, 100])

    context = gs391.webull_primary_vwap_context(frame)

    assert context["anchor_mode"] == gs391.PRIMARY_POLICY
    assert context["anchor_time"].hour == 4
    assert context["value"] > 0.99
    assert round(context["rth_value"], 4) == 0.81
    assert context["value"] != context["rth_value"]


def test_latest_3m_snapshot_persists_ohlcv_vwap_and_existing_supertrend(monkeypatch):
    index = pd.date_range(
        "2026-09-08 09:30:00",
        periods=7,
        freq="min",
        tz="America/New_York",
    )
    closes = [0.80, 0.81, 0.82, 0.83, 0.84, 0.85, 0.86]
    frame = _frame(index, closes)
    primary = pd.Series([0.79] * len(frame), index=frame.index, dtype=float)
    context = {"day": frame, "series": primary}

    def fake_supertrend(tf, period, multiplier):
        assert period == 10
        assert multiplier == 3
        line = tf["close"].astype(float) - 0.02
        trend = pd.Series(True, index=tf.index, dtype=bool)
        return line, trend

    monkeypatch.setattr(gs391, "supertrend", fake_supertrend)
    snap = gs391._latest_timeframe_snapshot(context, "3m")

    assert snap["timeframe"] == "3m"
    assert snap["close"] == 0.86
    assert snap["vwap_value"] == 0.79
    assert snap["supertrend_10_3"] == 0.84
    assert snap["supertrend_bullish"] is True
    assert snap["relation_to_supertrend"] == "above"
    assert snap["supertrend_ready"] is True


def test_parity_audit_is_observational_and_keeps_both_vwap_contexts():
    observation = {
        "authority": gs391.AUTHORITY,
        "primary_vwap_policy": gs391.PRIMARY_POLICY,
        "one_minute": {"close": 0.86},
        "three_minute": {"close": 0.86},
    }
    payload = gs391._build_scan_parity(
        [
            {
                "symbol": "GMEX",
                "price": 0.86,
                "vwap_value": 0.965,
                "vwap_distance_pct": -10.88,
                "vwap_anchor_mode": gs391.PRIMARY_POLICY,
                "premarket_vwap_value": 0.98,
                "rth_vwap_value": 0.825,
                "st_webull_parity_observation": observation,
            }
        ]
    )

    assert payload["authority"] == "OBSERVATIONAL_ONLY"
    assert payload["symbol_count"] == 1
    row = payload["symbols"][0]
    assert row["symbol"] == "GMEX"
    assert row["primary_vwap"] == 0.965
    assert row["rth_only_vwap"] == 0.825
    assert row["parity"]["three_minute"]["close"] == 0.86


def test_gs391_runtime_wrappers_are_installed_without_replacing_supertrend_formula():
    assert getattr(gs378.primary_vwap_context, "_gs391_webull_vwap", False) is True
    assert getattr(gs378.apply_live_vwap_truth, "_gs391_webull_vwap", False) is True
    assert getattr(flight_recorder.persist_replayable_scan, "_gs391_webull_vwap", False) is True
    assert getattr(runtime_evidence.current_scan_export, "_gs391_webull_vwap", False) is True
    assert gs391.supertrend is indicators.supertrend
