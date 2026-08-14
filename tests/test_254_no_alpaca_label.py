import mide.webull_connection as connection


def test_native_pipeline_contains_no_alpaca_provider_name():
    text = repr(connection._native_pipeline_rows())
    assert "Alpaca Trading API" not in text
