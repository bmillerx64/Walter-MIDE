from datetime import datetime, timezone
from pathlib import Path

from mide import gs411_scan_cadence_timing_truth as gs411


def _dt(epoch: float) -> datetime:
    return datetime.fromtimestamp(epoch, timezone.utc)


def test_due_observation_preserves_first_true_boundary_and_tracks_rechecks():
    state = {}
    first = gs411.record_due_observation(
        state,
        refresh_seconds=60,
        last_updated=_dt(1050.0),
        last_scan_attempt=_dt(1000.0),
        retry_seconds=5,
        observed_epoch=1063.0,
    )
    second = gs411.record_due_observation(
        state,
        refresh_seconds=60,
        last_updated=_dt(1050.0),
        last_scan_attempt=_dt(1000.0),
        retry_seconds=5,
        observed_epoch=1068.0,
    )

    assert first["scheduled_due_epoch"] == 1060.0
    assert first["first_observed_epoch"] == 1063.0
    assert second["first_observed_epoch"] == 1063.0
    assert second["last_observed_epoch"] == 1068.0
    assert second["due_true_count"] == 2
    assert second["cadence_mode"] == "refresh"


def test_due_observation_uses_retry_boundary_after_failed_attempt():
    state = {}
    event = gs411.record_due_observation(
        state,
        refresh_seconds=60,
        last_updated=_dt(990.0),
        last_scan_attempt=_dt(1000.0),
        retry_seconds=20,
        observed_epoch=1021.0,
    )

    assert event["scheduled_due_epoch"] == 1020.0
    assert event["cadence_mode"] == "retry"
    assert event["retry_seconds"] == 20


def test_autoscan_timing_truth_separates_scheduler_wait_from_scan_runtime(monkeypatch):
    state = {
        gs411.LAST_ATTEMPT_EPOCH_KEY: 1000.0,
        gs411.LAST_FINISHED_EPOCH_KEY: 1050.0,
        "last_scan_attempt": _dt(1065.0),
        gs411.DUE_EVENT_KEY: {
            "prior_attempt_epoch": 1000.0,
            "last_updated_epoch": 1050.0,
            "scheduled_due_epoch": 1060.0,
            "first_observed_epoch": 1061.0,
            "last_observed_epoch": 1061.0,
            "due_true_count": 1,
            "refresh_seconds": 60,
            "retry_seconds": 5,
            "cadence_mode": "refresh",
        },
        gs411.RERUN_DECISIONS_KEY: [
            {
                "observed_epoch": 1061.1,
                "reason": "rerun cooldown active",
                "allowed": False,
                "protect_post_scan": True,
                "process_scan_running": False,
            },
            {
                "observed_epoch": 1064.9,
                "reason": None,
                "allowed": True,
                "protect_post_scan": True,
                "process_scan_running": False,
            },
        ],
    }
    monkeypatch.setattr(gs411, "_gs409_wrapper_active", lambda: True)

    captured = gs411.capture_scan_acquired(state, acquired_epoch=1065.5)
    truth = gs411.build_scan_timing_truth(state, recorder_epoch=1110.0)

    assert captured["trigger"] == "autoscan_fragment"
    assert truth["authority"] == "OBSERVATIONAL_ONLY"
    assert truth["configured_refresh_seconds"] == 60
    assert truth["previous_start_to_current_attempt_ms"] == 65000.0
    assert truth["previous_finish_to_current_attempt_ms"] == 15000.0
    assert truth["scheduled_due_to_first_observed_ms"] == 1000.0
    assert truth["first_due_observed_to_attempt_ms"] == 4000.0
    assert truth["attempt_to_watchdog_acquire_ms"] == 500.0
    assert truth["watchdog_acquire_to_recorder_ms"] == 44500.0
    assert truth["attempt_to_recorder_ms"] == 45000.0
    assert [item["reason"] for item in truth["rerun_decisions"]] == [
        "rerun cooldown active",
        None,
    ]
    assert truth["gs409_wrapper_active"] is True


