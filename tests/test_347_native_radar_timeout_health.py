import time

import pytest

from mide.gs347_native_radar_timeout_health import (
    guarded_fetch,
    reset_runtime_health,
    runtime_health,
)


class Client:
    def __init__(self):
        self.diagnostics = {}


def test_hung_native_radar_returns_control_within_bound_and_opens_circuit():
    reset_runtime_health()
    client = Client()

    def hung(_client):
        time.sleep(0.15)
        return {"symbols": []}

    started = time.monotonic()
    with pytest.raises(TimeoutError, match="native radar timed out"):
        guarded_fetch(hung, client, timeout_seconds=0.02, cooldown_seconds=1.0)
    elapsed = time.monotonic() - started

    assert elapsed < 0.10
    health = client.diagnostics["webull_native_health"]
    assert health["state"] == "DEGRADED"
    assert health["timeout_count"] == 1
    assert health["cooldown_seconds_remaining"] > 0
    assert "timed out" in health["error"]


def test_open_circuit_fails_fast_without_starting_more_vendor_work():
    reset_runtime_health()
    client = Client()
    calls = []

    def hung(_client):
        calls.append("called")
        time.sleep(0.15)
        return {}

    with pytest.raises(TimeoutError):
        guarded_fetch(hung, client, timeout_seconds=0.01, cooldown_seconds=1.0)

    started = time.monotonic()
    with pytest.raises(RuntimeError, match="temporarily disabled"):
        guarded_fetch(hung, client, timeout_seconds=0.01, cooldown_seconds=1.0)
    assert time.monotonic() - started < 0.05
    assert calls == ["called"]


def test_success_records_last_success_and_returns_report_health():
    reset_runtime_health()
    client = Client()

    report = guarded_fetch(
        lambda _client: {"symbols": [{"symbol": "TEST"}]},
        client,
        timeout_seconds=0.05,
        cooldown_seconds=0.1,
    )

    assert report["symbols"][0]["symbol"] == "TEST"
    assert report["runtime_health"]["state"] == "READY"
    assert report["runtime_health"]["last_success_utc"]
    assert client.diagnostics["webull_native_health"]["error"] == ""


def test_non_timeout_vendor_error_is_exposed_as_degraded_without_false_timeout():
    reset_runtime_health()
    client = Client()

    def fail(_client):
        raise PermissionError("403 denied")

    with pytest.raises(PermissionError, match="403 denied"):
        guarded_fetch(fail, client, timeout_seconds=0.05)

    health = client.diagnostics["webull_native_health"]
    assert health["state"] == "DEGRADED"
    assert health["timeout_count"] == 0
    assert "PermissionError" in health["error"]
    assert runtime_health()["cooldown_seconds_remaining"] == 0
