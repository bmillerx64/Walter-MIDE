from datetime import datetime, timezone
from types import SimpleNamespace

from mide import gs374_header_scan_truth as scan_truth
from mide import ui
from mide.version import BUILD


def _base_header(*args, **kwargs):
    return (
        "<div class='control-version'>"
        f"v{BUILD.version} · {BUILD.git_sha} · {BUILD.built_at}"
        "</div>"
    )


def test_header_timestamp_is_last_completed_scan_not_build_time(monkeypatch):
    completed = SimpleNamespace(
        completed_at=datetime(2026, 9, 3, 15, 26, 55, tzinfo=timezone.utc)
    )
    monkeypatch.setattr(
        scan_truth,
        "completed_scan_for_view",
        lambda state, view: completed,
    )
    monkeypatch.setattr(ui, "mission_control_header_markup", _base_header)
    monkeypatch.setattr(ui, "st", SimpleNamespace(session_state={}))

    scan_truth.install()
    markup = ui.mission_control_header_markup()

    assert "Last scan: 11:26:55 AM EDT" in markup
    assert BUILD.built_at not in markup
    assert BUILD.git_sha in markup


def test_header_without_completed_scan_does_not_show_deploy_time(monkeypatch):
    monkeypatch.setattr(
        scan_truth,
        "completed_scan_for_view",
        lambda state, view: None,
    )
    monkeypatch.setattr(ui, "mission_control_header_markup", _base_header)
    monkeypatch.setattr(ui, "st", SimpleNamespace(session_state={}))

    scan_truth.install()
    markup = ui.mission_control_header_markup()

    assert "Last scan: waiting" in markup
    assert BUILD.built_at not in markup


def test_header_scan_truth_install_is_idempotent(monkeypatch):
    monkeypatch.setattr(
        scan_truth,
        "completed_scan_for_view",
        lambda state, view: None,
    )
    monkeypatch.setattr(ui, "mission_control_header_markup", _base_header)
    monkeypatch.setattr(ui, "st", SimpleNamespace(session_state={}))

    scan_truth.install()
    installed = ui.mission_control_header_markup
    scan_truth.install()

    assert ui.mission_control_header_markup is installed
    assert getattr(installed, "_gs374_header_scan_truth", False) is True


def test_startup_binds_header_scan_truth_before_app_imports_ui():
    from mide import startup

    assert hasattr(startup, "ensure_header_scan_truth")
    # The full suite intentionally monkeypatches/reinstalls older presentation
    # wrappers in other tests. Importing an already-cached startup module does not
    # rerun module-level side effects, so explicitly exercise the binding helper
    # whose production call occurs during startup before app.py imports UI names.
    startup.ensure_header_scan_truth()
    assert getattr(ui.mission_control_header_markup, "_gs374_header_scan_truth", False)
