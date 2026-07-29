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
