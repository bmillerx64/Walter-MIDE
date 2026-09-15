from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from mide import gs310_unified_opportunity_state as unified
from mide import gs455_early_ignition_3m_confirmation as gs455
from mide.flight_recorder import prefilter_decision as established_prefilter
from mide.gs365_chime_semantic_classifier import semantic_chime_count


SETTINGS = SimpleNamespace(
    min_price=0.02,
    max_price=5.0,
    min_pct_change=3.0,
    min_day_volume=100_000,
)
EASTERN = ZoneInfo("America/New_York")


def snapshot(*, price=0.37, previous_close=0.3607, volume=19_311):
    return {
        "latestTrade": {"p": price},
        "latestQuote": {"bp": price * 0.99, "ap": price * 1.01},
        "dailyBar": {"c": price, "v": volume, "h": price},
        "prevDailyBar": {"c": previous_close},
    }


def _set_clock(monkeypatch, hour, minute):
    monkeypatch.setattr(
        gs455,
        "_market_now",
        lambda: datetime(2026, 9, 15, hour, minute, tzinfo=EASTERN),
    )


def _cross(label, timestamp, *, new=False, current=True):
    return {
        "timeframe": label,
        "crossed": True,
        "recent": True,
        "new": new,
        "timestamp": timestamp,
        "age_seconds": 30.0 if new else 600.0,
        "current_confirmed": current,
        "supertrend_value": 1.0,
        "vwap_value": 0.95,
        "price": 1.05,
    }


def progression_record(*, distance=3.0, newest="3m", halted=False):
    stamps = {
        "30s": "2026-09-15T10:18:00-04:00",
        "1m": "2026-09-15T10:26:00-04:00",
        "3m": "2026-09-15T10:39:00-04:00",
        "5m": "2026-09-15T10:40:00-04:00",
        "10m": "2026-09-15T10:50:00-04:00",
        "15m": "2026-09-15T11:15:00-04:00",
    }
    events = {
        label: _cross(label, stamp, new=(label == newest))
        for label, stamp in stamps.items()
        if label != "30s"
    }
    return {
        "symbol": "RETO",
        "price": 1.88,
        "pct_change": 420.0,
        "volume": 10_000_000,
        "vwap_relation": "above",
        "vwap_distance_pct": distance,
        "halted": halted,
        "operator_investigation_tripwire": True,
        "supertrend_30s_bullish": True,
        "supertrend_30s_last_flip_timestamp": stamps["30s"],
        "supertrend_30s_last_flip_age_seconds": 30.0 if newest == "30s" else 600.0,
        # GS378 remains canonical for literal 1m/3m line-cross truth.
        "st_vwap_cross_events": {
            "1m": dict(events["1m"]),
            "3m": dict(events["3m"]),
        },
        # GS423 retains 1m/3m/5m/10m metadata from the already-paid ST pass.
        "timeframes": {
            label: {
                "above_vwap": True,
                "supertrend": True,
                "current_confirmed": True,
                "st_vwap_line_cross": dict(events[label]),
            }
            for label in ("1m", "3m", "5m", "10m")
        },
        # GS423's selected maturation package owns the 15m pass.
        "multitimeframe_maturation": {
            "available": True,
            "timeframes": {
                "15m": {
                    "current_confirmed": True,
                    "st_vwap_line_cross": dict(events["15m"]),
                }
            },
        },
    }


def _trim_after(record, rung):
    cutoff = gs455.CROSSOVER_LADDER.index(rung)
    allowed = set(gs455.CROSSOVER_LADDER[: cutoff + 1])
    if "30s" not in allowed:
        record["operator_investigation_tripwire"] = False
        record["supertrend_30s_bullish"] = False
        record["supertrend_30s_last_flip_timestamp"] = None
    for label in ("1m", "3m"):
        if label not in allowed:
            record["st_vwap_cross_events"].pop(label, None)
            record["timeframes"].pop(label, None)
    for label in ("5m", "10m"):
        if label not in allowed:
            record["timeframes"].pop(label, None)
    if "15m" not in allowed:
        record["multitimeframe_maturation"]["timeframes"].pop("15m", None)
    return record


def base_view(state=unified.DEVELOPING):
    return {
        "state": state,
        "color": unified.STATE_COLORS[state],
        "reason": "base",
        "next_step": "base next",
        "attention_provenance": [],
        "evidence": [],
    }


