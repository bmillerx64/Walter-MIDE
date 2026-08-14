import mide.webull_connection as connection


def test_every_native_pipeline_row_marks_alpaca_unused():
    assert all(row["Alpaca used"] == "No" for row in connection._webull_native_pipeline_sources(object()))
