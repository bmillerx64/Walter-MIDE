from mide.webull_connection import _production_snapshot_fetch, run_connection_test


class InvalidSymbolClient:
    def __init__(self, *_args):
        self.snapshot_calls = []

    def snapshots(self, symbols):
        symbols = list(symbols)
        self.snapshot_calls.append(symbols)
        if "BADADR" in symbols:
            raise RuntimeError(
                "HTTP 417 INVALID_SYMBOL: The symbols does not exist in the category. [BADADR]."
            )
        return {symbol: {} for symbol in symbols}

    def get_gainers_losers(self, **_kwargs):
        return [{"symbol": "AAA", "change_ratio": 5.0}]

    def get_most_active(self, **_kwargs):
        return [{"symbol": "AAA", "change_ratio": 5.0}]


class AuthorizationFailureClient(InvalidSymbolClient):
    def snapshots(self, symbols):
        raise PermissionError("authorization denied")


def test_connection_diagnostic_uses_production_invalid_symbol_isolation():
    symbols = [f"S{i}" for i in range(20)] + ["BADADR"] + [f"T{i}" for i in range(20)]
    rows = run_connection_test(
        app_key="key",
        app_secret="secret",
        eligible_symbols=symbols,
        client_factory=InvalidSymbolClient,
    )

    sample = next(row for row in rows if row["Test"] == "100-symbol batch")
    production = next(
        row for row in rows if row["Test"] == "Full eligible-universe batching"
    )

    assert sample["Status"] == "PASS"
    assert sample["Diagnostic status"] == "CAUTION"
    assert sample["Result"].startswith("CAUTION · 100-symbol batch")
    assert production["Status"] == "PASS"
    assert production["Diagnostic status"] == "PASS"
    assert production["Skipped/isolated symbols"] == "BADADR"
    assert production["Request count"] == 2
    assert not [row for row in rows if row["Status"] == "FAIL"]


def test_production_snapshot_diagnostic_does_not_hide_auth_failure():
    rows = run_connection_test(
        app_key="key",
        app_secret="secret",
        eligible_symbols=["AAA", "BBB"],
        client_factory=AuthorizationFailureClient,
    )

    production = next(
        row for row in rows if row["Test"] == "Full eligible-universe batching"
    )
    assert production["Status"] == "FAIL"
    assert production["Diagnostic status"] == "FAIL"
    assert "authorization denied" in production["Result"]


def test_production_snapshot_diagnostic_prefilters_known_unsupported_suffixes():
    client = InvalidSymbolClient()
    returned, request_count, skipped = _production_snapshot_fetch(
        client, ["AAA", "IPO.WI"]
    )

    assert returned == {"AAA": {}}
    assert request_count == 1
    assert skipped == ["IPO.WI"]
    assert client.snapshot_calls == [["AAA"]]
