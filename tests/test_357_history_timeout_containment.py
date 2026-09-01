import time

import pytest

from mide import webull_live
from mide.gs357_history_timeout_containment import (
    HISTORY_CALL_TIMEOUT_SECONDS,
    WebullHistoryTimeout,
    _HEALTH,
    _HEALTH_LOCK,
    bounded_history_call,
    runtime_health,
)
from mide.gs355_runtime_truth_banner import _banner_html


class _Client:
    def __init__(self):
        self.history_call_diagnostics = {"batch_calls": 0, "single_fallback_calls": 0}


def _reset_health():
    with _HEALTH_LOCK:
        _HEALTH.update(
            timeout_count=0,
            circuit_skip_count=0,
            last_timeout_at=None,
            last_timeout_symbols=[],
            last_timeout_reason="",
            circuit_open_until_monotonic=0.0,
        )


def test_history_wait_budget_is_short_enough_to_protect_streamlit():
    assert 5 <= HISTORY_CALL_TIMEOUT_SECONDS <= 12


def test_bounded_history_timeout_fails_scan_and_opens_circuit():
    _reset_health()
    client = _Client()

    with pytest.raises(WebullHistoryTimeout, match="exceeded"):
        bounded_history_call(
            lambda: time.sleep(0.2),
            client=client,
            symbols=["AAA", "BBB"],
            timeout_seconds=0.01,
        )

    health = runtime_health()
    assert health["state"] == "DEGRADED"
    assert health["timeout_count"] == 1
    assert health["last_timeout_symbols"] == ["AAA", "BBB"]
    assert client.history_call_diagnostics["timeouts"] == 1


def test_open_history_circuit_rejects_followup_without_submitting_more_work():
    _reset_health()
    client = _Client()

    with pytest.raises(WebullHistoryTimeout):
        bounded_history_call(
            lambda: time.sleep(0.2), client=client, symbols=["AAA"], timeout_seconds=0.01
        )

    called = []
    with pytest.raises(WebullHistoryTimeout, match="cooling down"):
        bounded_history_call(
            lambda: called.append(True), client=client, symbols=["CCC"], timeout_seconds=0.1
        )

    assert called == []
    assert runtime_health()["circuit_skip_count"] == 1
    assert client.history_call_diagnostics["circuit_skips"] == 1


def test_final_webull_history_adapter_is_contained_after_compatibility_install():
    assert getattr(
        webull_live.WebullOpenAPIClient.bars,
        "_gs357_history_timeout_containment",
        False,
    ) is True


def test_runtime_banner_exposes_history_timeout_health():
    html = _banner_html(
        {
            "state": "DEGRADED",
            "reason": "Webull history exceeded 10s scan budget",
            "scan_age_seconds": 30,
            "auto_scan": True,
            "webull_native_state": "READY",
            "webull_history_state": "DEGRADED",
            "webull_history_timeout_count": 2,
            "suppressed_reruns": 0,
        }
    )

    assert "Webull history DEGRADED/2 timeouts" in html
    assert "Webull history exceeded 10s scan budget" in html
