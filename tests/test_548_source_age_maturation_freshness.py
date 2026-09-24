"""GS548: maturation freshness includes current source-bar age."""

from copy import deepcopy
from pathlib import Path

from mide import gs455_early_ignition_3m_confirmation as gs455
from mide.authorities import market_evidence
from mide.authorities import presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def _cross(label="1m", *, age=0.0, flip_age=0.0):
    return {
        "timeframe": label,
        "crossed": True,
        "recent": True,
        "new": True,
        "timestamp": "2026-09-24T16:04:00-04:00",
        "age_seconds": age,
        "bullish_flip_age_seconds": flip_age,
        "current_confirmed": True,
    }


def _record(*, bar_age=30.0, label="1m", age=0.0):
    return {
        "symbol": "MITQ",
        "bar_age_seconds": bar_age,
        "vwap_distance_pct": 1.0,
        "volume": 150_000,
        "st_vwap_cross_events": {
            label: _cross(label, age=age),
        },
        "timeframes": {
            label: {
                "timeframe": label,
                "data_available": True,
                "current_supertrend_bullish": True,
                "current_above_vwap": True,
                "current_confirmed": True,
                "bullish_flip_age_seconds": age,
                "st_vwap_line_cross": _cross(label, age=age),
            }
        },
    }


def test_gs548_stale_source_bar_expires_raw_zero_age_cross():
    record = _record(bar_age=3086.8, age=0.0)
    original = deepcopy(record)

    event = market_evidence.progression_rung_event(record, "1m")

    assert event["source_relative_age_seconds"] == 0.0
    assert event["source_bar_age_seconds"] == 3086.8
    assert event["operator_effective_age_seconds"] == 3086.8
    assert event["age_seconds"] == 3086.8
    assert event["new"] is False
    assert event["recent"] is False
    assert (
        event["freshness_authority"]
        == market_evidence.GS548_MATURATION_FRESHNESS_AUTHORITY
    )
    assert record == original


def test_gs548_live_source_bar_preserves_fresh_one_minute_event():
    record = _record(bar_age=30.0, age=0.0)

    progression = gs455.crossover_progression(record)
    signal = gs455.progression_signal(record)

    event = progression["events"]["1m"]
    assert event["age_seconds"] == 30.0
    assert event["new"] is True
    assert event["recent"] is True
    assert progression["fresh_rungs"] == ["1m"]
    assert signal["active"] is True
    assert signal["new_rung"] == "1m"


def test_gs548_stale_source_cannot_create_fresh_progression_signal():
    record = _record(bar_age=3086.8, age=0.0)

    progression = gs455.crossover_progression(record)
    signal = gs455.progression_signal(record)

    assert progression["active_rungs"] == ["1m"]
    assert progression["fresh_rungs"] == []
    assert progression["latest_new_rung"] is None
    assert signal["active"] is False
    assert signal["new_rung"] is None


def test_gs548_effective_age_adds_event_and_source_age():
    record = _record(bar_age=75.0, age=60.0)

    event = market_evidence.progression_rung_event(record, "1m")

    assert event["source_relative_age_seconds"] == 60.0
    assert event["source_bar_age_seconds"] == 75.0
    assert event["age_seconds"] == 135.0
    assert event["new"] is False
    assert event["recent"] is True


def test_gs548_top_level_cross_truth_is_rebuilt_from_effective_freshness():
    record = _record(bar_age=3086.8, age=0.0)
    raw = {
        "st_vwap_cross_recent": True,
        "st_vwap_cross_new": True,
        "st_vwap_cross_timeframes": ["1m"],
        "st_vwap_cross_new_timeframes": ["1m"],
        "st_vwap_cross_multi_timeframe": False,
        "st_vwap_cross_age_seconds": 0.0,
        "st_vwap_cross_signature": "1m@2026-09-24T16:04:00-04:00",
        "st_vwap_cross_events": {
            "1m": _cross("1m", age=0.0, flip_age=0.0),
            "3m": {
                "timeframe": "3m",
                "crossed": False,
                "recent": False,
                "new": False,
                "timestamp": None,
                "age_seconds": None,
                "bullish_flip_age_seconds": None,
                "current_confirmed": False,
            },
        },
        "crossed_vwap_and_supertrend": True,
        "supertrend_flipped_last_10m": True,
        "supertrend_flip_age_seconds": 0.0,
    }

    result = market_evidence.operator_fresh_st_vwap_evidence(record, raw)

    assert result["st_vwap_cross_recent"] is False
    assert result["st_vwap_cross_new"] is False
    assert result["st_vwap_cross_timeframes"] == []
    assert result["st_vwap_cross_new_timeframes"] == []
    assert result["st_vwap_cross_age_seconds"] is None
    assert result["crossed_vwap_and_supertrend"] is False
    assert result["supertrend_flip_age_seconds"] == 3086.8
    assert result["supertrend_flipped_last_10m"] is False


def test_gs548_presentation_audio_uses_effective_freshness():
    stale = _record(bar_age=3086.8, age=0.0)
    fresh = _record(bar_age=30.0, age=0.0)

    stale_detail = presentation_audio._maturation_tf(stale, "1m")
    fresh_detail = presentation_audio._maturation_tf(fresh, "1m")

    assert presentation_audio._maturation_cross_new(stale_detail) is False
    assert presentation_audio._maturation_cross_new(fresh_detail) is True


def test_gs548_three_minute_flip_audio_freshness_uses_source_age():
    record = _record(bar_age=900.0, label="3m", age=0.0)

    detail = presentation_audio._maturation_tf(record, "3m")

    assert detail["raw"]["bullish_flip_age_seconds"] == 900.0
    assert presentation_audio._three_minute_maturation_fresh(detail) is False


def test_gs548_gs378_delegates_freshness_without_wall_clock_reconstruction():
    source = (
        ROOT / "mide/gs378_live_vwap_st_crossover.py"
    ).read_text(encoding="utf-8")

    assert "operator_fresh_timeframe_details(" in source
    assert "operator_fresh_st_vwap_evidence(" in source
    assert "datetime.now(" not in source[
        source.index("# GS548: raw bar reconstruction"):
        source.index("record.update(", source.index("# GS548: raw bar reconstruction"))
    ]


def test_gs548_scope_does_not_change_entry_or_execution_authority():
    source = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")
    start = source.index(
        'GS548_MATURATION_FRESHNESS_AUTHORITY ='
    )
    end = source.index(
        "def thirty_second_progression_rung(",
        start,
    )
    block = source[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "expansion_score =",
        "opportunity_state =",
        "place_order(",
        "submit_order(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in block for token in forbidden)
