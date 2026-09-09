from pathlib import Path

from mide import gs384_diagnostic_signal_to_noise as gs384
from mide import startup


def test_gs384_defers_nested_late_imports_while_parent_package_initializes():
    source = Path("mide/gs384_diagnostic_signal_to_noise.py").read_text()
    guard = source.index("if _package_initializing():")
    first_late_import = source.index(
        "from .gs386_30s_observational_recorder import install as install_gs386"
    )
    assert guard < first_late_import


def test_app_entry_log_is_the_only_startup_log_that_triggers_late_chain(monkeypatch):
    calls = []
    monkeypatch.setattr(startup, "ensure_late_runtime_installers", lambda: calls.append("late"))

    startup.log_startup("initializing Webull provider")
    assert calls == []

    startup.log_startup("entering app.py")
    assert calls == ["late"]


def test_gs384_package_initializing_helper_is_false_after_normal_import():
    assert gs384._package_initializing() is False


def test_runtime_entry_point_exists_before_app_imports_provider_and_ui_names():
    app_source = Path("app.py").read_text()
    entry = app_source.index('log_startup("entering app.py")')
    provider_import = app_source.index("from mide.config import Settings")
    ui_import = app_source.index("from mide.ui import (")
    assert entry < provider_import < ui_import


def test_gs410_changes_bootstrap_only_not_trading_authority():
    combined = (
        Path("mide/gs384_diagnostic_signal_to_noise.py").read_text()
        + Path("mide/startup.py").read_text()
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "participation_score =",
        "expansion_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "opportunity_state =",
    )
    assert not any(token in combined for token in forbidden)
