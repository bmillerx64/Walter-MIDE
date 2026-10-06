from __future__ import annotations

from pathlib import Path


SOURCE = Path("app.py").read_text(encoding="utf-8")


def test_gs645_only_explicit_manual_request_can_reset_latched_webull_auth():
    assert "_explicit_manual_scan_request = bool(" in SOURCE
    assert "st.session_state.get(SCAN_REQUESTED_AT_KEY) is not None" in SOURCE
    assert "_webull_auth_latched = bool(" in SOURCE
    assert "if _webull_auth_latched and should_scan and not _explicit_manual_scan_request:" in SOURCE
    assert "st.session_state[SCAN_REQUESTED_KEY] = False" in SOURCE
    assert "should_scan = False" in SOURCE


def test_gs645_manual_recovery_detaches_provider_alias_and_clears_expired_token():
    start = SOURCE.index(
        "if _webull_auth_latched and _explicit_manual_scan_request:"
    )
    end = SOURCE.index("\n    try:\n        repair_mide_module_links()", start)
    block = SOURCE[start:end]

    assert 'retire_process_live_provider("WEBULL_OPENAPI_PRIMARY")' in block
    assert "scan_context(st.session_state).provider_instance = None" in block
    assert '".prepare_fresh_authorization()' not in block
    assert ").prepare_fresh_authorization()" in block
    assert "runtime_token_files_removed" in block


def test_gs645_recovery_runs_before_manual_watchdog_scan():
    recovery = SOURCE.index(
        "if _webull_auth_latched and _explicit_manual_scan_request:"
    )
    watchdog = SOURCE.index(
        "records, universe_count, prefiltered, warnings, diagnostics = watchdog.run(",
        recovery,
    )
    assert recovery < watchdog


def test_gs645_success_still_clears_process_auth_latch():
    manual_start = SOURCE.index(
        "if mode.startswith(\"Live \") and should_scan"
    )
    manual_block = SOURCE[manual_start:SOURCE.index("completed_scan =", manual_start)]

    assert "_clear_webull_auth_backoff(_gs585.process_state())" in manual_block


def test_gs645_scope_does_not_change_market_or_trading_authority():
    start = SOURCE.index("_explicit_manual_scan_request = bool(")
    end = SOURCE.index("completed_scan =", start)
    block = SOURCE[start:end]
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "opportunity_score =",
        "conviction_score =",
        "place_order(",
        "submit_order(",
        "execute_order(",
        "gs627_live_ignition_awareness",
    )
    assert not any(token in block for token in forbidden)
