"""GS546: Walter alone owns Webull TICK reconnects."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs546_webull_stream_retry_owner as gs546
from mide.authorities import market_evidence


ROOT = Path(__file__).resolve().parents[1]


class StreamingModule:
    class DataStreamingClient:
        calls = []

        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            type(self).calls.append((args, kwargs))


class RetryModule:
    NO_RETRY_POLICY = object()


class DataClient:
    def __init__(self):
        api_client = object()

        def legacy_factory():
            return api_client

        self._walter_streaming_client_factory = legacy_factory


def provider_with(data_client):
    return SimpleNamespace(
        _snapshot_client=SimpleNamespace(
            sdk=SimpleNamespace(
                sdk_client=data_client,
            )
        ),
        diagnostics={"webull_stream": {}},
    )


def test_gs546_v2_identity_is_stable_and_differs_from_gs545():
    first = market_evidence.webull_stream_retry_owner_session_id()
    second = market_evidence.webull_stream_retry_owner_session_id()

    assert first == second
    assert first == gs546.SESSION_ID_V2
    assert len(first) == 32
    assert first != market_evidence.webull_stream_takeover_session_id()


def test_gs546_factory_passes_sdk_no_retry_policy():
    StreamingModule.DataStreamingClient.calls.clear()
    client = DataClient()

    factory = market_evidence.single_retry_owner_webull_stream_factory(
        client,
        "app-key",
        "app-secret",
        StreamingModule,
        RetryModule.NO_RETRY_POLICY,
    )
    created = factory()

    assert isinstance(created, StreamingModule.DataStreamingClient)
    assert created.args[:3] == ("app-key", "app-secret", "us")
    assert created.args[3] == gs546.SESSION_ID_V2
    assert created.kwargs["retry_policy"] is RetryModule.NO_RETRY_POLICY


def test_gs546_authority_rebinds_without_opening_connection(monkeypatch):
    StreamingModule.DataStreamingClient.calls.clear()
    client = DataClient()
    provider = provider_with(client)

    def importer(name):
        if name == "webull.data.data_streaming_client":
            return StreamingModule
        if name == "webull.core.retry.retry_policy":
            return RetryModule
        raise AssertionError(name)

    monkeypatch.setattr(
        market_evidence.importlib,
        "import_module",
        importer,
    )

    assert market_evidence.install_webull_stream_retry_owner(
        provider,
        "app-key",
        "app-secret",
    ) is True
    assert StreamingModule.DataStreamingClient.calls == []

    created = client._walter_streaming_client_factory()
    assert created.kwargs["retry_policy"] is RetryModule.NO_RETRY_POLICY

    trace = provider.diagnostics["webull_stream"][
        "gs546_stream_retry_owner"
    ]
    assert trace["stable_session_identity_v2"] is True
    assert trace["sdk_internal_retry_disabled"] is True
    assert trace["walter_gs469_is_sole_retry_owner"] is True
    assert trace["network_connection_opened_here"] is False
    assert trace["trading_authority_changed"] is False


def test_gs546_warm_fallback_has_same_no_retry_contract(monkeypatch):
    StreamingModule.DataStreamingClient.calls.clear()
    client = DataClient()
    provider = provider_with(client)

    monkeypatch.setattr(
        gs546,
        "_market",
        lambda: SimpleNamespace(),
    )

    def importer(name):
        if name == "webull.data.data_streaming_client":
            return StreamingModule
        if name == "webull.core.retry.retry_policy":
            return RetryModule
        raise AssertionError(name)

    monkeypatch.setattr(
        gs546.importlib,
        "import_module",
        importer,
    )

    assert gs546.install_for_provider(
        provider,
        "app-key",
        "app-secret",
    ) is True
    created = client._walter_streaming_client_factory()

    assert created.args[3] == gs546.SESSION_ID_V2
    assert created.kwargs["retry_policy"] is RetryModule.NO_RETRY_POLICY
    trace = provider.diagnostics["webull_stream"][
        "gs546_stream_retry_owner"
    ]
    assert trace["warm_generation_fallback"] is True


def test_gs546_live_app_overrides_gs545_before_any_stream_open():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = source.index('if provider_name.upper() == "WEBULL":')
    gs545_bind = source.index("gs545.install_for_provider(", start)
    gs546_bind = source.index("gs546.install_for_provider(", start)
    initialize = source.index("client.initialize_quotes(seeds", start)

    assert start < gs545_bind < gs546_bind < initialize


def test_gs546_health_exposes_retry_owner_truth():
    source = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")

    assert '"gs546_stable_session_identity_v2"' in source
    assert '"gs546_sdk_internal_retry_disabled"' in source
    assert '"gs546_walter_gs469_is_sole_retry_owner"' in source


def test_gs546_scope_is_transport_lifecycle_only():
    source = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")
    start = source.index(
        "# GS546 single owner for Webull stream reconnect lifecycle"
    )
    end = source.index(
        "# GS488 Webull rc105 connection-limit containment",
        start,
    )
    block = source[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "expansion_score =",
        "opportunity_state =",
        "place_order(",
        "submit_order(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in block for token in forbidden)
