import math

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


def test_live_webull_refreshes_only_apparent_low_float(monkeypatch):
    class FakeYahoo:
        def __init__(self, *args, **kwargs):
            pass

        def lookup_many(self, symbols):
            assert list(symbols) == ["LOW"]
            return {"LOW": 5_200_000.0}, {}

    monkeypatch.setattr(free_float_inspector, "YahooFinanceFloatProvider", FakeYahoo)
    provider = _provider()
    snapshots = {
        "LOW": {"float_shares": 2_500_000},
        "HIGH": {"float_shares": 12_000_000},
    }

    provider.enrich_free_float(snapshots, ["LOW", "HIGH"])

    assert snapshots["LOW"]["float_shares"] == 5_200_000.0
    assert snapshots["HIGH"]["float_shares"] == 12_000_000.0
    assert provider.diagnostics["free_float_fallback_requested"] == 1
    assert provider.diagnostics["free_float_fallback_resolved"] == 1


def test_live_webull_fails_closed_without_primary_float_and_does_not_query_yahoo(monkeypatch):
    class FakeYahoo:
        def __init__(self, *args, **kwargs):
            pass

        def lookup_many(self, symbols):
            raise AssertionError("Yahoo must not be called for primary-float misses")

    monkeypatch.setattr(free_float_inspector, "YahooFinanceFloatProvider", FakeYahoo)
    provider = _provider()
    snapshots = {"UNKNOWN": {}}

    provider.enrich_free_float(snapshots, ["UNKNOWN"])

    assert math.isinf(snapshots["UNKNOWN"]["float_shares"])
    assert snapshots["UNKNOWN"]["free_float_verified"] is False
    assert snapshots["UNKNOWN"]["free_float_verification_status"] == "unavailable-reject"
    assert provider.diagnostics["free_float_fail_closed"] == 1
    assert provider.diagnostics["free_float_unresolved_primary"] == 1
    assert provider.diagnostics["free_float_fallback_requested"] == 0


def test_live_webull_fails_closed_when_low_float_refresh_is_unresolved(monkeypatch):
    class FakeYahoo:
        def __init__(self, *args, **kwargs):
            pass

        def lookup_many(self, symbols):
            assert list(symbols) == ["LOW"]
            return {}, {"LOW": "rate limited"}

    monkeypatch.setattr(free_float_inspector, "YahooFinanceFloatProvider", FakeYahoo)
    provider = _provider()
    snapshots = {"LOW": {"float_shares": 2_000_000}}

    provider.enrich_free_float(snapshots, ["LOW"])

    assert math.isinf(snapshots["LOW"]["float_shares"])
    assert snapshots["LOW"]["free_float_verification_status"] == "refresh-unavailable-reject"
    assert provider.diagnostics["free_float_refresh_failed"] == 1
    assert provider.warnings == []
