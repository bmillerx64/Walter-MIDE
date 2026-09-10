from datetime import datetime, timezone

from mide import gs424_warm_scan_history_cache as gs424


def test_timestamp_parser_accepts_iso_and_epoch_milliseconds():
    iso = gs424._utc_datetime("2026-09-10T14:00:00Z")
    ms = gs424._utc_datetime(1789048800000)
    assert iso == datetime(2026, 9, 10, 14, 0, tzinfo=timezone.utc)
    assert ms == datetime(2026, 9, 10, 14, 0, tzinfo=timezone.utc)
