import mide.webull_connection as connection


def test_native_pipeline_contains_no_alpaca_provider_name():
    text = repr(connection._webull_native_pipeline_sources(object()))
    assert "Alpaca Trading API" not in text
