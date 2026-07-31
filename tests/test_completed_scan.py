from datetime import datetime, timezone

from mide.completed_scan import (
    CompletedScan,
    completed_scan_for_view,
    store_completed_scan,
)
from mide.session_controls import (
    DATA_MODE_KEY,
    PROVIDER_KEY,
    finish_scan,
    initialize_session_controls,
    request_scan,
    select_data_mode,
)


def test_live_webull_completed_scan_is_the_authority_for_diagnostics_and_views():
    """Changing/rerendering controls cannot replace completed Webull evidence."""
    state = {}
    initialize_session_controls(state, default_mode="Live Alpaca")
    state[DATA_MODE_KEY] = "Live Webull"
    select_data_mode(state)
    request_scan(state)

    sources = [
        {
            "Stage": "Universe (tradable symbol list)",
            "Actual provider": "Webull OpenAPI rankings",
            "Endpoint / operation": "/api/quote/tickerRealTime/query",
            "Alpaca used": "No",
        },
        {
            "Stage": "Quote / snapshot retrieval",
            "Actual provider": "Webull OpenAPI",
            "Endpoint / operation": "/api/quote/ticker/query",
            "Alpaca used": "No",
        },
    ]
    scan = CompletedScan(
        provider=state[PROVIDER_KEY],
        records=[{"symbol": "TEST"}],
        diagnostics={
            "selected_provider": "WEBULL",
            "active_pipeline_sources": sources,
        },
        warnings=[],
        symbols_sampled=1,
        prefilter_count=1,
        completed_at=datetime.now(timezone.utc),
        source_label="Live WEBULL · 1 symbols sampled · 1 prefiltered",
    )
    store_completed_scan(state, scan)
    finish_scan(state)

    # Opening any view is a read of the same completed object, not construction
    # of a new provider or a new default session result.
    views = (
        "Radar",
        "Diagnostics",
        "Trade Outcomes",
        "Session Replay",
        "Data validation",
    )
    rendered = [completed_scan_for_view(state, view) for view in views]
    assert all(item is scan for item in rendered)
    diagnostics = rendered[1]
    assert diagnostics.provider == "WEBULL"
    assert diagnostics.diagnostics["selected_provider"] == "WEBULL"
    assert diagnostics.pipeline_sources is sources
    assert [row["Endpoint / operation"] for row in diagnostics.pipeline_sources] == [
        "/api/quote/tickerRealTime/query",
        "/api/quote/ticker/query",
    ]
    assert all(row["Alpaca used"] == "No" for row in diagnostics.pipeline_sources)
    assert state["records"] is scan.records
    assert state["scan_diagnostics"] is scan.diagnostics
