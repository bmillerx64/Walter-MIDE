import pytest

from mide.watchdog import ScanAlreadyRunning, ScanWatchdog


def test_successful_scan_has_short_process_handoff_guard_before_duplicate_start():
    now = [100.0]
    watchdog = ScanWatchdog(
        max_attempts=1,
        monotonic=lambda: now[0],
        completed_handoff_guard_seconds=10.0,
    )

    assert watchdog.run(lambda: "first") == "first"

    now[0] = 103.0
    with pytest.raises(ScanAlreadyRunning, match="cross-session handoff"):
        watchdog.run(lambda: "duplicate")

    now[0] = 110.0
    assert watchdog.run(lambda: "next cadence owner") == "next cadence owner"


def test_handoff_rejection_does_not_claim_scan_lifecycle_callbacks():
    now = [200.0]
    watchdog = ScanWatchdog(
        max_attempts=1,
        monotonic=lambda: now[0],
        completed_handoff_guard_seconds=10.0,
    )
    lifecycle = []

    assert watchdog.run(
        lambda: "first",
        on_acquired=lambda: lifecycle.append("first begin"),
        on_finished=lambda: lifecycle.append("first finish"),
    ) == "first"
    assert lifecycle == ["first begin", "first finish"]

    now[0] = 204.0
    with pytest.raises(ScanAlreadyRunning):
        watchdog.run(
            lambda: "duplicate",
            on_acquired=lambda: lifecycle.append("duplicate begin"),
            on_finished=lambda: lifecycle.append("duplicate finish"),
        )

    assert lifecycle == ["first begin", "first finish"]
    assert watchdog.is_running is False


def test_terminal_failure_is_not_guarded_and_can_retry_immediately_on_next_run():
    now = [300.0]
    watchdog = ScanWatchdog(
        max_attempts=1,
        monotonic=lambda: now[0],
        completed_handoff_guard_seconds=10.0,
    )

    with pytest.raises(RuntimeError, match="temporary"):
        watchdog.run(lambda: (_ for _ in ()).throw(RuntimeError("temporary")))

    now[0] = 301.0
    assert watchdog.run(lambda: "recovered") == "recovered"