def test_reto_like_933_snapshot_gets_narrow_early_open_admission(monkeypatch):
    _set_clock(monkeypatch, 9, 33)
    snap = snapshot()
    baseline = established_prefilter("RETO", snap, SETTINGS)
    assert baseline["passed"] is False
    assert baseline["failed_rule"] == "Percent change and average volume below thresholds"

    result = gs455._early_open_prefilter_decision(
        established_prefilter, "RETO", snap, SETTINGS
    )
    assert result["passed"] is True
    assert "early-open ignition" in result["reason"]
    assert result["thresholds"]["early_open_exception"] == {
        "window_et": "09:30-09:45",
        "min_pct_change": 2.0,
        "min_volume": 15_000.0,
    }


def test_early_open_exception_expires_at_945(monkeypatch):
    _set_clock(monkeypatch, 9, 45)
    result = gs455._early_open_prefilter_decision(
        established_prefilter, "RETO", snapshot(), SETTINGS
    )
    assert result["passed"] is False


def test_early_open_exception_requires_both_two_percent_and_15k(monkeypatch):
    _set_clock(monkeypatch, 9, 35)
    low_move = gs455._early_open_prefilter_decision(
        established_prefilter,
        "LOWMOVE",
        snapshot(price=0.365, previous_close=0.3607, volume=50_000),
        SETTINGS,
    )
    low_volume = gs455._early_open_prefilter_decision(
        established_prefilter,
        "LOWVOL",
        snapshot(price=0.37, previous_close=0.3607, volume=14_999),
        SETTINGS,
    )
    assert low_move["passed"] is False
    assert low_volume["passed"] is False


def test_early_open_exception_never_overrides_price_mission_ceiling(monkeypatch):
    _set_clock(monkeypatch, 9, 35)
    result = gs455._early_open_prefilter_decision(
        established_prefilter,
        "HIGH",
        snapshot(price=5.25, previous_close=5.0, volume=50_000),
        SETTINGS,
    )
    assert result["passed"] is False
    assert result["failed_rule"] == "Price outside threshold"


def test_reto_screenshot_sequence_is_one_ordered_six_rung_progression():
    progression = gs455.crossover_progression(progression_record(newest="15m"))
    assert progression["active_rungs"] == [
        "30s", "1m", "3m", "5m", "10m", "15m"
    ]
    assert progression["depth"] == 6
    assert progression["ordered"] is True
    assert progression["stage"] == "PERSISTENCE"
    assert progression["highest_rung"] == "15m"
    assert progression["latest_new_rung"] == "15m"
    assert progression["sequence"] == "30s -> 1m -> 3m -> 5m -> 10m -> 15m"


def test_progression_stage_advances_from_ignition_to_confirmation_to_persistence():
    ignition = _trim_after(progression_record(newest="1m"), "1m")
    assert gs455.crossover_progression(ignition)["stage"] == "IGNITION"

    confirmation = _trim_after(progression_record(newest="3m"), "3m")
    assert gs455.crossover_progression(confirmation)["stage"] == "CONFIRMATION"

    persistence = _trim_after(progression_record(newest="5m"), "5m")
    assert gs455.crossover_progression(persistence)["stage"] == "PERSISTENCE"


def test_every_new_rung_can_create_operator_attention_without_becoming_entry_authority():
    for rung in gs455.CROSSOVER_LADDER:
        record = _trim_after(progression_record(newest=rung), rung)
        signal = gs455.progression_signal(record)
        assert signal["active"] is True
        assert signal["new_rung"] == rung


def test_out_of_order_crosses_are_not_promoted_as_propagation():
    record = _trim_after(progression_record(newest="3m"), "3m")
    record["st_vwap_cross_events"]["3m"]["timestamp"] = "2026-09-15T10:20:00-04:00"
    record["timeframes"]["3m"]["st_vwap_line_cross"]["timestamp"] = (
        "2026-09-15T10:20:00-04:00"
    )
    progression = gs455.crossover_progression(record)
    assert progression["ordered"] is False
    assert gs455.progression_signal(record)["active"] is False


def test_near_vwap_new_progression_promotes_chart_review_to_look_now():
    record = _trim_after(progression_record(distance=3.0, newest="3m"), "3m")
    view = gs455._state_with_progression(
        lambda _record: base_view(unified.DEVELOPING), record
    )
    assert view["state"] == unified.LOOK_NOW
    assert "maturation reached 3M" in view["reason"]
    assert "not entry authority" in view["next_step"]
    assert "ST_VWAP_CROSSOVER_PROGRESSION" in view["attention_provenance"]


