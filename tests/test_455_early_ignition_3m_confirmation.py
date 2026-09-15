from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

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


def confirmation_record(*, distance=3.0, age=30.0, new=True, halted=False):
    return {
        "symbol": "RETO",
        "price": 0.84,
        "pct_change": 132.0,
        "volume": 4_000_000,
        "vwap_relation": "above",
        "vwap_distance_pct": distance,
        "halted": halted,
        "timeframes": {
            "1m": {"above_vwap": True, "supertrend": True},
            "3m": {"above_vwap": True, "supertrend": True},
        },
        "st_vwap_cross_events": {
            "3m": {
                "crossed": True,
                "new": new,
                "recent": True,
                "timestamp": "2026-09-15T10:39:00-04:00",
                "age_seconds": age,
                "price": 0.84,
                "supertrend_value": 0.8328,
                "vwap_value": 0.8328,
            }
        },
    }


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


def test_existing_normal_prefilter_pass_is_unchanged(monkeypatch):
    _set_clock(monkeypatch, 9, 34)
    snap = snapshot(price=0.40, previous_close=0.36, volume=1_000)
    baseline = established_prefilter("MOVE", snap, SETTINGS)
    result = gs455._early_open_prefilter_decision(
        established_prefilter, "MOVE", snap, SETTINGS
    )
    assert baseline["passed"] is True
    assert result == baseline


def test_fresh_3m_cross_with_constructive_1m_3m_is_maturation_evidence():
    evidence = gs455.three_minute_confirmation(confirmation_record())
    assert evidence["active"] is True
    assert evidence["one_minute_constructive"] is True
    assert evidence["three_minute_constructive"] is True
    assert evidence["timestamp"] == "2026-09-15T10:39:00-04:00"


def test_near_vwap_fresh_3m_confirmation_promotes_chart_review_to_look_now():
    record = confirmation_record(distance=3.0)
    view = gs455._state_with_three_minute_confirmation(
        lambda _record: base_view(unified.DEVELOPING), record
    )
    assert view["state"] == unified.LOOK_NOW
    assert "3m confirmation" in view["reason"]
    assert "not entry authority" in view["next_step"]
    assert "FRESH_3M_ST_VWAP_CONFIRMATION" in view["attention_provenance"]


def test_extended_reto_like_confirmation_stays_chase_wait_but_is_not_silent():
    record = confirmation_record(distance=48.0)
    view = gs455._state_with_three_minute_confirmation(
        lambda _record: base_view(unified.CHASE_WAIT), record
    )
    assert view["state"] == unified.CHASE_WAIT
    assert "confirming trend maturation" in view["reason"]
    assert "DO NOT CHASE" in view["next_step"]
    assert "anti-chase guard remains authoritative" in view["next_step"]

    phrase = gs455._confirmation_phrase([record])
    assert "LOOK NOW" in phrase
    assert "Do not chase" in phrase
    assert semantic_chime_count(phrase) == 2


def test_stale_or_broken_structure_does_not_manufacture_confirmation():
    stale = confirmation_record(age=151.0, new=False)
    assert gs455.three_minute_confirmation(stale)["active"] is False

    broken = confirmation_record()
    broken["timeframes"]["1m"]["supertrend"] = False
    assert gs455.three_minute_confirmation(broken)["active"] is False


def test_halt_and_existing_entry_state_are_never_overridden():
    halted = confirmation_record(halted=True)
    halted_view = gs455._state_with_three_minute_confirmation(
        lambda _record: base_view(unified.HALTED), halted
    )
    assert halted_view["state"] == unified.HALTED

    entry = confirmation_record()
    entry_view = gs455._state_with_three_minute_confirmation(
        lambda _record: base_view(unified.WATCH_FOR_ENTRY), entry
    )
    assert entry_view["state"] == unified.WATCH_FOR_ENTRY


def test_confirmation_signature_is_bound_to_canonical_cross_timestamp():
    change = gs455._confirmation_change(confirmation_record())
    assert change == {
        "symbol": "RETO",
        "from": "3M CROSS@2026-09-15T10:39:00-04:00",
        "to": "3M ST/VWAP CONFIRMATION",
    }


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
    assert "st_vwap_cross_events" in source
    assert "EARLY_OPEN_MIN_PCT_CHANGE = 2.0" in source
    assert "EARLY_OPEN_MIN_VOLUME = 15_000.0" in source
