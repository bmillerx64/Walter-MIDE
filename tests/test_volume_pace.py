from datetime import datetime, timedelta, timezone

import pandas as pd

from mide.discovery import VOLUME_PROFILE_LOOKBACK_DAYS
from mide.scanner_v2 import (
    VPI_MIN_ACCELERATION_RATIO,
    VPI_MIN_PACE_RATIO,
    apply_scanner_v2,
)
from mide.volume_pace import (
    MAX_PROFILE_CACHE_ENTRIES,
    _PROFILE_CACHE,
    clear_volume_profile_cache,
    volume_pace_metrics,
)


def _bars(day, volumes):
    start = datetime(day.year, day.month, day.day, 13, 30, tzinfo=timezone.utc)
    index = [start + timedelta(minutes=i) for i in range(len(volumes))]
    return pd.DataFrame(
        {"open": 1, "high": 1, "low": 1, "close": 1, "volume": volumes},
        index=pd.DatetimeIndex(index),
    )


def _record(symbol, volume, vpr, accel):
    return {
        "symbol": symbol,
        "price": 1.0,
        "pct_change": 8,
        "volume": volume,
        "dollar_volume": max(100_000, volume),
        "spread_pct": 1,
        "vwap_relation": "above",
        "vwap_distance_pct": 0.1,
        "supertrend_bullish": True,
        "supertrend_flip": False,
        "supertrend_30s_flip": True,
        "ema65_relation": "above",
        "volume_acceleration": 1.0,
        "rvol_proxy": 1.0,
        "higher_lows": True,
        "headline": "",
        "discovery_reasons": [],
        "opportunity_score": 50,
        "participation_score": 50,
        "status": "MONITOR",
        "timeframes": {
            "1m": {"above_vwap": True, "supertrend": True},
            "3m": {"above_vwap": True, "supertrend": True},
        },
        "expected_volume_by_time": volume / vpr,
        "volume_pace_ratio": vpr,
        "five_minute_volume": 50_000 * accel,
        "expected_five_minute_volume": 50_000,
        "acceleration_ratio": accel,
        "reasons": [],
        "cautions": [],
    }


def test_vpi_promotes_quiet_stock_when_news_volume_explodes_at_130pm():
    quiet_history = [_bars(datetime(2026, 7, d), [1_000] * 245) for d in (20, 21, 22)]
    today = _bars(datetime(2026, 7, 23), [1_000] * 240 + [50_000] * 5)
    frame = pd.concat(quiet_history + [today])
    clear_volume_profile_cache()

    vpi = volume_pace_metrics("NEWS", frame)

    assert vpi.volume_pace_ratio > 1.8
    assert vpi.acceleration_ratio > 40
    ranked = apply_scanner_v2(
        [_record("NEWS", 490_000, vpi.volume_pace_ratio, vpi.acceleration_ratio)], {}
    )
    assert ranked[0]["candidate_status"] in {"Strengthening", "Entry Ready"}
    assert ranked[0]["volume_pace_diagnostics"]["passed"] is True


def test_vpi_ratio_decreases_when_opening_volume_fades():
    history = [_bars(datetime(2026, 7, d), [10_000] * 120) for d in (20, 21, 22)]
    early = pd.concat(history + [_bars(datetime(2026, 7, 23), [40_000] * 30)])
    late = pd.concat(
        history + [_bars(datetime(2026, 7, 23), [40_000] * 30 + [1_000] * 90)]
    )
    clear_volume_profile_cache()

    early_vpi = volume_pace_metrics("FADE", early)
    late_vpi = volume_pace_metrics("FADE", late)

    assert early_vpi.volume_pace_ratio > late_vpi.volume_pace_ratio
    assert late_vpi.acceleration_ratio < 1


