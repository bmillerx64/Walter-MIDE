from mide import gs424_warm_scan_history_cache as gs424


def test_only_current_session_stage6_reasons_are_incrementalized():
    assert gs424.INCREMENTAL_HISTORY_REASONS == frozenset(
        {"stage6_current_session", "stage6_benchmark"}
    )
