from datetime import datetime, timezone

from mide.completed_scan import (
    CompletedScan,
    LAST_SCAN_FAILURE_KEY,
    completed_scan_for_view,
    publish_scan_result,
    scan_context,
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
    context = scan_context(state)
    provider = object()
    pipeline = object()
    context.provider_instance = provider
    context.pipeline = pipeline
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
        "What changed",
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
    assert scan_context(state) is context
    assert context.provider_instance is provider
    assert context.pipeline is pipeline


def test_failed_rerun_cannot_replace_completed_webull_scan_with_zero_symbols():
    state = {}
    completed = CompletedScan(
        provider="WEBULL",
        records=[{"symbol": "WALT"}, {"symbol": "MIDE"}],
        diagnostics={"selected_provider": "WEBULL", "universe_count": 731},
        warnings=[], symbols_sampled=731, prefilter_count=28,
        completed_at=datetime.now(timezone.utc), source_label="Live WEBULL",
    )
    publish_scan_result(state, completed)

    interrupted = CompletedScan(
        provider="WEBULL", records=[],
        diagnostics={"scan_completed": False, "provider_failures": [{}]},
        warnings=["transport interrupted"], symbols_sampled=0,
        prefilter_count=0, completed_at=datetime.now(timezone.utc),
        source_label="Live WEBULL · 0 symbols sampled",
    )
    assert publish_scan_result(state, interrupted) is completed

    for view in (
        "Radar", "Diagnostics", "Session Replay", "Trade Outcomes",
        "Data validation", "What changed",
    ):
        observed = completed_scan_for_view(state, view)
        assert observed is completed
        assert observed.provider == "WEBULL"
        assert observed.symbols_sampled == 731
        assert [row["symbol"] for row in observed.records] == ["WALT", "MIDE"]
        assert observed.diagnostics["selected_provider"] == "WEBULL"


def test_completed_empty_universe_is_never_published():
    state = {}
    empty = CompletedScan(
        provider="WEBULL", records=[], diagnostics={"scan_completed": True},
        warnings=[], symbols_sampled=0, prefilter_count=0,
        completed_at=datetime.now(timezone.utc), source_label="empty universe",
    )
    assert publish_scan_result(state, empty) is None
    assert completed_scan_for_view(state, "Radar") is None


def test_context_survives_streamlit_hot_reload_class_identity_change():
    """Old module instances are accepted by shape, not fragile isinstance."""
    state = {}

    class PreviousDeploymentContext:
        completed_scan = None
        provider_instance = object()
        pipeline = object()

    previous = PreviousDeploymentContext()
    state["scan_context"] = previous
    assert scan_context(state) is previous


def _scan(symbol: str, *, sampled: int = 34, completed: bool = True):
    return CompletedScan(
        provider="WEBULL", records=[{"symbol": symbol}] if sampled else [],
        diagnostics={"scan_completed": completed},
        warnings=[] if completed and sampled else ["fresh discovery was empty"],
        symbols_sampled=sampled, prefilter_count=6 if sampled else 0,
        completed_at=datetime.now(timezone.utc), source_label="Live WEBULL",
    )


def test_successful_scan_survives_ordinary_streamlit_rerun():
    state = {}
    first = _scan("FIRST")
    publish_scan_result(state, first)

    initialize_session_controls(state, default_mode="Live Webull", scan_running=False)

    assert completed_scan_for_view(state, "rerun") is first


def test_auto_scan_begin_keeps_completed_result_visible_until_publication():
    state = {}
    first = _scan("FIRST")
    publish_scan_result(state, first)

    initialize_session_controls(state, default_mode="Live Webull", scan_running=True)

    assert completed_scan_for_view(state, "pending auto scan") is first


def test_failed_or_empty_auto_scan_preserves_result_and_surfaces_failure():
    state = {}
    first = _scan("FIRST")
    publish_scan_result(state, first)

    assert publish_scan_result(state, _scan("", sampled=0)) is first
    assert completed_scan_for_view(state, "failed auto scan") is first
    assert state[LAST_SCAN_FAILURE_KEY]["message"] == "fresh discovery was empty"


def test_successful_auto_scan_atomically_replaces_completed_result():
    state = {}
    first = _scan("FIRST")
    second = _scan("SECOND", sampled=35)
    publish_scan_result(state, first)

    assert completed_scan_for_view(state, "pending") is first
    assert publish_scan_result(state, second) is second
    assert completed_scan_for_view(state, "complete") is second
    assert state[LAST_SCAN_FAILURE_KEY] is None
