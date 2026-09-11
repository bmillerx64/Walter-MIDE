from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from mide import gs413_single_process_autoscan_authority as gs413
from mide import gs435_due_deadline_owner_handoff as gs435
from mide import session_controls


def setup_function():
    gs413._reset_process_authority_for_tests()


def _due_chain(*, authority_result=False, observations=None):
    observations = observations if observations is not None else []

    def raw_due(
        refresh_seconds,
        last_updated,
        last_scan_attempt,
        *,
        retry_seconds=5,
        now=None,
    ):
        current = now or datetime.now(timezone.utc)
        retry_pending = bool(
            last_scan_attempt
            and (last_updated is None or last_scan_attempt > last_updated)
        )
        threshold = retry_seconds if retry_pending else refresh_seconds
        return bool(
            last_scan_attempt
            and (current - last_scan_attempt).total_seconds() >= threshold
        )

    def observed_due(*args, **kwargs):
        result = raw_due(*args, **kwargs)
        if result:
            observations.append((args, kwargs))
        return result

    observed_due._gs411_scan_cadence_timing_truth = True
    observed_due._gs411_original = raw_due

    def authority_due(*args, **kwargs):
        return bool(authority_result)

    authority_due._gs413_single_process_autoscan_authority = True
    authority_due._gs413_original = observed_due
    return authority_due, raw_due, observed_due, observations


def _prime_abandoned_owner(started: datetime, *, heartbeat=10.0):
    gs413._PROCESS_CADENCE_OWNER = "old-owner"
    gs413._PROCESS_CADENCE_HEARTBEAT = heartbeat
    gs413._PROCESS_LAST_SCAN_START = started


def test_passive_session_claims_due_deadline_without_waiting_for_120s_lease(monkeypatch):
    started = datetime(2026, 9, 11, 13, 29, 37, tzinfo=timezone.utc)
    completed = started + timedelta(seconds=20)
    state = {}
    authority_due, _raw, _observed, observations = _due_chain()

    monkeypatch.setattr(session_controls, "autoscan_request_due", authority_due)
    monkeypatch.setattr(gs413, "_session_state", lambda: state)
    monkeypatch.setattr(gs413, "_process_scan_running", lambda: False)
    monkeypatch.setattr(gs413, "_now_monotonic", lambda: 100.0)
    _prime_abandoned_owner(started, heartbeat=10.0)

    gs435.install()
    due = session_controls.autoscan_request_due(
        60,
        completed,
        started,
        retry_seconds=5,
        now=started + timedelta(seconds=61),
    )

    assert due is True
    assert gs413._PROCESS_CADENCE_OWNER == state[gs413.SESSION_TOKEN_KEY]
    assert gs413._PROCESS_CADENCE_HEARTBEAT == 100.0
    assert len(observations) == 1
    assert observations[0][0][2] == started
    diagnostic = state[gs435.DIAGNOSTIC_KEY]
    assert diagnostic["authority"] == "ORCHESTRATION_LATENCY_ONLY"
    assert diagnostic["previous_owner_present"] is True
    assert diagnostic["trading_logic_changed"] is False


def test_not_due_does_not_transfer_owner(monkeypatch):
    started = datetime(2026, 9, 11, 13, 29, 37, tzinfo=timezone.utc)
    completed = started + timedelta(seconds=20)
    state = {}
    authority_due, _raw, _observed, observations = _due_chain()

    monkeypatch.setattr(session_controls, "autoscan_request_due", authority_due)
    monkeypatch.setattr(gs413, "_session_state", lambda: state)
    monkeypatch.setattr(gs413, "_process_scan_running", lambda: False)
    monkeypatch.setattr(gs413, "_now_monotonic", lambda: 100.0)
    _prime_abandoned_owner(started, heartbeat=10.0)

    gs435.install()
    due = session_controls.autoscan_request_due(
        60,
        completed,
        started,
        now=started + timedelta(seconds=59),
    )

    assert due is False
    assert gs413._PROCESS_CADENCE_OWNER == "old-owner"
    assert observations == []
    assert gs435.DIAGNOSTIC_KEY not in state


def test_recent_owner_heartbeat_wins_race_guard(monkeypatch):
    started = datetime(2026, 9, 11, 13, 29, 37, tzinfo=timezone.utc)
    completed = started + timedelta(seconds=20)
    state = {}
    authority_due, _raw, _observed, observations = _due_chain()

    monkeypatch.setattr(session_controls, "autoscan_request_due", authority_due)
    monkeypatch.setattr(gs413, "_session_state", lambda: state)
    monkeypatch.setattr(gs413, "_process_scan_running", lambda: False)
    monkeypatch.setattr(gs413, "_now_monotonic", lambda: 100.0)
    _prime_abandoned_owner(started, heartbeat=99.25)

    gs435.install()
    due = session_controls.autoscan_request_due(
        60,
        completed,
        started,
        now=started + timedelta(seconds=61),
    )

    assert due is False
    assert gs413._PROCESS_CADENCE_OWNER == "old-owner"
    assert observations == []


