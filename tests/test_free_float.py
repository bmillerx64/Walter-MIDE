from unittest.mock import Mock, patch

from mide.free_float import FreeFloatClient, enrich_snapshots_with_free_float


def test_fmp_lookup_uses_float_shares_not_free_float_percentage():
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = [{
        "symbol": "NCRA", "freeFloat": 62.4, "floatShares": 1_300_000
    }]

    with patch("mide.free_float.requests.get", return_value=response) as get:
        values, errors = FreeFloatClient("key", max_workers=1).lookup_many(["ncra"])

    assert values == {"NCRA": 1_300_000}
    assert errors == {}
    get.assert_called_once_with(
        "https://financialmodelingprep.com/stable/shares-float",
        params={"symbol": "NCRA", "apikey": "key"},
        timeout=12,
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


def test_fmp_lookup_reports_missing_float_as_failure():
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = [{"symbol": "NCRA", "freeFloat": 62.4}]

    with patch("mide.free_float.requests.get", return_value=response):
        values, errors = FreeFloatClient("key", max_workers=1).lookup_many(["NCRA"])

    assert values == {}
    assert errors == {"NCRA": "response contained no positive floatShares"}
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
