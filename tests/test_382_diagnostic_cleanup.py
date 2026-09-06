from mide.webull_connection import run_connection_test


class MostlyHealthyClient:
    def __init__(self, *_args):
        pass

    def snapshots(self, symbols):
        if symbols == ["HYFM"]:
            raise RuntimeError("single-symbol probe rejected")
        return {symbol: {} for symbol in symbols}

    def get_gainers_losers(self, **_kwargs):
        return [{"symbol": "AAA"}]

    def get_most_active(self, **_kwargs):
        return [{"symbol": "AAA", "change_ratio": 5.0}]


class BrokenProductionClient(MostlyHealthyClient):
    def snapshots(self, symbols):
        raise PermissionError("entitlement denied")


def test_failed_probe_is_caution_when_production_batch_is_healthy():
    rows = run_connection_test(
        app_key="key",
        app_secret="secret",
        eligible_symbols=["AAA", "BBB"],
        client_factory=MostlyHealthyClient,
    )

    hyfm = next(row for row in rows if row["Test"] == "HYFM snapshot")
    full = next(row for row in rows if row["Test"] == "Full eligible-universe batching")

    assert list(hyfm)[0] == "Result"
    assert hyfm["Status"] == "PASS"
    assert hyfm["Diagnostic status"] == "CAUTION"
    assert hyfm["Result"].startswith("CAUTION · HYFM snapshot")
    assert "production full-universe batching passed" in hyfm["Impact"].lower()
    assert full["Status"] == "PASS"
    assert not [row for row in rows if row["Status"] == "FAIL"]


def test_real_production_snapshot_failure_remains_fail_closed():
    rows = run_connection_test(
        app_key="key",
        app_secret="secret",
        eligible_symbols=["AAA", "BBB"],
        client_factory=BrokenProductionClient,
    )

    hyfm = next(row for row in rows if row["Test"] == "HYFM snapshot")
    full = next(row for row in rows if row["Test"] == "Full eligible-universe batching")

    assert hyfm["Status"] == "FAIL"
    assert hyfm["Diagnostic status"] == "FAIL"
    assert full["Status"] == "FAIL"
    assert "entitlement denied" in full["Result"]


def test_missing_credentials_still_returns_a_readable_hard_failure():
    rows = run_connection_test(
        app_key="",
        app_secret="",
        eligible_symbols=["AAA"],
        client_factory=MostlyHealthyClient,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["Status"] == "FAIL"
    assert row["Diagnostic status"] == "FAIL"
    assert row["Result"].startswith("FAIL · Credential loading")
    assert "WEBULL_APP_KEY" in row["Result"]
