"""GS545: one stable Webull MQTT session identity across deployments."""

from pathlib import Path
from types import SimpleNamespace

from mide.authorities import market_evidence


ROOT = Path(__file__).resolve().parents[1]


class StreamingModule:
    class DataStreamingClient:
        calls = []

        def __init__(self, *args):
            self.args = args
            type(self).calls.append(args)


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


def test_gs545_session_id_is_stable_and_sdk_safe():
    first = market_evidence.webull_stream_takeover_session_id()
    second = market_evidence.webull_stream_takeover_session_id()

    assert first == second
    assert isinstance(first, str)
    assert len(first) == 32


def test_gs545_separate_factories_reuse_same_session_id():
    StreamingModule.DataStreamingClient.calls.clear()

    first_factory = market_evidence.stable_webull_stream_factory(
        DataClient(),
        "app-key",
        "app-secret",
        StreamingModule,
    )
    second_factory = market_evidence.stable_webull_stream_factory(
        DataClient(),
        "app-key",
        "app-secret",
        StreamingModule,
    )

    first_factory()
    second_factory()

    first_args, second_args = StreamingModule.DataStreamingClient.calls
    assert first_args[:3] == ("app-key", "app-secret", "us")
    assert second_args[:3] == ("app-key", "app-secret", "us")
    assert first_args[3] == second_args[3]
    assert first_args[3] == market_evidence.webull_stream_takeover_session_id()


def test_gs545_rebinds_exact_retained_provider_without_opening_network(monkeypatch):
    StreamingModule.DataStreamingClient.calls.clear()
    client = DataClient()
    provider = provider_with(client)

    monkeypatch.setattr(
        market_evidence.importlib,
        "import_module",
        lambda name: (
            StreamingModule
            if name == "webull.data.data_streaming_client"
            else __import__(name)
        ),
    )

    assert market_evidence.install_webull_stream_session_takeover(
        provider,
        "app-key",
        "app-secret",
    ) is True

    # Installation only replaces the future factory; it does not create a
    # streaming client or touch the network by itself.
    assert StreamingModule.DataStreamingClient.calls == []

    created = client._walter_streaming_client_factory()
    assert isinstance(created, StreamingModule.DataStreamingClient)
    assert created.args[3] == market_evidence.webull_stream_takeover_session_id()

    trace = provider.diagnostics["webull_stream"][
        "gs545_stream_session_takeover"
    ]
    assert trace["stable_session_identity"] is True
    assert trace["cross_deployment_takeover"] is True
    assert trace["network_connection_opened_here"] is False
    assert trace["trading_authority_changed"] is False


def test_gs545_live_app_binds_takeover_before_stream_open():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = source.index('if provider_name.upper() == "WEBULL":')
    bind = source.index("gs545.install_for_provider(", start)
    initialize = source.index("client.initialize_quotes(seeds", start)
    alpaca_branch = source.index(
        '    else:\n        api_key = get_secret("ALPACA_API_KEY")',
        start,
    )

    assert start < bind < initialize
    assert bind < alpaca_branch


def test_gs545_30s_health_exposes_takeover_truth():
    provider = provider_with(DataClient())
    provider._enable_streaming = True
    provider._subscription = None
    provider._subscribed = set()
    provider._lock = __import__("threading").Lock()
    provider._gs379_30s_current = {}
    provider._gs379_30s_closed = {}

    stream = provider.diagnostics["webull_stream"]
    stream.update(
        stream_connection_status="error",
        tick_messages_received=0,
        last_tick_timestamp_ms=None,
        thirty_second_bars_closed=0,
        thirty_second_symbols_ready=0,
        gs545_stream_session_takeover={
            "stable_session_identity": True,
        },
    )

    health = market_evidence.production_30s_health(provider)
    assert health["gs545_stable_session_takeover"] is True


def test_gs545_scope_is_transport_lifecycle_only():
    authority = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")
    start = authority.index(
        "# GS545 Webull cross-deployment stream-session takeover"
    )
    end = authority.index(
        "# GS488 Webull rc105 connection-limit containment",
        start,
    )
    block = authority[start:end]

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
