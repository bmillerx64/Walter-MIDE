from __future__ import annotations

import ast
from pathlib import Path


SOURCE = Path("app.py").read_text(encoding="utf-8")


def _function_source(name: str) -> str:
    tree = ast.parse(SOURCE)
    lines = SOURCE.splitlines()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(f"missing function {name}")


def test_gs635_recognizes_expired_token_check_path_narrowly():
    helper = _function_source("_is_webull_expired_token_failure")
    assert '"ERROR_CHECK_TOKEN"' in helper
    assert '"status:EXPIRED"' in helper
    assert '"token_manager.py"' in helper
    assert '"init_token"' in helper
    assert '"fetch_token_from_server"' in helper
    assert '"check_token"' in helper


def test_gs635_combines_existing_417_and_expired_token_paths():
    helper = _function_source("_is_webull_authorization_required_failure")
    assert "_is_webull_token_creation_failure(exc)" in helper
    assert "_is_webull_expired_token_failure(exc)" in helper


def test_gs635_auth_circuit_is_latched_not_time_elapsed():
    helper = _function_source("_webull_auth_backoff_active")
    assert "return bool(runtime_state.get(WEBULL_AUTH_REQUIRED_KEY))" in helper
    assert "datetime.now" not in helper
    assert "retry_at" not in helper


def test_gs635_stops_watchdog_retry_amplification_after_first_auth_failure():
    worker = _function_source("_run_process_autoscan")
    assert "WebullAuthorizationRequired" in worker
    assert "_scan_once_with_auth_guard" in worker
    assert "_before_process_retry" in worker
    assert 'last_failure.error_type == "WebullAuthorizationRequired"' in worker
    assert "before_retry=_before_process_retry" in worker


def test_gs635_process_autoscan_stays_latched_until_success():
    worker = _function_source("_run_process_autoscan")
    assert "_webull_auth_backoff_active(runtime_state)" in worker
    assert "automatic provider retries are paused until a controlled manual" in worker
    assert "_clear_webull_auth_backoff(runtime_state)" in worker
    assert "does not auto-unlatch" in worker


def test_gs635_operator_message_promises_no_automatic_retry():
    assert "No automatic provider retry will occur while this circuit is " in SOURCE
    assert "latched. A manual Run live scan remains available for one controlled retry. " in SOURCE
    assert "The first successful completed scan clears the circuit immediately." in SOURCE


def test_gs635_does_not_change_trading_liw_or_audio_authority():
    worker = _function_source("_run_process_autoscan")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "opportunity_score =",
        "conviction_score =",
        "place_order(",
        "submit_order(",
        "execute_order(",
        "gs627_live_ignition_awareness",
        "speak",
        "audio",
    )
    assert not any(token in worker for token in forbidden)
