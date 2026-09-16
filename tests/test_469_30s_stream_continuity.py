from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock

from mide import gs379_webull_stream_data_truth as gs379
from mide import gs469_30s_stream_continuity as gs469
from mide import webull_live


class _Subscription:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _Provider:
    def __init__(self, *, subscription=True, last_tick_ms=None):
        self._enable_streaming = True
        self._subscription = _Subscription() if subscription else None
        self._subscribed = {"RETO", "QCLS"} if subscription else set()
        self._lock = Lock()
        self._gs379_30s_current = {}
        self._gs379_30s_closed = {}
        self.diagnostics = {
            "webull_stream": {
                "last_tick_timestamp_ms": last_tick_ms,
                "stream_connection_status": "connected" if subscription else "disconnected",
            }
        }


def _et_midday() -> datetime:
    # 16:00 UTC is 12:00 EDT on 2026-09-16.
    return datetime(2026, 9, 16, 16, 0, tzinfo=timezone.utc)


def _original_reconnector(calls):
    def original(provider, symbols):
        calls.append(list(symbols))
        if provider._subscription is None:
            provider._subscription = _Subscription()
            provider._subscribed = {str(symbol).upper() for symbol in symbols}
            provider.diagnostics["webull_stream"]["stream_connection_status"] = "connected"
        return True

    return original


def test_reasserts_retained_provider_when_gs379_registry_was_lost(monkeypatch):
    provider = _Provider(last_tick_ms=int(_et_midday().timestamp() * 1000))
    monkeypatch.setattr(gs379, "_ACTIVE_PROVIDER_REF", None)

    assert gs469.reassert_active_provider(provider) is True
    assert gs469._active_registry_provider() is provider
    assert provider.diagnostics["webull_stream"]["gs469_active_provider_rebinds"] == 1

    assert gs469.reassert_active_provider(provider) is False
    assert provider.diagnostics["webull_stream"]["gs469_active_provider_rebinds"] == 1


def test_fresh_tick_stream_is_not_restarted(monkeypatch):
    now = _et_midday()
    provider = _Provider(last_tick_ms=int((now - timedelta(seconds=45)).timestamp() * 1000))
    subscription = provider._subscription
    monkeypatch.setattr(gs379, "_ACTIVE_PROVIDER_REF", None)
    calls = []

    assert gs469.ensure_stream_continuity(
        _original_reconnector(calls), provider, ["RETO", "QCLS"], now=now
    ) is True

    assert provider._subscription is subscription
    assert subscription.closed is False
    assert calls == [["RETO", "QCLS"]]
    diag = provider.diagnostics["webull_stream"]["gs469_30s_stream_continuity"]
    assert diag["active_provider_reasserted"] is True
    assert diag["restart_performed"] is False
    assert diag["last_tick_age_seconds"] == 45.0


def test_stale_tick_stream_is_retired_and_resubscribed(monkeypatch):
    now = _et_midday()
    provider = _Provider(last_tick_ms=int((now - timedelta(minutes=8)).timestamp() * 1000))
    stale_subscription = provider._subscription
    monkeypatch.setattr(gs379, "_ACTIVE_PROVIDER_REF", None)
    calls = []

    result = gs469.ensure_stream_continuity(
        _original_reconnector(calls), provider, ["RETO", "QCLS"], now=now
    )

    assert result is True
    assert stale_subscription.closed is True
    assert provider._subscription is not stale_subscription
    assert provider._subscribed == {"RETO", "QCLS"}
    assert provider.diagnostics["webull_stream"]["gs469_stale_stream_restarts"] == 1
    diag = provider.diagnostics["webull_stream"]["gs469_30s_stream_continuity"]
    assert diag["restart_performed"] is True
    assert "heartbeat" in diag["restart_reason"]
    assert diag["synthetic_30s_bars"] is False
    assert diag["entry_authority_changed"] is False


def test_inherited_subscription_with_no_tick_heartbeat_repairs_immediately(monkeypatch):
    now = _et_midday()
    provider = _Provider(last_tick_ms=None)
    stale_subscription = provider._subscription
    monkeypatch.setattr(gs379, "_ACTIVE_PROVIDER_REF", None)

    gs469.ensure_stream_continuity(
        _original_reconnector([]), provider, ["RETO"], now=now
    )

    assert stale_subscription.closed is True
    assert provider._subscription is not stale_subscription
    assert provider.diagnostics["webull_stream"]["gs469_stale_stream_restarts"] == 1


