from __future__ import annotations

from pathlib import Path

from mide import gs489_webull_graduated_backoff as gs489


class Provider:
    def __init__(self):
        self._subscription = None
        self.calls = 0
        self.diagnostics = {
            "webull_stream": {
                "stream_connection_status": "error",
                "subscription_failures": [],
            }
        }


def _limit_failure(provider):
    def original(_symbols):
        provider.calls += 1
        provider.diagnostics["webull_stream"]["subscription_failures"].append(
            "RuntimeError: Webull OpenAPI stream failed: rc code: 105, "
            "msg: Connection limit exceeded"
        )
        return False
    return original


def test_graduated_rc105_schedule_is_five_ten_then_fifteen_minutes():
    provider = Provider()
    original = _limit_failure(provider)

    assert gs489.ensure_stream_with_graduated_backoff(
        original, provider, ["PAAI"], now=1000.0
    ) is False
    state = gs489._state(provider)
    assert state["cooldown_seconds"] == 300.0
    assert state["next_retry_epoch"] == 1300.0
    assert state["consecutive_limit_failures"] == 1

    assert gs489.ensure_stream_with_graduated_backoff(
        original, provider, ["PAAI"], now=1301.0
    ) is False
    assert state["cooldown_seconds"] == 600.0
    assert state["next_retry_epoch"] == 1901.0
    assert state["consecutive_limit_failures"] == 2

    assert gs489.ensure_stream_with_graduated_backoff(
        original, provider, ["PAAI"], now=1902.0
    ) is False
    assert state["cooldown_seconds"] == 900.0
    assert state["next_retry_epoch"] == 2802.0
    assert state["consecutive_limit_failures"] == 3

    assert gs489.ensure_stream_with_graduated_backoff(
        original, provider, ["PAAI"], now=2803.0
    ) is False
    assert state["cooldown_seconds"] == 900.0
    assert state["consecutive_limit_failures"] == 4


def test_retained_flat_gs488_state_is_extended_without_early_retry():
    provider = Provider()
    state = gs489._state(provider)
    state.update(
        active=True,
        cooldown_seconds=300.0,
        next_retry_epoch=1300.0,
        consecutive_limit_failures=5,
        last_limit_failure_epoch=1000.0,
        last_limit_failure="WEBULL_RC105_CONNECTION_LIMIT",
    )
    calls = {"count": 0}

    def original(_symbols):
        calls["count"] += 1
        return False

    assert gs489.ensure_stream_with_graduated_backoff(
        original, provider, ["PAAI"], now=1100.0
    ) is False
    assert calls["count"] == 0
    assert state["cooldown_seconds"] == 900.0
    assert state["next_retry_epoch"] == 1900.0
    assert state["gs489_retained_deadline_extended"] is True


def test_exact_old_gs488_wrapper_is_upgraded_in_place_not_nested(monkeypatch):
    monkeypatch.setattr(gs489.time, "time", lambda: 1100.0)
    provider = Provider()
    state = gs489._state(provider)
    state.update(
        active=True,
        cooldown_seconds=300.0,
        next_retry_epoch=1300.0,
        consecutive_limit_failures=5,
        last_limit_failure_epoch=1000.0,
    )
    called = {"original": 0}

    def original(_symbols):
        called["original"] += 1
        return False

    namespace = {
        "ensure_stream_with_backoff": lambda fn, active_provider, symbols: fn(symbols),
        "original": original,
        "provider": provider,
    }
    exec(
        "def retained(symbols):\n"
        "    return ensure_stream_with_backoff(original, provider, symbols)\n",
        namespace,
    )
    retained = namespace["retained"]
    setattr(retained, gs489._GS488_OWNER, True)
    provider.ensure_stream = retained

    assert gs489.install_for_provider(provider) is True
    assert provider.ensure_stream is retained
    assert getattr(retained, gs489._GS489_OWNER) == gs489.REVISION
    assert provider.ensure_stream(["PAAI"]) is False
    assert called["original"] == 0
    assert state["cooldown_seconds"] == 900.0


def test_successful_subscription_resets_consecutive_limit_failures():
    provider = Provider()
    state = gs489._state(provider)
    state.update(
        active=True,
        cooldown_seconds=900.0,
        next_retry_epoch=1000.0,
        consecutive_limit_failures=5,
    )
    provider._subscription = object()

    assert gs489.ensure_stream_with_graduated_backoff(
        lambda _symbols: True, provider, ["PAAI"], now=1100.0
    ) is True
    assert state["active"] is False
    assert state["consecutive_limit_failures"] == 0
    assert state["cooldown_seconds"] == 300.0
    assert state["next_retry_epoch"] is None


def test_app_binds_unique_gs489_module_before_webull_initialize_quotes():
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index('if provider_name.upper() == "WEBULL":')
    end = source.index('    else:\n        api_key = get_secret("ALPACA_API_KEY")', start)
    webull_block = source[start:end]
    assert "mide.gs489_webull_graduated_backoff" in webull_block
    assert "gs489.install_for_provider(client)" in webull_block
    assert source.index("gs489.install_for_provider(client)", start) < source.index(
        "client.initialize_quotes(seeds", start
    )


def test_scope_lock_changes_only_connection_limit_retry_lifecycle():
    source = Path("mide/gs489_webull_graduated_backoff.py").read_text(encoding="utf-8")
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
    assert "BACKOFF_SECONDS = (300.0, 600.0, 900.0)" in source
    assert "rest_snapshot_history_unchanged" in source
    assert '"trading_authority_changed": False' in source
