from __future__ import annotations

from datetime import datetime, timedelta, timezone

from mide import free_float_inspector
from mide import gs426_intraday_free_float_cache as gs426


def _reset_cache():
    with gs426._CACHE_LOCK:
        gs426._CACHE.clear()


def test_success_is_reused_across_provider_instances_without_second_network_lookup(monkeypatch):
    _reset_cache()
    calls = []

    def fake_lookup_many(self, symbols):
        symbols = list(symbols)
        calls.append(symbols)
        return {symbol: 7_500_000.0 for symbol in symbols}, {}

    monkeypatch.setattr(gs426._BaseYahooFinanceFloatProvider, "lookup_many", fake_lookup_many)
    first = gs426.IntradayCachedYahooFinanceFloatProvider()
    second = gs426.IntradayCachedYahooFinanceFloatProvider()

    assert first.lookup_many(["AAA"]) == ({"AAA": 7_500_000.0}, {})
    assert second.lookup_many(["AAA"]) == ({"AAA": 7_500_000.0}, {})
    assert calls == [["AAA"]]
    assert second.walter_gs426_cache_diagnostics["cache_hits"] == 1
    assert second.walter_gs426_cache_diagnostics["network_misses"] == 0


def test_transient_failure_is_reused_only_for_failure_ttl(monkeypatch):
    _reset_cache()
    clock = [datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)]
    calls = []

    monkeypatch.setattr(gs426, "_now", lambda: clock[0])

    def fake_lookup_many(self, symbols):
        symbols = list(symbols)
        calls.append(symbols)
        return {}, {symbol: "rate limited" for symbol in symbols}

    monkeypatch.setattr(gs426._BaseYahooFinanceFloatProvider, "lookup_many", fake_lookup_many)
    provider = gs426.IntradayCachedYahooFinanceFloatProvider()

    assert provider.lookup_many(["AAA"]) == ({}, {"AAA": "rate limited"})
    assert provider.lookup_many(["AAA"]) == ({}, {"AAA": "rate limited"})
    assert calls == [["AAA"]]

    clock[0] += gs426.FAILURE_TTL + timedelta(seconds=1)
    assert provider.lookup_many(["AAA"]) == ({}, {"AAA": "rate limited"})
    assert calls == [["AAA"], ["AAA"]]


def test_new_trading_date_invalidates_success_cache(monkeypatch):
    _reset_cache()
    clock = [datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)]
    calls = []
    monkeypatch.setattr(gs426, "_now", lambda: clock[0])

    def fake_lookup_many(self, symbols):
        symbols = list(symbols)
        calls.append(symbols)
        return {symbol: 4_000_000.0 for symbol in symbols}, {}

    monkeypatch.setattr(gs426._BaseYahooFinanceFloatProvider, "lookup_many", fake_lookup_many)
    provider = gs426.IntradayCachedYahooFinanceFloatProvider()
    provider.lookup_many(["AAA"])

    clock[0] += timedelta(days=1)
    provider.lookup_many(["AAA"])
    assert calls == [["AAA"], ["AAA"]]


def test_install_changes_only_live_webull_secondary_resolver_alias(monkeypatch):
    original = free_float_inspector.YahooFinanceFloatProvider
    monkeypatch.setattr(free_float_inspector, "YahooFinanceFloatProvider", original)

    gs426.install()

    assert free_float_inspector.YahooFinanceFloatProvider is gs426.IntradayCachedYahooFinanceFloatProvider
    assert getattr(
        free_float_inspector.YahooFinanceFloatProvider,
        "_gs426_intraday_cache",
        False,
    ) is True


def test_live_enrichment_keeps_conservative_max_and_reuses_secondary_result(monkeypatch):
    _reset_cache()
    calls = []

    def fake_lookup_many(self, symbols):
        symbols = list(symbols)
        calls.append(symbols)
        return {"LOW": 5_200_000.0}, {}

    monkeypatch.setattr(gs426._BaseYahooFinanceFloatProvider, "lookup_many", fake_lookup_many)
    monkeypatch.setattr(
        free_float_inspector,
        "YahooFinanceFloatProvider",
        gs426.IntradayCachedYahooFinanceFloatProvider,
    )

    class Provider:
        diagnostics = {}

    provider = Provider()
    first = {"LOW": {"float_shares": 2_500_000.0}}
    second = {"LOW": {"float_shares": 2_500_000.0}}

    free_float_inspector._webull_enrich_free_float(provider, first, ["LOW"])
    free_float_inspector._webull_enrich_free_float(provider, second, ["LOW"])

    assert first["LOW"]["float_shares"] == 5_200_000.0
    assert second["LOW"]["float_shares"] == 5_200_000.0
    assert first["LOW"]["free_float_verification_status"] == "verified-live-refresh"
    assert second["LOW"]["free_float_verification_status"] == "verified-live-refresh"
    assert calls == [["LOW"]]
