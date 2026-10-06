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


def test_gs634_recognizes_only_token_creation_417_path():
    helper = _function_source("_is_webull_token_creation_failure")
    assert '"HTTP Status: 417"' in helper
    assert '"token_manager.py"' in helper
    assert '"create_token"' in helper
    assert '"init_token"' in helper


def test_gs634_process_worker_has_bounded_auth_backoff():
    worker = _function_source("_run_process_autoscan")
    assert "_webull_auth_backoff_active(runtime_state)" in worker
    assert "Webull auth backoff active" in worker
    assert "Webull authorization circuit opened" in worker
    assert "timedelta(seconds=WEBULL_AUTH_BLOCK_SECONDS)" in worker
    assert "_clear_webull_auth_backoff(runtime_state)" in worker


def test_gs634_keeps_manual_retry_available_and_clears_after_success():
    assert "Use Run live scan once to retire the expired SDK runtime and request one " in SOURCE
    assert "_clear_webull_auth_backoff(_gs585.process_state())" in SOURCE


def test_gs634_does_not_change_trading_or_liw_authority():
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
    )
    assert not any(token in worker for token in forbidden)
