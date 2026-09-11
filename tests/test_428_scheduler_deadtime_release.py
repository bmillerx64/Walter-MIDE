from pathlib import Path
from types import SimpleNamespace

import pytest

from mide import gs428_scheduler_deadtime_release as gs428
from mide import session_controls, watchdog


def _gs413_due(*args, **kwargs):
    return False


_gs413_due._gs413_single_process_autoscan_authority = True


def test_gs428_releases_only_production_singleton_guard_after_gs413(monkeypatch):
    fake_watchdog = SimpleNamespace(completed_handoff_guard_seconds=10.0)
    monkeypatch.setattr(session_controls, "autoscan_request_due", _gs413_due)
    monkeypatch.setattr(watchdog, "PROCESS_SCAN_WATCHDOG", fake_watchdog)
    monkeypatch.setattr(gs428, "_INSTALLED", False)

    gs428.install()

    assert fake_watchdog.completed_handoff_guard_seconds == 0.0
    assert fake_watchdog._walter_gs428_previous_handoff_guard_seconds == 10.0
    assert fake_watchdog._walter_gs428_scheduler_deadtime_release is True
    assert fake_watchdog._walter_gs428_authority == "ORCHESTRATION_LATENCY_ONLY"


def test_gs428_refuses_to_remove_guard_without_gs413(monkeypatch):
    def legacy_due(*args, **kwargs):
        return False

    fake_watchdog = SimpleNamespace(completed_handoff_guard_seconds=10.0)
    monkeypatch.setattr(session_controls, "autoscan_request_due", legacy_due)
    monkeypatch.setattr(watchdog, "PROCESS_SCAN_WATCHDOG", fake_watchdog)
    monkeypatch.setattr(gs428, "_INSTALLED", False)

    with pytest.raises(RuntimeError, match="requires GS413"):
        gs428.install()

    assert fake_watchdog.completed_handoff_guard_seconds == 10.0


def test_gs428_installs_after_gs427_latency_truth_boundary():
    source = Path("mide/startup.py").read_text(encoding="utf-8")

    gs427 = source.index("install_gs427()")
    gs428 = source.index("install_gs428()")

    assert gs427 < gs428


def test_gs428_deployment_marker_forces_clean_runtime_without_dependency_change():
    requirements = Path("requirements.txt").read_text(encoding="utf-8")

    assert "GS428 deployment marker" in requirements
    assert "webull-openapi-python-sdk==2.0.16" in requirements
    assert "streamlit==1.62.0" in requirements
