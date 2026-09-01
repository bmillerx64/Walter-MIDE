from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from mide.completed_scan import COMPLETED_SCAN_KEY, LAST_SCAN_FAILURE_KEY
from mide.gs355_runtime_truth_banner import (
    STALE_AUTO_SCAN_SECONDS,
    _banner_html,
    runtime_truth_snapshot,
)
from mide.session_controls import AUTO_SCAN_KEY, SCAN_RUNNING_KEY


def _ready_native(monkeypatch):
    monkeypatch.setattr(
        "mide.gs347_native_radar_timeout_health.runtime_health",
        lambda: {"state": "READY", "timeout_count": 0},
    )


def test_auto_scan_stale_completed_result_is_degraded(monkeypatch):
    _ready_native(monkeypatch)
    now = datetime(2026, 9, 1, 20, 30, tzinfo=timezone.utc)
    state = {
        COMPLETED_SCAN_KEY: SimpleNamespace(
            completed_at=now - timedelta(seconds=STALE_AUTO_SCAN_SECONDS + 1)
        ),
        AUTO_SCAN_KEY: True,
        SCAN_RUNNING_KEY: False,
    }
    snapshot = runtime_truth_snapshot(state, now=now)
    assert snapshot["state"] == "DEGRADED"
    assert "No completed auto-scan" in snapshot["reason"]


def test_old_manual_scan_does_not_create_false_stale_alarm(monkeypatch):
    _ready_native(monkeypatch)
    now = datetime(2026, 9, 1, 20, 30, tzinfo=timezone.utc)
    state = {
        COMPLETED_SCAN_KEY: SimpleNamespace(completed_at=now - timedelta(minutes=30)),
        AUTO_SCAN_KEY: False,
        SCAN_RUNNING_KEY: False,
    }
    assert runtime_truth_snapshot(state, now=now)["state"] == "READY"


def test_newer_scan_failure_overrides_old_green_result(monkeypatch):
    _ready_native(monkeypatch)
    now = datetime(2026, 9, 1, 20, 30, tzinfo=timezone.utc)
    state = {
        COMPLETED_SCAN_KEY: SimpleNamespace(completed_at=now - timedelta(minutes=2)),
        LAST_SCAN_FAILURE_KEY: {
            "attempted_at": now - timedelta(seconds=20),
            "message": "provider call failed",
        },
        AUTO_SCAN_KEY: True,
        SCAN_RUNNING_KEY: False,
    }
    snapshot = runtime_truth_snapshot(state, now=now)
    assert snapshot["state"] == "DEGRADED"
    assert snapshot["reason"] == "provider call failed"


def test_browser_banner_can_age_without_server_rerender():
    html = _banner_html(
        {
            "state": "READY",
            "reason": "",
            "scan_age_seconds": 5,
            "auto_scan": True,
            "webull_native_state": "READY",
            "suppressed_reruns": 0,
        }
    )
    assert "setInterval(tick,1000)" in html
    assert "RUNTIME STALE" in html
    assert "CONNECTING" in html
