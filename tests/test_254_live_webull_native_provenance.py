import mide.webull_connection  # applies deployed Live Webull cutover
from mide.webull_live import LiveWebullProvider


def test_live_webull_pipeline_provenance_reports_no_alpaca_after_cutover():
    provider = object.__new__(LiveWebullProvider)
    rows = provider.pipeline_sources()

    universe = rows[0]
    assert universe["Actual provider"] == "Webull OpenAPI SDK"
    assert "get_gainers_losers" in universe["Endpoint / operation"]
    assert "get_most_active" in universe["Endpoint / operation"]
    assert universe["Alpaca used"] == "No"
    assert all(row["Alpaca used"] == "No" for row in rows)
