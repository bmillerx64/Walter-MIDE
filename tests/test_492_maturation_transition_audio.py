from __future__ import annotations

from pathlib import Path

from mide import gs492_maturation_transition_audio as gs492


def _tf(*, bullish=True, above=True, flip_age=None, cross_new=False):
    return {
        "data_available": True,
        "current_supertrend_bullish": bullish,
        "current_above_vwap": above,
        "supertrend": bullish,
        "above_vwap": above,
        "bullish_flip_age_seconds": flip_age,
        "st_vwap_line_cross": {"new": cross_new},
    }


def _record(**overrides):
    record = {
        "symbol": "NCPL",
        "status": "WATCH NOW",
        "candidate_status": "Entry Ready",
        "vwap_distance_pct": 2.3,
        "qualified_for_entry": False,
        "qualified_for_alert": False,
        "participation_gate": {"passed": True},
        "structure_gate": {"passed": True},
        "timeframes": {
            "30s": _tf(),
            "1m": _tf(),
            "3m": _tf(bullish=False, above=True, flip_age=999.0),
        },
        "opportunity_pulse_previous": {
            "symbol": "NCPL",
            "status": "PASS",
            "candidate_status": "Watching",
        },
    }
    record.update(overrides)
    return record


def test_runner_building_speaks_when_30s_1m_align_before_3m():
    record = _record()
    event = gs492.maturation_transition(record)
    assert event["stage"] == "RUNNER_BUILDING"
    phrase = gs492.maturation_audio_phrase([record])
    assert "NCPL. RUNNER BUILDING. LOOK NOW." in phrase
    assert "3 minute confirmation is pending" in phrase
    assert "Attention only" in phrase


def test_ncpl_regression_3m_join_is_fresh_even_if_watch_now_already_existed():
    # Reproduces the Sep 18 failure mode: prior scan was already WATCH NOW, so GS473's
    # status-based freshness suppressed the important 3m maturation join.
    record = _record(
        vwap_distance_pct=15.1,
        timeframes={
            "30s": _tf(cross_new=True),
            "1m": _tf(cross_new=True),
            "3m": _tf(bullish=True, above=True, flip_age=120.0),
        },
        opportunity_pulse_previous={
            "symbol": "NCPL",
            "status": "WATCH NOW",
            "candidate_status": "Entry Ready",
        },
    )
    event = gs492.maturation_transition(record)
    assert event["stage"] == "RUNNER_DETECTED"
    assert event["structure_fresh"] is True

    phrase = gs492.maturation_audio_phrase([record])
    assert "NCPL. RUNNER DETECTED. LOOK NOW." in phrase
    assert "30 second, 1 minute, and 3 minute" in phrase
    assert "Extended 15.1 percent above VWAP" in phrase
    assert "Do not chase; watch for a reset" in phrase


def test_stale_three_rung_alignment_does_not_repeat_every_scan():
    record = _record(
        timeframes={
            "30s": _tf(cross_new=False),
            "1m": _tf(cross_new=False),
            "3m": _tf(bullish=True, above=True, flip_age=600.0),
        },
        opportunity_pulse_previous={
            "symbol": "NCPL",
            "status": "WATCH NOW",
            "candidate_status": "Entry Ready",
        },
    )
    event = gs492.maturation_transition(record)
    assert event["stage"] == "NONE"
    assert gs492.maturation_audio_phrase([record]) == ""


def test_failed_gate_blocks_runner_audio():
    record = _record(participation_gate={"passed": False})
    assert gs492.maturation_transition(record)["stage"] == "NONE"


def test_no_entry_or_alert_authority_is_granted():
    record = _record(
        timeframes={
            "30s": _tf(cross_new=True),
            "1m": _tf(),
            "3m": _tf(bullish=True, above=True, flip_age=60.0),
        }
    )
    event = gs492.maturation_transition(record)
    assert event["qualified_for_entry"] is False
    assert event["qualified_for_alert"] is False
    assert event["entry_authority_changed"] is False
    assert event["alert_authority_changed"] is False


def test_gs492_installs_after_gs477_at_final_late_boundary():
    source = Path("mide/gs414_final_enriched_opportunity_order.py").read_text(
        encoding="utf-8"
    )
    body = source.split("def install() -> None:", 1)[1]
    assert "_install_gs492()" in body
    assert body.index("_install_gs477()") < body.index("_install_gs492()")


def test_scope_lock_is_presentation_audio_only():
    source = Path("mide/gs492_maturation_transition_audio.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "opportunity_score =",
        "conviction_score =",
        "place_order(",
        "submit_order(",
        "execute_order(",
    )
    assert not any(token in source for token in forbidden)
    assert "OPERATOR_ATTENTION_AUDIO_ONLY" in source
    assert "entry_authority_changed" in source
