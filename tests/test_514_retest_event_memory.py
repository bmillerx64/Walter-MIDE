from pathlib import Path

import pandas as pd

from mide import gs493_3m_st_retest_truth as gs493
from mide import gs514_retest_event_memory as gs514


def _tf(index, lows, closes):
    return pd.DataFrame(
        {
            "open": closes,
            "high": [max(low, close) + 0.02 for low, close in zip(lows, closes)],
            "low": lows,
            "close": closes,
            "volume": [100000.0] * len(index),
        },
        index=index,
    )


def test_ncpl_style_retest_is_remembered_after_price_bounces_away():
    index = pd.date_range(
        "2026-09-21 09:00",
        periods=12,
        freq="3min",
        tz="America/New_York",
    )
    lows = [1.12] * 12
    closes = [1.14] * 12
    lows[6] = 1.05
    closes[6] = 1.11
    closes[-1] = 1.15
    frame = _tf(index, lows, closes)
    st = pd.Series([1.0457] * 12, index=index)
    trend = pd.Series([False, False] + [True] * 10, index=index)

    event = gs514._latest_held_retest(
        frame,
        st,
        trend,
        observed_at=index[-1],
    )

    assert event["available"] is True
    assert event["active_memory"] is True
    assert event["timestamp"] == index[6].isoformat()
    assert event["retest_low"] == 1.05
    assert event["supertrend_at_retest"] == 1.0457
    assert abs(event["signed_low_gap_pct"]) < 0.5
    assert event["current_close"] == 1.15
    assert event["current_bar_is_retest"] is False


def test_old_retest_does_not_survive_a_bearish_break_and_new_bullish_regime():
    index = pd.date_range(
        "2026-09-21 09:00",
        periods=10,
        freq="3min",
        tz="America/New_York",
    )
    lows = [1.00, 1.00, 1.005, 1.08, 0.95, 0.96, 1.10, 1.11, 1.12, 1.13]
    closes = [1.03, 1.04, 1.03, 1.10, 0.96, 0.97, 1.12, 1.13, 1.14, 1.15]
    frame = _tf(index, lows, closes)
    st = pd.Series([1.0] * 10, index=index)
    trend = pd.Series([True, True, True, True, False, False, True, True, True, True], index=index)

    event = gs514._latest_held_retest(
        frame,
        st,
        trend,
        observed_at=index[-1],
    )

    assert event["available"] is False
    assert event["active_memory"] is False
    assert event["current_three_minute_bullish"] is True


def test_prior_retest_changes_only_truth_description_not_opportunity_state():
    gs514.install()
    record = {
        "symbol": "NCPL",
        "price": 1.15,
        "vwap_relation": "below",
        "vwap_distance_pct": -1.4,
        "timeframes": {
            "30s": {
                "data_available": True,
                "current_supertrend_bullish": False,
                "current_above_vwap": False,
                "current_close": 1.15,
            },
            "1m": {
                "data_available": True,
                "current_supertrend_bullish": False,
                "current_above_vwap": False,
                "current_close": 1.15,
            },
            "3m": {
                "data_available": True,
                "current_supertrend_bullish": True,
                "current_above_vwap": False,
                "current_close": 1.15,
                "st_vwap_line_cross": {
                    "latest_supertrend_value": 1.0457,
                    "latest_vwap_value": 1.166,
                },
            },
        },
        "multitimeframe_maturation": {
            "three_minute_st_retest_event": {
                "available": True,
                "active_memory": True,
                "timestamp": "2026-09-21T10:18:00-04:00",
                "age_seconds": 1080.0,
                "retest_low": 1.05,
                "supertrend_at_retest": 1.0457,
            }
        },
    }

    truth = gs493.three_minute_st_retest_truth(record)
    assert truth["state"] == "PRIOR_ST_RETEST_HELD"
    assert truth["entry_authority_changed"] is False

    base = {
        "state": "DEVELOPING",
        "reason": "Price is below VWAP.",
        "next_step": "Wait for repair.",
    }
    view = gs493.state_with_3m_st_truth(lambda _record: dict(base), record)

    assert view["state"] == "DEVELOPING"
    assert view["reason"] == "Price is below VWAP."
    assert "PRIOR 3M ST RETEST HELD" in view["next_step"]
    assert "entry trigger is NOT earned yet" in view["next_step"]
    assert "VWAP acceptance" in view["next_step"]
    assert "30s repair" in view["next_step"]
    assert "1m repair" in view["next_step"]
    assert view["discipline_sequence"]["lower_timeframe_repair_complete"] is False


def test_repaired_lower_timeframes_still_do_not_grant_entry_authority():
    gs514.install()
    record = {
        "symbol": "NCPL",
        "price": 1.17,
        "vwap_relation": "above",
        "vwap_distance_pct": 0.3,
        "timeframes": {
            label: {
                "data_available": True,
                "current_supertrend_bullish": True,
                "current_above_vwap": True,
                "current_close": 1.17,
                **(
                    {
                        "st_vwap_line_cross": {
                            "latest_supertrend_value": 1.0457,
                            "latest_vwap_value": 1.166,
                        }
                    }
                    if label == "3m"
                    else {}
                ),
            }
            for label in ("30s", "1m", "3m")
        },
        "multitimeframe_maturation": {
            "three_minute_st_retest_event": {
                "available": True,
                "active_memory": True,
                "timestamp": "2026-09-21T10:18:00-04:00",
                "age_seconds": 1200.0,
                "retest_low": 1.05,
                "supertrend_at_retest": 1.0457,
            }
        },
    }
    truth = gs493.three_minute_st_retest_truth(record)
    assert truth["state"] == "PRIOR_ST_RETEST_HELD"

    view = gs493.state_with_3m_st_truth(
        lambda _record: {
            "state": "DEVELOPING",
            "reason": "Independent base state.",
            "next_step": "",
        },
        record,
    )
    assert view["state"] == "DEVELOPING"
    assert view["discipline_sequence"]["lower_timeframe_repair_complete"] is True
    assert "existing readiness and entry authority still control" in view["next_step"]


def test_gs514_installs_after_selective_maturation_recorder():
    chain = Path("mide/gs392_operator_order_audio.py").read_text(encoding="utf-8")
    assert chain.index("install_gs421()") < chain.index("install_gs422()")
    assert chain.index("install_gs422()") < chain.index("install_gs514()")


def test_scope_lock_is_memory_and_presentation_only():
    source = Path("mide/gs514_retest_event_memory.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "opportunity_score =",
        "place_order(",
        "submit_order(",
        "request_scan(",
        "TONE_PATTERNS",
        "play_alert(",
    )
    assert not any(token in source for token in forbidden)
    assert "PRESENTATION_MEMORY_ONLY" in source
