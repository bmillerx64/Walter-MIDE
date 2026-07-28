import threading

import pytest

from mide.watchdog import ScanAlreadyRunning, ScanWatchdog


def test_watchdog_retries_with_backoff_and_recreates_scan_resources():
    sleeps = []
    resources = []
    repairs = []
    watchdog = ScanWatchdog(max_attempts=3, backoff_seconds=(1, 3), sleep=sleeps.append)

    def scan():
        resource = object()
        resources.append(resource)
        if len(resources) < 3:
            raise KeyError("mide.scanner_v2")
        return "recovered"

    assert watchdog.run(scan, before_retry=lambda: repairs.append(True)) == "recovered"
    assert len(resources) == 3
    assert sleeps == [1, 3]
    assert repairs == [True, True]
    assert [failure.error_type for failure in watchdog.last_failures] == ["KeyError", "KeyError"]


def test_watchdog_releases_lock_after_terminal_failure():
    watchdog = ScanWatchdog(max_attempts=1)

    with pytest.raises(RuntimeError, match="temporary"):
        watchdog.run(lambda: (_ for _ in ()).throw(RuntimeError("temporary")))

    assert watchdog.run(lambda: "next scan") == "next scan"


def test_watchdog_rejects_overlapping_scans():
    watchdog = ScanWatchdog(max_attempts=1)
    entered = threading.Event()
    release = threading.Event()

    def blocking_scan():
        entered.set()
        release.wait(timeout=2)

    worker = threading.Thread(target=lambda: watchdog.run(blocking_scan))
    worker.start()
    assert entered.wait(timeout=1)
    with pytest.raises(ScanAlreadyRunning):
        watchdog.run(lambda: None)
    release.set()
    worker.join(timeout=2)
    assert not worker.is_alive()
