from mide import free_float_inspector
from mide.webull_live import LiveWebullProvider


def _provider():
    provider = object.__new__(LiveWebullProvider)
    provider.diagnostics = {}
    provider.warnings = []
    return provider


def test_live_webull_normalizes_float_millions_to_share_count_without_network():
    provider = _provider()
    snapshots = {"FRTT": {"float_millions": 4.28}}

    provider.enrich_free_float(snapshots, ["FRTT"])

    assert snapshots["FRTT"]["float_shares"] == 4_280_000
    assert provider.diagnostics["free_float_snapshot_normalized"] == 1
    assert provider.diagnostics["free_float_fallback_requested"] == 0


def test_live_webull_uses_yahoo_fallback_for_missing_float(monkeypatch):
    class FakeYahoo:
        def __init__(self, *args, **kwargs):
            pass

        def lookup_many(self, symbols):
            assert list(symbols) == ["PLUG"]
            return {"PLUG": 1_330_000_000.0}, {}

    monkeypatch.setattr(free_float_inspector, "YahooFinanceFloatProvider", FakeYahoo)
    provider = _provider()
    snapshots = {"PLUG": {}}

    provider.enrich_free_float(snapshots, ["PLUG"])

    assert snapshots["PLUG"]["float_shares"] == 1_330_000_000.0
    assert snapshots["PLUG"]["free_float_source"].startswith("Yahoo Finance")
    assert provider.diagnostics["free_float_fallback_requested"] == 1
    assert provider.diagnostics["free_float_fallback_resolved"] == 1
    assert provider.diagnostics["free_float_fallback_failed"] == 0
