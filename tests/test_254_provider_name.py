import mide.webull_connection as connection


def test_native_pipeline_names_webull_as_universe_provider():
    rows = connection._native_pipeline_rows()
    assert rows[0]["Actual provider"] == "Webull OpenAPI SDK"
