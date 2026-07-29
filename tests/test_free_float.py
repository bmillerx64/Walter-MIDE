from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from mide.free_float import (
    FreeFloatClient,
    cache_diagnostics_or_default,
    enrich_snapshots_with_free_float,
)


def test_diagnostics_fallback_keeps_page_safe_when_interface_is_unavailable():
    diagnostics = cache_diagnostics_or_default(object())

    assert diagnostics.cached_symbols == 0
    assert diagnostics.oldest_entry is None
    assert diagnostics.newest_entry is None


def test_diagnostics_fallback_keeps_page_safe_when_inspection_fails():
    provider = Mock()
    provider.cache_diagnostics.side_effect = RuntimeError("cache unavailable")

    diagnostics = cache_diagnostics_or_default(provider)

    assert diagnostics.cached_symbols == 0
    assert diagnostics.cache_hits == 0


def test_fmp_lookup_uses_float_shares_not_free_float_percentage(tmp_path, caplog):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = [{
        "symbol": "NCRA", "freeFloat": 62.4, "floatShares": 1_300_000
    }]

    with caplog.at_level("INFO", logger="mide.free_float"), patch(
        "mide.free_float.requests.get", return_value=response
    ) as get:
        values, errors = FreeFloatClient(
            "key", max_workers=1, cache_path=tmp_path / "float.json"
        ).lookup_many(["ncra"])

    assert values == {"NCRA": 1_300_000}
    assert errors == {}
    get.assert_called_once_with(
        "https://financialmodelingprep.com/stable/shares-float",
        params={"symbol": "NCRA", "apikey": "key"},
        timeout=12,
    )
    assert caplog.messages[0] == (
        "FMP request: "
        "url=https://financialmodelingprep.com/stable/shares-float "
        "ticker=NCRA FMP_API_KEY_found=True"
    )
    assert caplog.messages[1].startswith(
        "FMP float cache: hits=0 misses=1 requests_made=1 requests_avoided=0"
    )


def test_enrichment_adds_provider_reference_without_overwriting_existing_float():
    snapshots = {
        "NCRA": {"latestTrade": {"p": 1.25}},
        "KNOWN": {"float_shares": 900_000},
    }

    class Provider:
        def lookup_many(self, symbols):
            assert symbols == ["NCRA"]
            return {"NCRA": 1_300_000}, {}

    count, errors = enrich_snapshots_with_free_float(snapshots, Provider())

    assert count == 1
    assert errors == {}
    assert snapshots["NCRA"]["reference"] == {
        "float_shares": 1_300_000,
        "provider": "Financial Modeling Prep",
    }
    assert snapshots["KNOWN"]["float_shares"] == 900_000


def test_fmp_lookup_reports_missing_float_as_failure(tmp_path):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = [{"symbol": "NCRA", "freeFloat": 62.4}]

    with patch("mide.free_float.requests.get", return_value=response):
        values, errors = FreeFloatClient(
            "key", max_workers=1, cache_path=tmp_path / "float.json"
        ).lookup_many(["NCRA"])

    assert values == {}
    assert errors == {"NCRA": "response contained no positive floatShares"}


def test_fmp_float_cache_is_reused_across_client_instances(tmp_path):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = [{"symbol": "NCRA", "floatShares": 1_300_000}]
    cache_path = tmp_path / "float.json"

    with patch("mide.free_float.requests.get", return_value=response) as get:
        first = FreeFloatClient("key", max_workers=1, cache_path=cache_path)
        second = FreeFloatClient("key", max_workers=1, cache_path=cache_path)
        assert first.lookup_many(["NCRA"])[0] == {"NCRA": 1_300_000}
        assert second.lookup_many(["NCRA"])[0] == {"NCRA": 1_300_000}

    assert get.call_count == 1
    assert first.requests_made == 1
    assert second.requests_made == 0
    assert second.cache_hits == 1

    diagnostics = second.cache_diagnostics()
    assert diagnostics.cached_symbols == 1
    assert diagnostics.cache_hits == 1
    assert diagnostics.cache_misses == 0
    assert diagnostics.requests_made == 0
    assert diagnostics.requests_avoided == 1
    assert diagnostics.oldest_entry is not None
    assert diagnostics.newest_entry == diagnostics.oldest_entry


def test_expired_fmp_float_cache_is_refreshed(tmp_path):
    cache_path = tmp_path / "float.json"
    old_now = datetime(2026, 7, 29, 13, tzinfo=timezone.utc)
    seed = FreeFloatClient("key", cache_path=cache_path)
    seed._store([("NCRA", 900_000, None)], old_now)
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = [{"symbol": "NCRA", "floatShares": 1_300_000}]

    with patch("mide.free_float.requests.get", return_value=response) as get, patch.object(
        FreeFloatClient, "_now", return_value=old_now + timedelta(hours=25)
    ):
        client = FreeFloatClient("key", max_workers=1, cache_path=cache_path)
        values, errors = client.lookup_many(["NCRA"])

    assert values == {"NCRA": 1_300_000}
    assert errors == {}
    assert client.requests_made == 1
    get.assert_called_once()