def test_vpi_gives_no_bonus_for_average_volume_session():
    history = [_bars(datetime(2026, 7, d), [10_000] * 120) for d in (20, 21, 22)]
    today = _bars(datetime(2026, 7, 23), [10_000] * 120)
    clear_volume_profile_cache()

    vpi = volume_pace_metrics("AVG", pd.concat(history + [today]))
    ranked = apply_scanner_v2(
        [_record("AVG", 1_200_000, vpi.volume_pace_ratio, vpi.acceleration_ratio)], {}
    )

    assert vpi.volume_pace_ratio == 1
    assert vpi.acceleration_ratio == 1
    assert "VPI" not in " ".join(ranked[0]["reasons"])


def test_monday_profile_uses_friday_and_five_completed_sessions():
    completed = [datetime(2026, 7, day) for day in (27, 28, 29, 30, 31)]
    monday = datetime(2026, 8, 3)
    history = [
        _bars(day, [volume])
        for day, volume in zip(completed, range(100, 600, 100))
    ]
    clear_volume_profile_cache()

    metrics = volume_pace_metrics("MON", pd.concat(history + [_bars(monday, [600])]))

    # The expected value is the mean of all five sessions, including Friday (500).
    assert metrics.expected_volume == 300
    assert metrics.volume_pace_ratio == 2
    assert metrics.status == "available"


def test_post_holiday_profile_has_five_completed_sessions():
    # Tuesday follows the Monday Labor Day closure.
    completed = [datetime(2026, 8, 31) + timedelta(days=day) for day in range(5)]
    history = [_bars(day, [1_000]) for day in completed]
    clear_volume_profile_cache()

    metrics = volume_pace_metrics(
        "HOLIDAY", pd.concat(history + [_bars(datetime(2026, 9, 8), [1_500])])
    )

    assert VOLUME_PROFILE_LOOKBACK_DAYS == 14
    assert metrics.expected_volume == 1_000
    assert metrics.volume_pace_ratio == 1.5
    assert metrics.status == "available"


def test_missing_history_is_unavailable_not_synthetic_one_x():
    metrics = volume_pace_metrics("NEW", _bars(datetime(2026, 7, 23), [10_000]))

    assert metrics.status == "unavailable"
    assert metrics.reason == "missing_historical_profile"
    assert metrics.volume_pace_ratio == 0
    assert metrics.acceleration_ratio == 0
    assert metrics.passed is False


def test_premarket_is_explicitly_unavailable():
    history = _bars(datetime(2026, 7, 22), [1_000])
    premarket = _bars(datetime(2026, 7, 23), [2_000])
    premarket.index = premarket.index - timedelta(hours=2)

    metrics = volume_pace_metrics("PRE", pd.concat([history, premarket]))

    assert metrics.status == "unavailable"
    assert metrics.reason == "outside_regular_session"
    assert metrics.volume_pace_ratio == 0


def test_current_minute_absent_from_profile_has_distinct_reason():
    history = _bars(datetime(2026, 7, 22), [1_000])
    today = _bars(datetime(2026, 7, 23), [1_000, 1_000])

    metrics = volume_pace_metrics("GAP", pd.concat([history, today]))

    assert metrics.status == "unavailable"
    assert metrics.reason == "minute_not_in_profile"
    assert metrics.passed is False


def test_volume_pace_thresholds_are_unchanged():
    assert VPI_MIN_PACE_RATIO == 1.2
    assert VPI_MIN_ACCELERATION_RATIO == 1.2


def test_volume_profile_cache_has_a_hard_lru_limit():
    clear_volume_profile_cache()
    history = _bars(datetime(2026, 7, 22), [1_000])
    today = _bars(datetime(2026, 7, 23), [2_000])
    frame = pd.concat([history, today])

    for index in range(MAX_PROFILE_CACHE_ENTRIES + 5):
        volume_pace_metrics(f"SYM{index}", frame)

    assert len(_PROFILE_CACHE) == MAX_PROFILE_CACHE_ENTRIES
    assert not any(key[0] == "SYM0" for key in _PROFILE_CACHE)
