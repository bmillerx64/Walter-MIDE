from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from mide import gs379_webull_stream_data_truth as gs379
from mide import gs637_webull_invalid_session_recovery as gs637


INVALID = (
    "RuntimeError: HTTP Status: 417, Code: INVALID_SESSION, "
    "Msg: Mqtt connection not exist for session: abc123"
)


class Client:
    def __init__(self, failures):
        self.failures = list(failures)
        self.calls = 0
        self.disconnects = 0
        self.transport = None

    def subscribe(self, symbols, category, sub_types):
        self.calls += 1
        assert symbols == ["ABC", "XYZ"]
        assert category == "US_STOCK"
        assert sub_types == ["TICK"]
        failure = self.failures.pop(0) if self.failures else None
        if failure is not None:
            raise RuntimeError(failure)
        self.transport._subscribed.set()

    def disconnect(self):
        self.disconnects += 1


class Provider:
    def __init__(self):
        self._subscription = None
        self._subscribed = set()
        self.diagnostics = {
            "webull_stream": {
                "stream_connection_status": "disconnected",
                "subscription_failures": [],
                "tick_messages_received": 0,
                "last_tick_timestamp_ms": None,
            }
        }


def _transport(client):
    value = gs379.OfficialWebullTickTransport(client, lambda _event: None)
    client.transport = value
    return value


def test_gs637_same_connected_transport_retries_invalid_session_once(monkeypatch):
    monkeypatch.setattr(gs637.time, "sleep", lambda _seconds: None)
    gs637._install_transport_patch()

    client = Client([INVALID, None])
    transport = _transport(client)

    transport.subscribe(["ABC", "XYZ"])

    assert client.calls == 2
    assert client.disconnects == 0
    assert transport._closed is False
    event = transport._gs637_recovery_event
    assert event["retry_attempted"] is True
    assert event["retry_result"] is True
    assert event["consumed"] is False


def test_gs637_provider_diagnostics_consume_successful_transport_recovery(monkeypatch):
    monkeypatch.setattr(gs637.time, "sleep", lambda _seconds: None)
    gs637._install_transport_patch()

    client = Client([INVALID, None])
    transport = _transport(client)
    provider = Provider()

    def base(symbols):
        transport.subscribe(symbols)
        provider._subscription = SimpleNamespace(transport=transport)
        provider._subscribed = set(symbols)
        provider.diagnostics["webull_stream"].update(
            stream_connection_status="connected",
            tick_messages_received=7,
            last_tick_timestamp_ms=123456789,
        )
        return True

    provider.ensure_stream = base
    assert gs637.install_for_provider(provider) is True

    assert provider.ensure_stream(["ABC", "XYZ", "ABC"]) is True

    trace = provider.diagnostics["webull_stream"][
        "gs637_invalid_session_recovery"
    ]
    assert client.calls == 2
    assert trace["same_transport_retry_attempts"] == 1
    assert trace["same_transport_retry_successes"] == 1
    assert trace["terminal_invalid_session_failures"] == 0
    assert trace["last_retry_result"] is True
    assert trace["tick_messages_received"] == 7
    assert trace["last_tick_timestamp_ms"] == 123456789
    assert trace["same_mqtt_transport_retry"] is True
    assert trace["process_provider_reused"] is True
    assert trace["second_provider_created"] is False
    assert trace["second_scheduler_created"] is False
    assert trace["gs469_remains_reconnect_owner"] is True


def test_gs637_second_invalid_session_failure_closes_and_yields(monkeypatch):
    monkeypatch.setattr(gs637.time, "sleep", lambda _seconds: None)
    gs637._install_transport_patch()

    client = Client([INVALID, INVALID])
    transport = _transport(client)
    provider = Provider()

    def base(symbols):
        try:
            transport.subscribe(symbols)
        except Exception as exc:
            provider.diagnostics["webull_stream"]["subscription_failures"].append(
                f"{type(exc).__name__}: {exc}"
            )
            provider.diagnostics["webull_stream"][
                "stream_connection_status"
            ] = "error"
            return False
        raise AssertionError("second INVALID_SESSION must not report success")

    provider.ensure_stream = base
    gs637.install_for_provider(provider)

    assert provider.ensure_stream(["ABC", "XYZ"]) is False
    assert client.calls == 2
    assert client.disconnects == 1
    assert transport._closed is True
    trace = provider.diagnostics["webull_stream"][
        "gs637_invalid_session_recovery"
    ]
    assert trace["same_transport_retry_attempts"] == 1
    assert trace["same_transport_retry_successes"] == 0
    assert trace["terminal_invalid_session_failures"] == 1
    assert trace["last_retry_result"] is False


def test_gs637_unrelated_stream_failure_is_not_retried(monkeypatch):
    monkeypatch.setattr(gs637.time, "sleep", lambda _seconds: None)
    gs637._install_transport_patch()

    client = Client(["socket closed"])
    transport = _transport(client)

    try:
        transport.subscribe(["ABC", "XYZ"])
    except RuntimeError as exc:
        assert "socket closed" in str(exc)
    else:
        raise AssertionError("unrelated failure should propagate")

    assert client.calls == 1
    assert client.disconnects == 1
    assert transport._closed is True


def test_gs637_requires_both_invalid_session_and_mqtt_session_signature():
    assert gs637._invalid_session_failure(INVALID) is True
    assert gs637._invalid_session_failure(
        "HTTP 417 INVALID_SESSION unrelated provider error"
    ) is False
    assert gs637._invalid_session_failure(
        "Mqtt connection not exist for session but no code"
    ) is False


def test_gs637_install_is_idempotent_on_exact_retained_provider():
    provider = Provider()

    def base(_symbols):
        return True

    provider.ensure_stream = base
    gs637._install_transport_patch()
    assert gs637.install_for_provider(provider) is True
    installed = provider.ensure_stream
    assert gs637.install_for_provider(provider) is False
    assert provider.ensure_stream is installed


def test_gs637_app_wraps_final_stream_guards_before_quote_initialization():
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index('if provider_name.upper() == "WEBULL":')
    end = source.index(
        '    else:\n        api_key = get_secret("ALPACA_API_KEY")',
        start,
    )
    block = source[start:end]
    assert "mide.gs629_webull_stream_membership_guard" in block
    assert "mide.gs637_webull_invalid_session_recovery" in block
    assert block.index("gs629.install_for_provider(client)") < block.index(
        "gs637.install_for_provider(client)"
    )
    assert source.index("gs637.install_for_provider(client)", start) < source.index(
        "client.initialize_quotes(seeds", start
    )


def test_gs637_scope_lock_preserves_authority_boundaries():
    source = Path(
        "mide/gs637_webull_invalid_session_recovery.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "candidate_status =",
        "participation_score =",
        "expansion_score =",
        "opportunity_score =",
        "conviction_score =",
        "place_order(",
        "submit_order(",
        "execute_order(",
        "request_scan(",
    )
    assert not any(token in source for token in forbidden)
    assert '"one_retry_only": True' in source
    assert '"same_mqtt_transport_retry": True' in source
    assert '"process_provider_reused": True' in source
    assert '"second_provider_created": False' in source
    assert '"second_scheduler_created": False' in source
    assert '"gs469_remains_reconnect_owner": True' in source
    assert '"rest_snapshot_history_unchanged": True' in source
    assert '"trading_authority_changed": False' in source