def test_manual_request_wins_over_stale_autoscan_due_event(monkeypatch):
    state = {
        gs411.LAST_ATTEMPT_EPOCH_KEY: 1900.0,
        gs411.LAST_FINISHED_EPOCH_KEY: 1950.0,
        "last_scan_attempt": _dt(2001.0),
        "_walter_scan_requested_epoch": 2000.0,
        gs411.DUE_EVENT_KEY: {
            "prior_attempt_epoch": 1900.0,
            "scheduled_due_epoch": 1960.0,
            "first_observed_epoch": 1961.0,
            "last_observed_epoch": 1961.0,
            "due_true_count": 1,
            "refresh_seconds": 60,
            "retry_seconds": 5,
            "cadence_mode": "refresh",
        },
    }
    monkeypatch.setattr(gs411, "_gs409_wrapper_active", lambda: True)

    event = gs411.capture_scan_acquired(state, acquired_epoch=2001.2)
    truth = gs411.build_scan_timing_truth(state, recorder_epoch=2010.0)

    assert event["trigger"] == "manual"
    assert event["due_event"] is None
    assert truth["manual_request_to_attempt_ms"] == 1000.0
    assert truth["scheduled_due_at"] is None


def test_finish_boundary_is_saved_for_the_next_scan():
    state = {}
    assert gs411.capture_scan_finished(state, finished_epoch=1234.5) == 1234.5
    assert state[gs411.LAST_FINISHED_EPOCH_KEY] == 1234.5


def test_rerun_decision_observation_preserves_reason_and_caps_history():
    state = {}
    for index in range(gs411.MAX_RERUN_DECISIONS + 3):
        gs411.record_rerun_decision(
            state,
            reason="post-scan render cooldown" if index == 0 else None,
            protect_post_scan=True,
            process_scan_running=False,
            observed_epoch=1000.0 + index,
        )

    history = state[gs411.RERUN_DECISIONS_KEY]
    assert len(history) == gs411.MAX_RERUN_DECISIONS
    assert history[-1]["reason"] is None
    assert history[-1]["allowed"] is True


def test_attached_timing_truth_does_not_mutate_scan_or_trading_records(monkeypatch):
    state = {
        gs411.CURRENT_SCAN_KEY: {
            "trigger": "fallback_or_initial",
            "attempt_epoch": 1000.0,
            "acquired_epoch": 1000.25,
            "rerun_decisions": [],
            "gs409_wrapper_active": True,
        }
    }
    scan = {"scan_id": "scan-1", "symbols": [{"symbol": "TEST"}]}
    original = {"scan_id": "scan-1", "symbols": [{"symbol": "TEST"}]}

    enriched = gs411.attach_scan_timing_truth(
        scan, state, recorder_epoch=1045.0
    )

    assert scan == original
    assert enriched["scan_id"] == "scan-1"
    assert enriched["symbols"] == [{"symbol": "TEST"}]
    assert enriched["scan_timing_truth"]["attempt_to_recorder_ms"] == 45000.0
    assert enriched["scan_timing_truth"]["watchdog_acquire_to_recorder_ms"] == 44750.0


def test_gs411_installs_after_gs408_at_safe_late_boundary():
    source = Path("mide/gs392_operator_order_audio.py").read_text()
    gs408 = source.index("install_gs408()")
    gs411_import = source.index(
        "from .gs411_scan_cadence_timing_truth import install as install_gs411"
    )
    gs411_call = source.index("install_gs411()")

    assert gs408 < gs411_import < gs411_call


def test_gs411_installers_are_idempotence_guarded():
    source = Path("mide/gs411_scan_cadence_timing_truth.py").read_text()

    assert source.count('_gs411_scan_cadence_timing_truth", False') == 5
    assert "session_controls.autoscan_request_due = due_with_observation" in source
    assert "session_controls.begin_scheduled_scan = begin_with_observation" in source
    assert "session_controls.finish_scan = finish_with_observation" in source
    assert "reruns.rerun_suppression_reason = reason_with_observation" in source
    assert "flight_recorder.persist_replayable_scan = persist_with_timing" in source


def test_gs411_is_observational_only_not_trading_authority():
    source = Path("mide/gs411_scan_cadence_timing_truth.py").read_text()
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "participation_score =",
        "expansion_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "opportunity_state =",
    )

    assert not any(token in source for token in forbidden)
