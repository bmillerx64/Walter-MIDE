from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import mide.gs413_single_process_autoscan_authority as gs413
from mide.session_controls import SCAN_REQUESTED_AT_KEY, SCAN_REQUESTED_KEY


def setup_function():
    gs413._reset_process_authority_for_tests()


def test_one_session_owns_process_autoscan_until_lease_expires():
    owner = {}
    passive = {}

    assert gs413.cadence_owner_allows(
        owner, process_scan_running=False, now_monotonic=100.0
    ) is True
    assert gs413.cadence_owner_allows(
        passive, process_scan_running=False, now_monotonic=150.0
    ) is False

    # A stale owner can be replaced only while provider work is idle.
    assert gs413.cadence_owner_allows(
        passive, process_scan_running=True, now_monotonic=221.0
    ) is False
    assert gs413.cadence_owner_allows(
        passive, process_scan_running=False, now_monotonic=221.0
    ) is True
    assert gs413.cadence_owner_allows(
        owner, process_scan_running=False, now_monotonic=222.0
    ) is False


def test_actual_watchdog_start_becomes_shared_cadence_baseline():
    state = {}
    started = datetime(2026, 9, 10, 13, 30, tzinfo=timezone.utc)

    observed = gs413._record_actual_scan_start(
        state,
        automatic=True,
        started_at=started,
        now_monotonic=500.0,
    )

    assert observed is started
    assert state["last_scan_attempt"] is started
    assert gs413._process_scan_start() is started
    assert gs413.cadence_owner_allows(
        state, process_scan_running=False, now_monotonic=501.0
    ) is True


def test_passive_scheduler_view_cannot_trigger_completion_time_fallback():
    owner = {}
    passive = {SCAN_REQUESTED_KEY: True}
    completed_at = datetime(2026, 9, 10, 13, 31, tzinfo=timezone.utc)
    scheduler_now = completed_at + timedelta(seconds=90)
    scan = SimpleNamespace(provider="WEBULL", completed_at=completed_at)

    assert gs413.cadence_owner_allows(
        owner, process_scan_running=False, now_monotonic=1000.0
    ) is True

    projected = gs413.scheduler_scan_projection(
        scan,
        passive,
        "scheduler",
        process_scan_running=False,
        now=scheduler_now,
        now_monotonic=1001.0,
    )

    assert projected is not scan
    assert projected.completed_at == scheduler_now
    assert scan.completed_at == completed_at
    assert passive[SCAN_REQUESTED_KEY] is False


def test_passive_scheduler_never_clears_explicit_manual_request():
    owner = {}
    manual = {
        SCAN_REQUESTED_KEY: True,
        SCAN_REQUESTED_AT_KEY: 1234.5,
    }
    completed_at = datetime(2026, 9, 10, 13, 31, tzinfo=timezone.utc)
    scan = SimpleNamespace(provider="WEBULL", completed_at=completed_at)

    assert gs413.cadence_owner_allows(
        owner, process_scan_running=False, now_monotonic=2000.0
    ) is True

    projected = gs413.scheduler_scan_projection(
        scan,
        manual,
        "scheduler",
        process_scan_running=False,
        now=completed_at + timedelta(seconds=90),
        now_monotonic=2001.0,
    )

    assert projected is not scan
    assert manual[SCAN_REQUESTED_KEY] is True
    assert manual[SCAN_REQUESTED_AT_KEY] == 1234.5


def test_trader_facing_completed_scan_timestamp_is_never_projected():
    owner = {}
    passive = {}
    completed_at = datetime(2026, 9, 10, 13, 31, tzinfo=timezone.utc)
    scan = SimpleNamespace(provider="WEBULL", completed_at=completed_at)

    assert gs413.cadence_owner_allows(
        owner, process_scan_running=False, now_monotonic=3000.0
    ) is True

    observed = gs413.scheduler_scan_projection(
        scan,
        passive,
        "Radar",
        process_scan_running=False,
        now=completed_at + timedelta(seconds=90),
        now_monotonic=3001.0,
    )

    assert observed is scan
    assert observed.completed_at == completed_at


def test_gs413_is_installed_after_gs411_lifecycle_timing():
    source = Path("mide/gs392_operator_order_audio.py").read_text(encoding="utf-8")

    gs411 = source.index("install_gs411()")
    gs413 = source.index("install_gs413()")

    assert gs411 < gs413
    assert "gs413_single_process_autoscan_authority" in source
