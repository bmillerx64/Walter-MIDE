from __future__ import annotations

from types import SimpleNamespace

from mide import gs379_webull_stream_data_truth as gs379
from mide import gs389_webull_mode_exit_lifecycle as gs389
from mide import session_controls
from mide.completed_scan import SCAN_CONTEXT_KEY


class _Subscription:
    def __init__(self, *, fail=False):
        self.closed = 0
        self.fail = fail

    def close(self):
        self.closed += 1
        if self.fail:
            raise RuntimeError("close failed")


class _Provider:
    def __init__(self, subscription):
        self._subscription = subscription
        self._subscribed = {"AAA", "BBB"}
        self.diagnostics = {
            "webull_stream": {
                "stream_connection_status": "connected",
                "subscribed_symbols": 2,
            }
        }


def _state(mode, provider):
    return {
        session_controls.DATA_MODE_KEY: mode,
        SCAN_CONTEXT_KEY: SimpleNamespace(provider_instance=provider),
    }


def test_explicit_demo_mode_closes_retained_webull_stream_and_clears_subscription_state():
    subscription = _Subscription()
    provider = _Provider(subscription)
    state = _state("Demo", provider)

    assert gs389.retire_session_stream_on_mode_exit(state) is True

    stream = provider.diagnostics["webull_stream"]
    assert subscription.closed == 1
    assert provider._subscription is None
    assert provider._subscribed == set()
    assert stream["subscribed_symbols"] == 0
    assert stream["stream_connection_status"] == "bypassed"
    assert stream["stream_bypass_reason"] == "Live Webull mode is not selected"
    assert stream["stream_mode_exit_count"] == 1


def test_live_webull_selection_never_closes_persistent_stream():
    subscription = _Subscription()
    provider = _Provider(subscription)
    state = _state("Live Webull", provider)

    assert gs389.retire_session_stream_on_mode_exit(state) is False
    assert subscription.closed == 0
    assert provider._subscription is subscription
    assert provider._subscribed == {"AAA", "BBB"}


def test_mode_exit_cleanup_failure_detaches_failed_transport_and_records_failure():
    subscription = _Subscription(fail=True)
    provider = _Provider(subscription)
    state = _state("Demo", provider)

    assert gs389.retire_session_stream_on_mode_exit(state) is False

    stream = provider.diagnostics["webull_stream"]
    assert provider._subscription is None
    assert provider._subscribed == set()
    assert stream["stream_cleanup_failures"] == 1
    assert stream["stream_mode_exit_error"] == "RuntimeError"
    assert stream["stream_connection_status"] == "bypassed"


def test_gs380_replacement_registry_retires_prior_stream_before_new_provider_is_authoritative():
    gs379._reset_active_provider_registry()
    first_subscription = _Subscription()
    second_subscription = _Subscription()
    first = _Provider(first_subscription)
    second = _Provider(second_subscription)

    gs379._register_active_provider(first)
    gs379._register_active_provider(second)

    assert first_subscription.closed == 1
    assert first._subscription is None
    assert first._subscribed == set()
    assert first.diagnostics["webull_stream"]["stream_connection_status"] == "replaced"
    assert second_subscription.closed == 0
    assert second._subscription is second_subscription
    gs379._reset_active_provider_registry()


def test_select_data_mode_wrapper_is_installed():
    assert getattr(
        session_controls.select_data_mode,
        "_gs389_webull_mode_exit_lifecycle",
        False,
    ) is True
