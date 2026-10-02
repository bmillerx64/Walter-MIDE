from __future__ import annotations

from pathlib import Path

from mide import gs629_webull_stream_membership_guard as gs629


class _Subscription:
    def __init__(self):
        self.closed = 0

    def close(self):
        self.closed += 1


class Provider:
    def __init__(self):
        self._subscription = None
        self._subscribed = set()
        self.calls = []
        self.diagnostics = {
            "webull_stream": {
                "subscription_failures": [],
                "snapshot_unsupported_symbols": [],
            }
        }


def test_caps_membership_at_100_and_filters_snapshot_invalid_symbols():
    provider = Provider()
    provider.diagnostics["webull_stream"]["snapshot_unsupported_symbols"] = [
        "BAD1",
        "BAD2",
    ]

    def original(symbols):
        provider.calls.append(list(symbols))
        provider._subscribed = set(symbols)
        provider._subscription = object()
        return True

    symbols = ["BAD1"] + [f"S{i:03d}" for i in range(105)] + ["BAD2"]
    assert gs629.ensure_stream_with_membership_guard(
        original, provider, symbols
    ) is True

    assert len(provider.calls) == 1
    assert len(provider.calls[0]) == 100
    assert "BAD1" not in provider.calls[0]
    assert "BAD2" not in provider.calls[0]
    assert provider.calls[0] == [f"S{i:03d}" for i in range(100)]

    trace = provider.diagnostics["webull_stream"]["gs629_stream_membership"]
    assert trace["requested_symbol_count"] == 107
    assert trace["selected_symbol_count"] == 100
    assert trace["omitted_invalid_symbols"] == ["BAD1", "BAD2"]
    assert trace["omitted_due_cap_symbols"] == [f"S{i:03d}" for i in range(100, 105)]
    assert trace["trading_authority_changed"] is False
    assert trace["discovery_membership_changed"] is False
    assert trace["rest_snapshot_history_unchanged"] is True


def test_explicit_invalid_symbol_gets_one_bounded_retry_and_refills_to_cap():
    provider = Provider()

    def original(symbols):
        provider.calls.append(list(symbols))
        if len(provider.calls) == 1:
            provider.diagnostics["webull_stream"]["subscription_failures"].append(
                "ServerException: HTTP Status: 417, Code: INVALID_SYMBOL, "
                "Msg: The symbols does not exist in the category. [S005]."
            )
            return False
        provider._subscribed = set(symbols)
        provider._subscription = object()
        return True

    symbols = [f"S{i:03d}" for i in range(101)]
    assert gs629.ensure_stream_with_membership_guard(
        original, provider, symbols
    ) is True

    assert len(provider.calls) == 2
    assert len(provider.calls[0]) == 100
    assert len(provider.calls[1]) == 100
    assert "S005" not in provider.calls[1]
    assert "S100" in provider.calls[1]

    trace = provider.diagnostics["webull_stream"]["gs629_stream_membership"]
    assert trace["invalid_symbols"] == ["S005"]
    assert trace["invalid_retries_last_call"] == 1
    assert trace["invalid_retry_total"] == 1
    assert trace["last_result"] is True


def test_invalid_add_retires_failed_subscription_before_retry():
    provider = Provider()
    failed = _Subscription()
    provider._subscription = failed
    provider._subscribed = {"OLD"}

    def original(symbols):
        provider.calls.append(list(symbols))
        if len(provider.calls) == 1:
            provider.diagnostics["webull_stream"]["subscription_failures"].append(
                "ServerException: HTTP Status: 417, Code: INVALID_SYMBOL, "
                "Msg: The symbols does not exist in the category. [BAD]."
            )
            return False
        assert provider._subscription is None
        assert provider._subscribed == set()
        provider._subscribed = set(symbols)
        provider._subscription = object()
        return True

    assert gs629.ensure_stream_with_membership_guard(
        original, provider, ["GOOD", "BAD"]
    ) is True

    assert failed.closed == 1
    assert provider.calls == [["GOOD", "BAD"], ["GOOD"]]
    trace = provider.diagnostics["webull_stream"]["gs629_stream_membership"]
    assert trace["failed_subscription_retired"] is True
    assert trace["failed_subscription_retirements"] == 1


def test_non_invalid_delegate_failure_is_not_retried():
    provider = Provider()

    def original(symbols):
        provider.calls.append(list(symbols))
        provider.diagnostics["webull_stream"]["subscription_failures"].append(
            "RuntimeError: unrelated stream failure"
        )
        return False

    assert gs629.ensure_stream_with_membership_guard(
        original, provider, ["AAA", "BBB"]
    ) is False
    assert provider.calls == [["AAA", "BBB"]]


def test_install_for_provider_is_idempotent():
    provider = Provider()

    def original(_symbols):
        return True

    provider.ensure_stream = original
    assert gs629.install_for_provider(provider) is True
    installed = provider.ensure_stream
    assert gs629.install_for_provider(provider) is False
    assert provider.ensure_stream is installed
    assert getattr(installed, gs629._OWNER) == gs629.REVISION


def test_app_installs_gs629_after_window_guard_before_snapshot_retry():
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index('if provider_name.upper() == "WEBULL":')
    end = source.index('    else:\n        api_key = get_secret("ALPACA_API_KEY")', start)
    block = source[start:end]

    assert "mide.gs629_webull_stream_membership_guard" in block
    assert block.index("gs490.install_for_provider(client)") < block.index(
        "gs629.install_for_provider(client)"
    )
    assert block.index("gs629.install_for_provider(client)") < block.index(
        "gs494.install_for_provider(client)"
    )
    assert block.index("gs629.install_for_provider(client)") < block.index(
        "client.initialize_quotes(seeds"
    )


def test_scope_lock_changes_only_optional_stream_membership():
    source = Path("mide/gs629_webull_stream_membership_guard.py").read_text(
        encoding="utf-8"
    )
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
        "initialize_quotes(",
    )
    assert not any(token in source for token in forbidden)
    assert "MAX_STREAM_SYMBOLS = 100" in source
    assert '"trading_authority_changed": False' in source
    assert '"discovery_membership_changed": False' in source
    assert '"rest_snapshot_history_unchanged": True' in source
