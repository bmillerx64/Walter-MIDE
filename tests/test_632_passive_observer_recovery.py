from __future__ import annotations

from pathlib import Path


def _live_clock_block() -> str:
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("transport_recovery_ms = 45_000")
    end = source.index("\ndef _run_live_pipeline(", start)
    return source[start:end]


def test_gs632_adds_passive_observer_stale_view_recovery():
    block = _live_clock_block()
    assert "passive_observer_recovery_ms = 45_000" in block
    assert "const passiveObserverRecoveryMs =" in block
    assert "const passiveObserverRecoveryDue =" in block
    assert "&& processOwned" in block
    assert "overdueSeconds * 1000 >= passiveObserverRecoveryMs" in block
    assert "REFRESHING STALE VIEW" in block


def test_existing_connecting_recovery_remains_intact():
    block = _live_clock_block()
    assert "const recoveryDue = recoveryBaselinePresent" in block
    assert "nativeStreamlitConnecting()" in block
    assert "overdueSeconds * 1000 >= transportRecoveryMs" in block
    assert "RECONNECTING STREAMLIT" in block


def test_gs632_recycles_browser_only_and_does_not_request_scans():
    block = _live_clock_block()
    assert "forceTopLevelRecovery()" in block
    assert "root.location.replace(href)" in block
    forbidden = (
        "run_live_scan(",
        "_run_live_pipeline(",
        "request_scan(",
        "scan_once(",
        "submit_order(",
        "place_order(",
        "execute_order(",
    )
    assert not any(token in block for token in forbidden)


def test_recovery_keeps_same_baseline_cooldown_guard():
    block = _live_clock_block()
    assert "recoveryState.baselineAt !== baselineAt" in block
    assert "transportRecoveryCooldownMs" in block
    assert "JSON.stringify({{baselineAt, recoveredAt: now}})" in block


def test_gs635_stale_recovery_escapes_component_iframe_sandbox():
    block = _live_clock_block()
    assert "const forceTopLevelRecovery = () =>" in block
    assert "walter-stale-view-recovery" in block
    assert "meta.httpEquiv = 'refresh'" in block
    assert "meta.content = `0;url=${{href}}`" in block
    assert "(root.document.head || root.document.documentElement).appendChild(meta)" in block
