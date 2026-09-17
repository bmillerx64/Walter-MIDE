from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from mide import gs490_webull_stream_window_guard as gs490


class Provider:
    def __init__(self):
        self._subscription = None
        self.calls = 0
        self.diagnostics = {
            "webull_stream": {
                "stream_connection_status": "error",
                "stream_bypass_reason": None,
            }
        }


def test_stream_window_is_weekday_0400_through_195959_eastern():
    # September is EDT (UTC-4).
    assert gs490.stream_window_open(
        datetime(2026, 9, 21, 7, 59, 59, tzinfo=timezone.utc)
    ) is False
    assert gs490.stream_window_open(
        datetime(2026, 9, 21, 8, 0, 0, tzinfo=timezone.utc)
    ) is True
    assert gs490.stream_window_open(
        datetime(2026, 9, 21, 23, 59, 59, tzinfo=timezone.utc)
    ) is True
    assert gs490.stream_window_open(
        datetime(2026, 9, 22, 0, 0, 0, tzinfo=timezone.utc)
    ) is False

    # Saturday 10:00 ET is outside even though the clock is between 04:00 and 20:00.
    assert gs490.stream_window_open(
        datetime(2026, 9, 19, 14, 0, 0, tzinfo=timezone.utc)
    ) is False


def test_no_subscription_after_2000_et_is_bypassed_without_calling_original():
    provider = Provider()

    def original(_symbols):
        provider.calls += 1
        raise AssertionError("new stream must not open outside GS490 window")

    result = gs490.ensure_stream_in_window(
        original,
        provider,
        ["PAAI"],
        now=datetime(2026, 9, 22, 0, 5, tzinfo=timezone.utc),
    )
    assert result is False
    assert provider.calls == 0
    stream = provider.diagnostics["webull_stream"]
    assert stream["stream_connection_status"] == "bypassed"
    assert stream["stream_bypass_reason"] == gs490.BYPASS_REASON
    guard = stream["gs490_stream_window_guard"]
    assert guard["window_open"] is False
    assert guard["blocked_last_check"] is True
    assert guard["blocked_new_connection_attempts"] == 1
    assert guard["rest_snapshot_history_unchanged"] is True
    assert guard["trading_authority_changed"] is False


def test_0400_et_clears_own_bypass_and_delegates_normal_stream_path():
    provider = Provider()
    provider.diagnostics["webull_stream"]["stream_connection_status"] = "bypassed"
    provider.diagnostics["webull_stream"]["stream_bypass_reason"] = gs490.BYPASS_REASON

    def original(_symbols):
        provider.calls += 1
        return True

    result = gs490.ensure_stream_in_window(
        original,
        provider,
        ["PAAI"],
        now=datetime(2026, 9, 21, 8, 0, tzinfo=timezone.utc),
    )
    assert result is True
    assert provider.calls == 1
    stream = provider.diagnostics["webull_stream"]
    assert stream["stream_bypass_reason"] is None
    assert stream["stream_connection_status"] == "disconnected"
    assert stream["gs490_stream_window_guard"]["window_open"] is True


def test_existing_subscription_is_not_retired_or_blocked_after_2000_et():
    provider = Provider()
    subscription = object()
    provider._subscription = subscription

    def original(_symbols):
        provider.calls += 1
        assert provider._subscription is subscription
        return True

    assert gs490.ensure_stream_in_window(
        original,
        provider,
        ["PAAI"],
        now=datetime(2026, 9, 22, 0, 5, tzinfo=timezone.utc),
    ) is True
    assert provider.calls == 1
    assert provider._subscription is subscription


def test_exact_retained_provider_install_is_idempotent():
    provider = Provider()

    def legacy_ensure(_symbols):
        provider.calls += 1
        return False

    provider.ensure_stream = legacy_ensure
    assert gs490.install_for_provider(provider) is True
    installed = provider.ensure_stream
    assert gs490.install_for_provider(provider) is False
    assert provider.ensure_stream is installed
    assert getattr(installed, gs490._OWNER) == gs490.REVISION


def test_app_installs_gs490_outside_gs489_before_initialize_quotes():
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index('if provider_name.upper() == "WEBULL":')
    end = source.index('    else:\n        api_key = get_secret("ALPACA_API_KEY")', start)
    block = source[start:end]
    assert "mide.gs489_webull_graduated_backoff" in block
    assert "mide.gs490_webull_stream_window_guard" in block
    assert block.index("gs489.install_for_provider(client)") < block.index(
        "gs490.install_for_provider(client)"
    )
    assert source.index("gs490.install_for_provider(client)", start) < source.index(
        "client.initialize_quotes(seeds", start
    )


def test_scope_lock_only_changes_stream_initiation_lifecycle():
    source = Path("mide/gs490_webull_stream_window_guard.py").read_text(encoding="utf-8")
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
    assert 'STREAM_START_ET = time(4, 0)' in source
    assert 'STREAM_END_ET = time(20, 0)' in source
    assert "rest_snapshot_history_unchanged" in source
    assert '"trading_authority_changed": False' in source
