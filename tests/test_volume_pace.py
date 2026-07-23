from datetime import datetime, timedelta, timezone

import pandas as pd

from mide.scanner_v2 import apply_scanner_v2
from mide.volume_pace import clear_volume_profile_cache, volume_pace_metrics


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
