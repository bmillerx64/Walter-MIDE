from __future__ import annotations

from pathlib import Path

from mide import gs637_webull_invalid_session_recovery as gs637


INVALID = (
    "RuntimeError: HTTP Status: 417, Code: INVALID_SESSION, "
    "Msg: Mqtt connection not exist for session: abc123"
)


class Provider:
    def __init__(self):
        self._subscription = None
        self._subscribed = set()
        self.calls = 0
        self.diagnostics = {
            "webull_stream": {
                "stream_connection_status": "error",
                "subscription_failures": [],
                "tick_messages_received": 0,
                "last_tick_timestamp_ms": None,
            }
        }


def test_gs637_exact_invalid_session_gets_one_same_provider_retry(monkeypatch):
    provider = Provider()
    retired = []

    def retire(value):
        assert value is provider
        retired.append(value)
        value._subscription = None
        value._subscribed.clear()

    from mide import gs379_webull_stream_data_truth as gs379
    monkeypatch.setattr(gs379, "_retire_provider_stream", retire)

    def original(symbols):
        provider.calls += 1
        assert symbols == ["ABC", "XYZ"]
        if provider.calls == 1:
            provider.diagnostics["webull_stream"]["subscription_failures"].append(
                INVALID
            )
            return False
        provider._subscription = object()
        provider._subscribed = set(symbols)
        provider.diagnostics["webull_stream"].update(
            stream_connection_status="connected",
            tick_messages_received=7,
            last_tick_timestamp_ms=123456789,
        )
        return True

    result = gs637.ensure_stream_with_invalid_session_recovery(
        original,
        provider,
        ["ABC", "XYZ", "ABC"],
    )

    assert result is True
    assert provider.calls == 2
    assert retired == [provider]
    trace = provider.diagnostics["webull_stream"][
        "gs637_invalid_session_recovery"
    ]
    assert trace["detected_total"] == 1
    assert trace["recovery_attempts"] == 1
    assert trace["recovery_successes"] == 1
    assert trace["recovery_failures"] == 0
    assert trace["last_retry_result"] is True
    assert trace["tick_messages_received"] == 7
    assert trace["last_tick_timestamp_ms"] == 123456789
    assert trace["process_provider_reused"] is True
    assert trace["second_provider_created"] is False
    assert trace["second_scheduler_created"] is False


def test_gs637_second_invalid_session_failure_stops_after_one_retry(monkeypatch):
    provider = Provider()
    from mide import gs379_webull_stream_data_truth as gs379
    monkeypatch.setattr(gs379, "_retire_provider_stream", lambda _provider: None)

    def original(_symbols):
        provider.calls += 1
        provider.diagnostics["webull_stream"]["subscription_failures"].append(
            INVALID
        )
        return False

    assert gs637.ensure_stream_with_invalid_session_recovery(
        original, provider, ["ABC"]
    ) is False
    assert provider.calls == 2
    trace = provider.diagnostics["webull_stream"][
        "gs637_invalid_session_recovery"
    ]
    assert trace["recovery_attempts"] == 1
    assert trace["recovery_successes"] == 0
    assert trace["recovery_failures"] == 1
    assert "INVALID_SESSION" in trace["last_retry_failure"]


def test_gs637_unrelated_stream_failure_keeps_existing_lifecycle():
    provider = Provider()

    def original(_symbols):
        provider.calls += 1
        provider.diagnostics["webull_stream"]["subscription_failures"].append(
            "RuntimeError: socket closed"
        )
        return False

    assert gs637.ensure_stream_with_invalid_session_recovery(
        original, provider, ["ABC"]
    ) is False
    assert provider.calls == 1
    trace = provider.diagnostics["webull_stream"][
        "gs637_invalid_session_recovery"
    ]
    assert trace["detected_total"] == 0
    assert trace["recovery_attempts"] == 0


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
    assert '"process_provider_reused": True' in source
    assert '"second_provider_created": False' in source
    assert '"second_scheduler_created": False' in source
    assert '"rest_snapshot_history_unchanged": True' in source
    assert '"trading_authority_changed": False' in source
