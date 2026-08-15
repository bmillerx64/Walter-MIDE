from mide.webull_live import LiveWebullProvider, live_data_modes


def test_live_modes_expose_only_webull_and_demo():
    modes, index = live_data_modes(alpaca_configured=True, webull_configured=True)
    assert modes == ["Live Webull", "Demo"]
    assert index == 0
    assert "Live Alpaca" not in modes


def test_webull_mode_does_not_retain_legacy_universe_client(monkeypatch):
    class FakeSnapshotClient:
        def __init__(self):
            self.history_call_diagnostics = {}

        def stream(self, callback):
            raise AssertionError("stream should not be opened in constructor")

    legacy = object()
    provider = LiveWebullProvider(
        "app", "secret", rest_client=FakeSnapshotClient(), universe_client=legacy
    )
    assert provider._universe_client is None
    assert provider.diagnostics["alpaca_runtime_enabled"] is False
    assert provider.diagnostics["alpaca_universe_used"] is False
    assert provider.diagnostics["market_data_sources"]["universe_provider"] == (
        "Webull OpenAPI SDK native radar"
    )