def test_extended_reto_progression_stays_chase_wait_but_is_not_silent():
    record = _trim_after(progression_record(distance=48.0, newest="5m"), "5m")
    view = gs455._state_with_progression(
        lambda _record: base_view(unified.CHASE_WAIT), record
    )
    assert view["state"] == unified.CHASE_WAIT
    assert "maturation reached 5M" in view["reason"]
    assert "DO NOT CHASE" in view["next_step"]
    assert "anti-chase guard remains authoritative" in view["next_step"]

    phrase = gs455._progression_phrase([record])
    assert "LOOK NOW" in phrase
    assert "5 minute" in phrase
    assert "Do not chase" in phrase
    assert semantic_chime_count(phrase) == 2


def test_halt_and_existing_entry_state_are_never_overridden():
    halted = _trim_after(progression_record(halted=True, newest="3m"), "3m")
    halted_view = gs455._state_with_progression(
        lambda _record: base_view(unified.HALTED), halted
    )
    assert halted_view["state"] == unified.HALTED

    entry = _trim_after(progression_record(newest="3m"), "3m")
    entry_view = gs455._state_with_progression(
        lambda _record: base_view(unified.WATCH_FOR_ENTRY), entry
    )
    assert entry_view["state"] == unified.WATCH_FOR_ENTRY


def test_progression_signature_is_bound_to_new_rung_and_cross_timestamp():
    record = _trim_after(progression_record(newest="3m"), "3m")
    change = gs455._progression_change(record)
    assert change == {
        "symbol": "RETO",
        "from": "3M CROSS@2026-09-15T10:39:00-04:00",
        "to": "ST/VWAP MATURATION 3M",
    }


def test_line_cross_event_normalizes_unready_nan_instead_of_breaking_scan_equality():
    index = pd.date_range("2026-09-15 10:00", periods=2, freq="1min", tz=EASTERN)
    frame = pd.DataFrame(
        {
            "open": [1.0, 1.0],
            "high": [1.1, 1.1],
            "low": [0.9, 0.9],
            "close": [1.0, 1.0],
            "volume": [1000, 1000],
        },
        index=index,
    )
    vwap = pd.Series([1.0, 1.0], index=index)
    st_line = pd.Series([np.nan, np.nan], index=index)
    trend = pd.Series([False, False], index=index)
    event = gs455._line_cross_event(
        frame,
        vwap,
        st_line,
        trend,
        "10m",
        latest_source_time=index[-1],
    )
    assert event["latest_supertrend_value"] is None
    assert event["latest_vwap_value"] == 1.0
    assert event["crossed"] is False


def test_gs455_reuses_gs423_and_gs421_supertrend_passes_instead_of_requesting_history():
    source = Path("mide/gs455_early_ignition_3m_confirmation.py").read_text(
        encoding="utf-8"
    )
    assert "gs423.install()" in source
    assert "gs378._confirmation_details = _confirmation_details_with_line_cross" in source
    assert "gs421._timeframe_event = _timeframe_event_with_line_cross" in source
    assert "client.bars(" not in source
    assert "provider.bars(" not in source
    assert "extra_crossover_events" not in source


def test_gs455_keeps_gs378_canonical_for_1m_3m_cross_truth():
    source = Path("mide/gs455_early_ignition_3m_confirmation.py").read_text(
        encoding="utf-8"
    )
    assert 'if label in {"1m", "3m"}' in source
    assert 'record.get("st_vwap_cross_events")' in source


def test_gs455_chains_after_gs454_on_cold_and_warm_runtime_paths():
    source = Path("mide/gs454_flight_recorder_download_freshness.py").read_text(
        encoding="utf-8"
    )
    assert "gs455_early_ignition_3m_confirmation" in source
    assert source.count("_install_gs455()") >= 2


def test_gs455_scope_lock_keeps_entry_execution_authority_untouched():
    source = Path("mide/gs455_early_ignition_3m_confirmation.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "place_order(",
        "submit_order(",
        "request_scan(",
    )
    for token in forbidden:
        assert token not in source
    assert 'CROSSOVER_LADDER = ("30s", "1m", "3m", "5m", "10m", "15m")' in source
    assert "EARLY_OPEN_MIN_PCT_CHANGE = 2.0" in source
    assert "EARLY_OPEN_MIN_VOLUME = 15_000.0" in source
