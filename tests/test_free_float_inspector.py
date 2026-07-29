from mide.free_float_inspector import inspect_free_float


class Provider:
    provider_name = "Test Provider"

    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error

    def lookup_many(self, symbols):
        if self.error:
            raise self.error
        symbol = list(symbols)[0]
        return ({symbol: self.value} if self.value is not None else {}, {})


def test_inspector_reports_pipeline_value_and_computed_float():
    result = inspect_free_float(
        Provider(3_250_000),
        " ncra ",
    )

    assert result.ticker == "NCRA"
    assert result.provider == "Test Provider"
    assert result.request_succeeded is True
    assert result.returned_fields == {
        "sharesOutstanding": None,
        "floatShares": 3_250_000,
        "freeFloat": None,
        "marketCap": None,
    }
    assert result.computed_free_float == 3_250_000
    assert result.computed_from == "Test Provider.lookup_many"


def test_inspector_makes_provider_limitation_visible():
    result = inspect_free_float(Provider(), "NCRA")

    assert result.request_succeeded is True
    assert all(value is None for value in result.returned_fields.values())
    assert result.computed_free_float is None
    assert result.error is None


def test_inspector_reports_api_failure_without_raising():
    result = inspect_free_float(Provider(error=RuntimeError("provider unavailable")), "NCRA")

    assert result.request_succeeded is False
    assert result.computed_free_float is None
    assert result.error == "RuntimeError: provider unavailable"


def test_inspector_reports_pipeline_error_for_symbol():
    class ErrorProvider(Provider):
        def lookup_many(self, symbols):
            return {}, {"NCRA": "no provider value"}

    result = inspect_free_float(ErrorProvider(), "NCRA")

    assert result.request_succeeded is False
    assert result.error == "RuntimeError: no provider value"
