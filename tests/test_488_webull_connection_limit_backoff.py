from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from mide import gs488_webull_connection_limit_backoff as gs488


class Provider:
    def __init__(self):
        self._subscription = None
        self._subscribed = set()
        self.calls = 0
        self.diagnostics = {
            "webull_stream": {
                "stream_connection_status": "disconnected",
                "subscription_failures": [],
            }
        }


def _limit_failure(provider):
    def original(_symbols):
        provider.calls += 1
        provider.diagnostics["webull_stream"]["stream_connection_status"] = "error"
        provider.diagnostics["webull_stream"]["subscription_failures"].append(
            "RuntimeError: Webull OpenAPI stream failed: rc code: 105, "
            "msg: Connection limit exceeded"
        )
        return False

    return original


def test_rc105_graduates_five_ten_fifteen_minute_backoff_and_suppresses_per_scan_retries():
    provider = Provider()
    original = _limit_failure(provider)

    assert gs488.ensure_stream_with_backoff(
        original, provider, ["PAAI"], now=1000.0
    ) is False
    assert provider.calls == 1
    first = gs488.backoff_snapshot(provider, now=1000.0)
    assert first["active"] is True
    assert first["cooldown_seconds"] == 300.0
    assert first["seconds_remaining"] == 300.0
    assert first["consecutive_limit_failures"] == 1
    assert first["last_limit_failure"] == "WEBULL_RC105_CONNECTION_LIMIT"

    assert gs488.ensure_stream_with_backoff(
        original, provider, ["PAAI"], now=1061.0
    ) is False
    assert provider.calls == 1
    suppressed = gs488.backoff_snapshot(provider, now=1061.0)
    assert suppressed["active"] is True
    assert suppressed["suppressed_attempts"] == 1

    assert gs488.ensure_stream_with_backoff(
        original, provider, ["PAAI"], now=1301.0
    ) is False
    assert provider.calls == 2
    retried = gs488.backoff_snapshot(provider, now=1301.0)
    assert retried["consecutive_limit_failures"] == 2
    assert retried["cooldown_seconds"] == 600.0
    assert retried["seconds_remaining"] == 600.0

    assert gs488.ensure_stream_with_backoff(
        original, provider, ["PAAI"], now=1601.0
    ) is False
    assert provider.calls == 2

    assert gs488.ensure_stream_with_backoff(
        original, provider, ["PAAI"], now=1902.0
    ) is False
    assert provider.calls == 3
    third = gs488.backoff_snapshot(provider, now=1902.0)
    assert third["consecutive_limit_failures"] == 3
    assert third["cooldown_seconds"] == 900.0
    assert third["seconds_remaining"] == 900.0

    assert gs488.ensure_stream_with_backoff(
        original, provider, ["PAAI"], now=2803.0
    ) is False
    fourth = gs488.backoff_snapshot(provider, now=2803.0)
    assert fourth["consecutive_limit_failures"] == 4
    assert fourth["cooldown_seconds"] == 900.0



def test_retained_flat_backoff_is_extended_in_place_without_early_retry():
    provider = Provider()
    state = gs488._state(provider)
    state.update(
        active=True,
        cooldown_seconds=300.0,
        next_retry_epoch=1300.0,
        consecutive_limit_failures=5,
        last_limit_failure_epoch=1000.0,
        last_limit_failure="WEBULL_RC105_CONNECTION_LIMIT",
    )

    snap = gs488.backoff_snapshot(provider, now=1100.0)
    assert snap["active"] is True
    assert snap["cooldown_seconds"] == 900.0
    assert snap["next_retry_epoch"] == 1900.0
    assert snap["seconds_remaining"] == 800.0
    assert snap["gs489_retained_deadline_extended"] is True


def test_retained_gs488_instance_wrapper_is_upgraded_in_place_not_nested():
    provider = Provider()
    state = gs488._state(provider)
    state.update(
        active=True,
        cooldown_seconds=300.0,
        next_retry_epoch=1300.0,
        consecutive_limit_failures=5,
        last_limit_failure_epoch=1000.0,
    )
    calls = {"original": 0}

    def original(_symbols):
        calls["original"] += 1
        return False

    namespace = {
        "ensure_stream_with_backoff": lambda original_fn, active_provider, symbols, now=None: original_fn(symbols),
        "original": original,
        "provider": provider,
    }
    exec(
        "def retained(symbols):\n"
        "    return ensure_stream_with_backoff(original, provider, symbols, now=1100.0)\n",
        namespace,
    )
    retained = namespace["retained"]
    setattr(retained, gs488._OWNER, True)
    setattr(retained, gs488._PROVIDER_OWNER, True)
    provider.ensure_stream = retained

    assert gs488.install_for_provider(provider) is True
    assert provider.ensure_stream is retained
    assert getattr(retained, gs488._OWNER) == gs488.REVISION
    assert provider.ensure_stream(["PAAI"]) is False
    assert calls["original"] == 0
    assert gs488.backoff_snapshot(provider, now=1100.0)["cooldown_seconds"] == 900.0


