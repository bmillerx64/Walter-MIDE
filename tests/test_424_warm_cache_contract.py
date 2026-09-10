from mide import gs424_warm_scan_history_cache as gs424


def test_warm_cache_keeps_three_minute_overlap():
    assert int(gs424.OVERLAP.total_seconds()) == 180