def test_watchdog_running_remains_absolute_no_overlap_authority(monkeypatch):
    started = datetime(2026, 9, 11, 13, 29, 37, tzinfo=timezone.utc)
    state = {}
    authority_due, _raw, _observed, observations = _due_chain()

    monkeypatch.setattr(session_controls, "autoscan_request_due", authority_due)
    monkeypatch.setattr(gs413, "_session_state", lambda: state)
    monkeypatch.setattr(gs413, "_process_scan_running", lambda: True)
    _prime_abandoned_owner(started, heartbeat=10.0)

    gs435.install()
    due = session_controls.autoscan_request_due(
        60,
        started + timedelta(seconds=20),
        started,
        now=started + timedelta(seconds=90),
    )

    assert due is False
    assert gs413._PROCESS_CADENCE_OWNER == "old-owner"
    assert observations == []


def test_manual_request_is_never_reclassified_as_deadline_handoff(monkeypatch):
    started = datetime(2026, 9, 11, 13, 29, 37, tzinfo=timezone.utc)
    state = {session_controls.SCAN_REQUESTED_AT_KEY: 12345.0}
    authority_due, _raw, _observed, observations = _due_chain()

    monkeypatch.setattr(session_controls, "autoscan_request_due", authority_due)
    monkeypatch.setattr(gs413, "_session_state", lambda: state)
    monkeypatch.setattr(gs413, "_process_scan_running", lambda: False)
    monkeypatch.setattr(gs413, "_now_monotonic", lambda: 100.0)
    _prime_abandoned_owner(started, heartbeat=10.0)

    gs435.install()
    due = session_controls.autoscan_request_due(
        60,
        started + timedelta(seconds=20),
        started,
        now=started + timedelta(seconds=90),
    )

    assert due is False
    assert state[session_controls.SCAN_REQUESTED_AT_KEY] == 12345.0
    assert gs413._PROCESS_CADENCE_OWNER == "old-owner"
    assert observations == []


def test_changed_process_baseline_blocks_stale_takeover(monkeypatch):
    expected = datetime(2026, 9, 11, 13, 29, 37, tzinfo=timezone.utc)
    newer = expected + timedelta(seconds=60)
    state = {}
    monkeypatch.setattr(gs413, "_process_scan_running", lambda: False)
    monkeypatch.setattr(gs413, "_now_monotonic", lambda: 100.0)
    _prime_abandoned_owner(newer, heartbeat=10.0)

    assert gs435._claim_due_owner(state, expected_scan_start=expected) is False
    assert gs413._PROCESS_CADENCE_OWNER == "old-owner"


def test_healthy_gs413_owner_path_is_not_recomputed_or_replaced(monkeypatch):
    started = datetime(2026, 9, 11, 13, 29, 37, tzinfo=timezone.utc)
    state = {}
    authority_due, _raw, _observed, observations = _due_chain(authority_result=True)

    monkeypatch.setattr(session_controls, "autoscan_request_due", authority_due)
    monkeypatch.setattr(gs413, "_session_state", lambda: state)
    _prime_abandoned_owner(started, heartbeat=10.0)

    gs435.install()
    assert session_controls.autoscan_request_due(
        60,
        started + timedelta(seconds=20),
        started,
        now=started + timedelta(seconds=61),
    ) is True

    assert gs413._PROCESS_CADENCE_OWNER == "old-owner"
    assert observations == []
    assert gs435.DIAGNOSTIC_KEY not in state


def test_startup_installs_gs435_after_gs428_and_scope_is_orchestration_only():
    startup = Path("mide/startup.py").read_text(encoding="utf-8")
    source = Path("mide/gs435_due_deadline_owner_handoff.py").read_text(encoding="utf-8")

    assert startup.index("install_gs428()") < startup.index("install_gs435()")
    assert gs435.AUTHORITY == "ORCHESTRATION_LATENCY_ONLY"
    forbidden = (
        'record["qualified_for_entry"] =',
        'record["qualified_for_alert"] =',
        'record["participation_score"] =',
        'record["expansion_score"] =',
        'record["vwap_distance_pct"] =',
        "client.bars(",
        "play_alert(",
    )
    assert not any(token in source for token in forbidden)


def test_requirements_marker_forces_clean_runtime_without_dependency_change():
    requirements = Path("requirements.txt").read_text(encoding="utf-8")
    assert "GS435 deployment marker" in requirements
    assert "streamlit==1.62.0" in requirements
    assert "webull-openapi-python-sdk==2.0.16" in requirements