def test_unrelated_stream_failure_keeps_existing_retry_behavior():
    provider = Provider()

    def original(_symbols):
        provider.calls += 1
        provider.diagnostics["webull_stream"]["subscription_failures"].append(
            "RuntimeError: socket closed"
        )
        return False

    assert gs488.ensure_stream_with_backoff(original, provider, ["ABC"], now=10.0) is False
    assert gs488.ensure_stream_with_backoff(original, provider, ["ABC"], now=70.0) is False
    assert provider.calls == 2
    state = gs488.backoff_snapshot(provider, now=70.0)
    assert state["active"] is False
    assert state["consecutive_limit_failures"] == 0


def test_healthy_subscription_is_never_suppressed_and_clears_limit_state():
    provider = Provider()
    state = gs488._state(provider)
    state.update(
        active=True,
        next_retry_epoch=2000.0,
        consecutive_limit_failures=2,
    )
    provider._subscription = object()

    def original(_symbols):
        provider.calls += 1
        return True

    assert gs488.ensure_stream_with_backoff(original, provider, ["ABC"], now=1000.0) is True
    assert provider.calls == 1
    current = gs488.backoff_snapshot(provider, now=1000.0)
    assert current["active"] is False
    assert current["next_retry_epoch"] is None
    assert current["consecutive_limit_failures"] == 0


def test_exact_retained_provider_instance_can_be_patched_idempotently():
    provider = Provider()

    def legacy_ensure(symbols):
        return _limit_failure(provider)(symbols)

    provider.ensure_stream = legacy_ensure
    assert gs488.install_for_provider(provider) is True
    installed = provider.ensure_stream
    assert gs488.install_for_provider(provider) is False
    assert provider.ensure_stream is installed

    assert provider.ensure_stream(["PAAI"]) is False
    before = provider.calls
    assert provider.ensure_stream(["PAAI"]) is False
    assert provider.calls == before


def test_stream_trace_reports_connection_limit_backoff(monkeypatch):
    from mide import gs481_live_evidence_hard_bind as gs481

    provider = Provider()
    gs488.ensure_stream_with_backoff(_limit_failure(provider), provider, ["PAAI"], now=100.0)

    original = gs481._stream_failure_truth
    try:
        gs488._install_stream_trace()
        truth = gs481._stream_failure_truth(provider)
        assert truth["gs488_connection_limit_containment"] is True
        backoff = truth["connection_limit_backoff"]
        assert backoff["authority"] == gs488.AUTHORITY
        assert backoff["last_limit_failure"] == "WEBULL_RC105_CONNECTION_LIMIT"
        assert backoff["trading_authority_changed"] is False
    finally:
        # Keep this test isolated from later tests in the same interpreter.
        current = gs481._stream_failure_truth
        gs481._stream_failure_truth = getattr(current, "_gs488_original", original)


def test_gs384_installs_gs488_after_activation_and_before_operator_audio():
    source = Path("mide/gs384_diagnostic_signal_to_noise.py").read_text(encoding="utf-8")
    assert "gs488_webull_connection_limit_backoff" in source
    assert source.index("install_gs470()") < source.index("install_gs488()")
    assert source.index("install_gs488()") < source.index("install_gs473()")


def test_scope_lock_only_changes_stream_retry_lifecycle():
    source = Path("mide/gs488_webull_connection_limit_backoff.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "opportunity_score =",
        "conviction_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "place_order(",
        "submit_order(",
        "execute_order(",
    )
    assert not any(token in source for token in forbidden)
    assert "COOLDOWN_SECONDS = 300.0" in source
    assert "BACKOFF_SECONDS = (300.0, 600.0, 900.0)" in source
    assert "REVISION = 2" in source
    assert "rest_snapshot_history_unchanged" in source
    assert '"trading_authority_changed": False' in source
