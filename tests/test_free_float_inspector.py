from mide.free_float_inspector import inspect_free_float


class Client:
    provider_name = "Test Provider"

    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error

    def stock_snapshot(self, symbol):
        if self.error:
            raise self.error
        return self.payload


def test_inspector_reports_raw_fields_and_computed_float():
    result = inspect_free_float(
        Client(
            {
                "reference": {
                    "sharesOutstanding": 20_000_000,
                    "floatShares": "3,250,000",
                    "marketCap": 40_000_000,
                }
            }
        ),
        " ncra ",
    )

    assert result.ticker == "NCRA"
    assert result.provider == "Test Provider"
    assert result.request_succeeded is True
    assert result.returned_fields == {
        "sharesOutstanding": 20_000_000,
        "floatShares": "3,250,000",
        "freeFloat": None,
        "marketCap": 40_000_000,
    }
    assert result.computed_free_float == 3_250_000
    assert result.computed_from == "reference.floatShares"


def test_inspector_makes_provider_limitation_visible():
    result = inspect_free_float(Client({"latestTrade": {"p": 1.23}}), "NCRA")

    assert result.request_succeeded is True
    assert all(value is None for value in result.returned_fields.values())
    assert result.computed_free_float is None
    assert result.error is None


def test_inspector_reports_api_failure_without_raising():
    result = inspect_free_float(Client(error=RuntimeError("provider unavailable")), "NCRA")

    assert result.request_succeeded is False
    assert result.computed_free_float is None
    assert result.error == "RuntimeError: provider unavailable"


def test_inspector_converts_explicit_millions_field():
    result = inspect_free_float(Client({"float_millions": "2.5"}), "NCRA")

    assert result.computed_free_float == 2_500_000
    assert result.computed_from == "response.float_millions × 1,000,000"
