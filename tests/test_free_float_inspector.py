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


def test_inspector_identifies_cache_and_live_fmp_sources():
    class DiagnosticProvider(Provider):
        provider_name = "Financial Modeling Prep"

        def __init__(self, value, live):
            super().__init__(value)
            self.requests_made = 0
            self.live = live

        def lookup_many(self, symbols):
            if self.live:
                self.requests_made += 1
            return super().lookup_many(symbols)

    cached = inspect_free_float(DiagnosticProvider(1_000_000, False), "NCRA")
    live = inspect_free_float(DiagnosticProvider(1_000_000, True), "NCRA")

    assert cached.source == "Cache"
    assert "Cache hit" in cached.cache_status
    assert live.source == "FMP"
    assert "cache was not bypassed" in live.cache_status
    assert live.cache_bypassed is False


def test_inspector_reports_yahoo_fallback_source():
    result = inspect_free_float(
        Provider(error=RuntimeError("FMP unavailable")),
        "NCRA",
        Provider(2_500_000),
    )

    assert result.request_succeeded is True
    assert result.source == "Yahoo fallback"
    assert result.computed_free_float == 2_500_000
    assert "Yahoo fallback used" in result.cache_status
