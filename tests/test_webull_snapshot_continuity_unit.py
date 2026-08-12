from mide.webull_connection import _merge_snapshot_continuity


def test_merge_preserves_omitted_fields_but_accepts_fresh_values():
    previous = {
        "latestTrade": {"p": 1.20},
        "dailyBar": {"c": 1.20, "v": 250_000},
        "prevDailyBar": {"c": 1.00},
    }
    current = {
        "latestTrade": {"p": 1.21},
        "dailyBar": {"c": 1.21, "v": None},
        "prevDailyBar": {"c": None},
    }
    merged = _merge_snapshot_continuity(previous, current)
    assert merged["latestTrade"]["p"] == 1.21
    assert merged["dailyBar"]["v"] == 250_000
    assert merged["prevDailyBar"]["c"] == 1.00


def test_real_zero_is_not_replaced_by_old_value():
    merged = _merge_snapshot_continuity(
        {"dailyBar": {"v": 250_000}}, {"dailyBar": {"v": 0}}
    )
    assert merged["dailyBar"]["v"] == 0
