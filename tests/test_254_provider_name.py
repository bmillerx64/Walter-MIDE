import mide.webull_connection as connection


def test_native_pipeline_names_webull_as_universe_provider():
    rows = connection._webull_native_pipeline_sources(object())
    assert rows[0]["Actual provider"] == "Webull OpenAPI SDK"
