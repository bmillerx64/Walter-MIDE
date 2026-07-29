from unittest.mock import Mock, patch

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
    response = Mock()
    response.json.return_value = {"quoteSummary": {"result": [
        {"defaultKeyStatistics": {"floatShares": {"raw": 2_000_000}}}
    ]}}
    with patch("mide.free_float.requests.get", return_value=response) as get:
        assert YahooFinanceFloatProvider(timeout=7).lookup("ncra") == 2_000_000

    get.assert_called_once_with(
        "https://query2.finance.yahoo.com/v10/finance/quoteSummary/NCRA",
        params={"modules": "defaultKeyStatistics"},
        headers={"User-Agent": "Mozilla/5.0 (Walter-MIDE free-float lookup)"},
        timeout=7,
    )
    response.raise_for_status.assert_called_once_with()