def test_fmp_failure_cache_prevents_retry_until_short_ttl_expires(tmp_path):
    response = Mock()
    response.raise_for_status.side_effect = RuntimeError("429 rate limit")
    now = datetime(2026, 7, 29, 13, tzinfo=timezone.utc)
    client = FreeFloatClient("key", max_workers=1, cache_path=tmp_path / "float.db")

    with patch("mide.free_float.requests.get", return_value=response) as get, patch.object(
        FreeFloatClient, "_now", return_value=now
    ):
        assert client.lookup_many(["NCRA"])[1] == {"NCRA": "429 rate limit"}
    with patch("mide.free_float.requests.get", return_value=response) as get_again, patch.object(
        FreeFloatClient, "_now", return_value=now + timedelta(minutes=5)
    ):
        assert client.lookup_many(["NCRA"])[1] == {"NCRA": "429 rate limit"}
        get_again.assert_not_called()
        assert client.requests_avoided == 1
    with patch("mide.free_float.requests.get", return_value=response) as get_expired, patch.object(
        FreeFloatClient, "_now", return_value=now + timedelta(minutes=11)
    ):
        client.lookup_many(["NCRA"])
        get_expired.assert_called_once()


def test_optional_bulk_preload_populates_daily_cache(tmp_path):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = [
        {"symbol": "NCRA", "floatShares": 1_300_000},
        {"symbol": "OTHER", "floatShares": 2_000_000},
    ]
    cache_path = tmp_path / "float.db"

    with patch("mide.free_float.requests.get", return_value=response) as get:
        first = FreeFloatClient("key", cache_path=cache_path, preload_bulk=True)
        assert first.lookup_many(["NCRA"])[0] == {"NCRA": 1_300_000}
        second = FreeFloatClient("key", cache_path=cache_path)
        assert second.lookup_many(["OTHER"])[0] == {"OTHER": 2_000_000}

    get.assert_called_once_with(
        "https://financialmodelingprep.com/stable/shares-float-all",
        params={"apikey": "key"},
        timeout=12,
    )
    assert second.requests_made == 0
    assert second.cache_hits == 1
from mide.alpaca import AlpacaClient
from mide.discovery import snapshot_identity_records
from mide.free_float import YahooFinanceFloatProvider


def test_yahoo_parser_reads_nested_raw_float_shares():
    payload = {"quoteSummary": {"result": [{"defaultKeyStatistics": {
        "floatShares": {"raw": 1_234_567, "fmt": "1.23M"}
    }}], "error": None}}

    assert YahooFinanceFloatProvider.parse(payload) == 1_234_567
    assert YahooFinanceFloatProvider.parse({"quoteSummary": {"result": None}}) is None


def test_alpaca_fallback_enriches_snapshot_with_auditable_source(monkeypatch):
    client = AlpacaClient("key", "secret")
    snapshots = {"NCRA": {"latestTrade": {"p": 1.25}}}
    monkeypatch.setattr(
        YahooFinanceFloatProvider, "lookup_many",
        lambda self, symbols: ({"NCRA": 1_300_000}, {}),
    )

    client.enrich_free_float(snapshots, ["NCRA"])

    record = snapshot_identity_records(snapshots)[0]
    assert record["float_shares"] == 1_300_000
    assert record["free_float_source"] == (
        "Yahoo Finance defaultKeyStatistics.floatShares.raw"
    )
    assert client.diagnostics["free_float_fallback_resolved"] == 1


def test_yahoo_lookup_uses_quote_summary_statistics_schema():
    cookie_response = Mock()
    crumb_response = Mock(text="request-crumb\n")
    response = Mock()
    response.json.return_value = {"quoteSummary": {"result": [
        {"defaultKeyStatistics": {"floatShares": {"raw": 2_000_000}}}
    ]}}
    provider = YahooFinanceFloatProvider(timeout=7, max_workers=1)
    provider.session.get = Mock(
        side_effect=[cookie_response, crumb_response, response, response]
    )

    assert provider.lookup("ncra") == 2_000_000
    assert isinstance(provider.lookup_many(["NCRA"])[0]["NCRA"], float)

    assert provider.session.get.call_args_list[0].args == ("https://fc.yahoo.com",)
    assert provider.session.get.call_args_list[1].args == (
        "https://query2.finance.yahoo.com/v1/test/getcrumb",
    )
    assert provider.session.get.call_args_list[2].args == (
        "https://query2.finance.yahoo.com/v10/finance/quoteSummary/NCRA",
    )
    assert provider.session.get.call_args_list[2].kwargs["params"] == {
        "modules": "defaultKeyStatistics",
        "crumb": "request-crumb",
    }
    assert provider.session.get.call_args_list[3].kwargs["params"]["crumb"] == (
        "request-crumb"
    )
    cookie_response.raise_for_status.assert_not_called()
    crumb_response.raise_for_status.assert_called_once_with()
    assert response.raise_for_status.call_count == 2
