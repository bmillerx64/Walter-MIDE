from __future__ import annotations

from mide import gs424_warm_scan_history_cache as gs424


def test_gs424_is_acquisition_only():
    assert gs424.AUTHORITY == "ACQUISITION_OPTIMIZATION_ONLY"
    assert gs424.INCREMENTAL_HISTORY_REASONS == frozenset(
        {"stage6_current_session", "stage6_benchmark"}
    )