def test_new_subscription_gets_grace_window_before_no_tick_restart(monkeypatch):
    now = _et_midday()
    provider = _Provider(subscription=False, last_tick_ms=None)
    monkeypatch.setattr(gs379, "_ACTIVE_PROVIDER_REF", None)
    calls = []
    original = _original_reconnector(calls)

    gs469.ensure_stream_continuity(original, provider, ["RETO"], now=now)
    first_subscription = provider._subscription
    assert first_subscription is not None
    assert first_subscription.closed is False

    gs469.ensure_stream_continuity(
        original, provider, ["RETO"], now=now + timedelta(seconds=60)
    )
    assert provider._subscription is first_subscription
    assert first_subscription.closed is False


def test_restart_is_rate_limited_even_if_tick_heartbeat_remains_stale(monkeypatch):
    now = _et_midday()
    provider = _Provider(last_tick_ms=int((now - timedelta(minutes=8)).timestamp() * 1000))
    monkeypatch.setattr(gs379, "_ACTIVE_PROVIDER_REF", None)
    original = _original_reconnector([])

    gs469.ensure_stream_continuity(original, provider, ["RETO"], now=now)
    first_replacement = provider._subscription

    gs469.ensure_stream_continuity(
        original, provider, ["RETO"], now=now + timedelta(seconds=60)
    )
    assert provider._subscription is first_replacement
    assert provider.diagnostics["webull_stream"]["gs469_stale_stream_restarts"] == 1


def test_no_forced_restart_outside_extended_trading_window(monkeypatch):
    # 01:00 EDT on the same Wednesday.
    now = datetime(2026, 9, 16, 5, 0, tzinfo=timezone.utc)
    provider = _Provider(last_tick_ms=int((now - timedelta(hours=2)).timestamp() * 1000))
    subscription = provider._subscription
    monkeypatch.setattr(gs379, "_ACTIVE_PROVIDER_REF", None)

    gs469.ensure_stream_continuity(
        _original_reconnector([]), provider, ["RETO"], now=now
    )

    assert provider._subscription is subscription
    assert subscription.closed is False
    assert provider.diagnostics["webull_stream"]["gs469_30s_stream_continuity"][
        "stream_expected_now"
    ] is False


def test_prior_eastern_day_30s_buffer_is_cleared_before_stale_restart(monkeypatch):
    now = _et_midday()
    yesterday = datetime(2026, 9, 15, 19, 30, tzinfo=timezone.utc)
    provider = _Provider(last_tick_ms=int(yesterday.timestamp() * 1000))
    old_ms = int(yesterday.timestamp() * 1000)
    provider._gs379_30s_current = {
        "RETO": {"t": old_ms, "o": 1.0, "h": 1.1, "l": 0.9, "c": 1.0, "v": 100}
    }
    provider._gs379_30s_closed = {"RETO": deque([dict(provider._gs379_30s_current["RETO"])])}
    monkeypatch.setattr(gs379, "_ACTIVE_PROVIDER_REF", None)

    gs469.ensure_stream_continuity(
        _original_reconnector([]), provider, ["RETO"], now=now
    )

    assert provider._gs379_30s_current == {}
    assert provider._gs379_30s_closed == {}
    diag = provider.diagnostics["webull_stream"]["gs469_30s_stream_continuity"]
    assert diag["prior_session_30s_cleared"] is True


def test_install_is_idempotent_and_owns_final_ensure_stream_boundary(monkeypatch):
    def base(self, symbols):
        return True

    monkeypatch.setattr(webull_live.LiveWebullProvider, "ensure_stream", base)
    gs469.install()
    once = webull_live.LiveWebullProvider.ensure_stream
    gs469.install()
    twice = webull_live.LiveWebullProvider.ensure_stream

    assert once is twice
    assert getattr(once, "_gs469_30s_stream_continuity", False) is True
    assert getattr(once, gs469._OWNER_ATTR, False) is True


def test_gs384_bootstraps_gs469_before_its_idempotence_return():
    source = Path("mide/gs384_diagnostic_signal_to_noise.py").read_text()
    assert "gs469_30s_stream_continuity" in source
    assert "install_gs469()" in source
    assert source.index("install_gs469()") < source.index(
        'if getattr(current_sources, "_gs384_signal_to_noise", False):'
    )


def test_scope_lock_no_synthetic_bars_or_trading_authority_changes():
    source = Path("mide/gs469_30s_stream_continuity.py").read_text()
    forbidden = (
        "client.bars(",
        "provider.bars(",
        "qualified_for_watch =",
        "qualified_for_entry =",
        "qualified_for_alert =",
        "candidate_status =",
        "participation_score =",
        "expansion_score =",
        "vwap_value =",
        "place_order(",
        "play_alert(",
    )
    assert not any(token in source for token in forbidden)
    assert "synthetic_30s_bars\": False" in source
