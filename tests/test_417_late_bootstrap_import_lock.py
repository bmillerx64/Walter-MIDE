from pathlib import Path


def test_parent_package_does_not_import_late_gs384_bootstrap():
    """The parent package lock must never wait on the late GS384 module lock."""
    source = Path("mide/__init__.py").read_text()
    assert "gs384_diagnostic_signal_to_noise" not in source
    assert "_install_gs384" not in source


def test_startup_hook_owns_the_gs384_late_bootstrap():
    """app.py's post-package startup hook remains the sole runtime entry point."""
    source = Path("mide/startup.py").read_text()
    function_start = source.index("def ensure_late_runtime_installers()")
    import_line = source.index("from .gs384_diagnostic_signal_to_noise import install", function_start)
    install_line = source.index("    install()", import_line)
    app_boundary = source.index('if component == "entering app.py":')
    call_line = source.index("ensure_late_runtime_installers()", app_boundary)
    assert function_start < import_line < install_line
    assert app_boundary < call_line


def test_late_bootstrap_remains_after_parent_import_boundary():
    """The app entry log must still run before provider/UI imports bind live callables."""
    app_source = Path("app.py").read_text()
    entry = app_source.index('log_startup("entering app.py")')
    provider_import = app_source.index("from mide.config import Settings")
    ui_import = app_source.index("from mide.ui import (")
    assert entry < provider_import < ui_import


def test_gs417_does_not_touch_trading_authority():
    combined = (
        Path("mide/__init__.py").read_text()
        + Path("mide/startup.py").read_text()
        + Path("tests/test_417_late_bootstrap_import_lock.py").read_text()
    )
    forbidden_assignments = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "participation_score =",
        "expansion_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "trigger_diagnostics =",
        "opportunity_state =",
    )
    assert not any(token in combined for token in forbidden_assignments)
