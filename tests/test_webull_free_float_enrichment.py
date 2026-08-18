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
    # Keep this fixture above the current 50M squeeze ceiling so the test remains
    # focused on normalization and does not intentionally trigger the narrow
    # Yahoo freshness check used for apparent low-float names.
    snapshots = {"FRTT": {"float_millions": 54.28}}

    provider.enrich_free_float(snapshots, ["FRTT"])

    assert snapshots["FRTT"]["float_shares"] == 54_280_000
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
        # Above the current 50M ceiling, so it must not trigger a Yahoo refresh.
        "HIGH": {"float_shares": 120_000_000},
    }

    provider.enrich_free_float(snapshots, ["LOW", "HIGH"])

    assert snapshots["LOW"]["float_shares"] == 5_200_000.0
    assert snapshots["HIGH"]["float_shares"] == 120_000_000.0
    assert provider.diagnostics["free_float_fallback_requested"] == 1
    assert provider.diagnostics["free_float_fallback_resolved"] == 1


def test_live_webull_resolves_missing_primary_float_from_secondary(monkeypatch):
    class FakeYahoo:
        def __init__(self, *args, **kwargs):
            pass

        def lookup_many(self, symbols):
            assert list(symbols) == ["UNKNOWN"]
            return {"UNKNOWN": 8_400_000.0}, {}

    monkeypatch.setattr(free_float_inspector, "YahooFinanceFloatProvider", FakeYahoo)
    provider = _provider()
    snapshots = {"UNKNOWN": {}}

    provider.enrich_free_float(snapshots, ["UNKNOWN"])

    assert snapshots["UNKNOWN"]["float_shares"] == 8_400_000.0
    assert snapshots["UNKNOWN"]["free_float_verified"] is True
    assert snapshots["UNKNOWN"]["free_float_verification_status"] == "verified-secondary-source"
    assert provider.diagnostics["free_float_fail_closed"] == 0
    assert provider.diagnostics["free_float_unresolved_primary"] == 0
    assert provider.diagnostics["free_float_fallback_requested"] == 1
    assert provider.diagnostics["free_float_fallback_resolved"] == 1


def test_live_webull_fails_closed_when_primary_and_secondary_float_unresolved(monkeypatch):
    class FakeYahoo:
        def __init__(self, *args, **kwargs):
            pass

        def lookup_many(self, symbols):
            assert list(symbols) == ["UNKNOWN"]
            return {}, {"UNKNOWN": "rate limited"}

    monkeypatch.setattr(free_float_inspector, "YahooFinanceFloatProvider", FakeYahoo)
    provider = _provider()
    snapshots = {"UNKNOWN": {}}

    provider.enrich_free_float(snapshots, ["UNKNOWN"])

    assert math.isinf(snapshots["UNKNOWN"]["float_shares"])
    assert snapshots["UNKNOWN"]["free_float_verified"] is False
    assert snapshots["UNKNOWN"]["free_float_verification_status"] == "unavailable-reject"
    assert provider.diagnostics["free_float_fail_closed"] == 1
    assert provider.diagnostics["free_float_unresolved_primary"] == 1
    assert provider.diagnostics["free_float_fallback_requested"] == 1


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
