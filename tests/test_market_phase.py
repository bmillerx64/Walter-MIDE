from datetime import datetime, timezone, timedelta

from mide.market_phase import apply_market_phase
from mide.scanner_v2 import apply_scanner_v2
from mide.ui import radar_table


def base_record(**overrides):
    record = {
        "symbol": "PHZ",
        "price": 1.2,
        "pct_change": 4.0,
        "volume": 1_000_000,
        "dollar_volume": 1_200_000,
        "spread_pct": 1.0,
        "vwap_relation": "testing",
        "vwap_distance_pct": -0.2,
        "supertrend_bullish": True,
        "supertrend_flip": True,
        "supertrend_30s_flip": True,
        "volume_acceleration": 1.4,
        "rvol_proxy": 2.0,
        "volume_pace_ratio": 1.3,
        "acceleration_ratio": 1.2,
        "higher_lows": True,
        "near_hod": False,
        "timeframes": {},
        "opportunity_score": 60,
        "conviction_score": 60,
        "status": "MONITOR",
        "participation_score": 60,
        "participation_tier": "STRONG",
        "attention_score": 60,
        "reasons": [],
        "cautions": [],
    }
    record.update(overrides)
    return record


def test_market_phase_defaults_every_symbol_to_emerging():
    result = apply_market_phase(base_record(volume_acceleration=1.0, rvol_proxy=1.0), {}, datetime(2026, 7, 24, 12, tzinfo=timezone.utc))

    assert result["market_phase"] == "Emerging"
    assert result["market_phase_history"] == [
        {"phase": "Emerging", "entered_at": "2026-07-24T12:00:00+00:00"}
    ]


def test_market_phase_requires_confirmation_before_momentum_transition():
    start = datetime(2026, 7, 24, 12, tzinfo=timezone.utc)
    momentum_record = base_record(
        vwap_relation="above",
        vwap_distance_pct=0.4,
        timeframes={
            "1m": {"supertrend": True},
            "3m": {"supertrend": True},
            "5m": {"near_supertrend_flip": True},
        },
        near_hod=True,
    )

    first = apply_market_phase(momentum_record, {}, start)
    second = apply_market_phase(momentum_record, {**momentum_record, **first}, start + timedelta(minutes=1))

    assert first["market_phase"] == "Emerging"
    assert first["market_phase_candidate"] == "Momentum"
    assert second["market_phase"] == "Momentum"
    assert [item["phase"] for item in second["market_phase_history"]] == ["Emerging", "Momentum"]


def test_broken_phase_blocks_immediate_repromotion():
    start = datetime(2026, 7, 24, 12, tzinfo=timezone.utc)
    strong = base_record(vwap_relation="above", vwap_distance_pct=0.5)
    prior = {**strong, "market_phase": "Broken", "market_phase_entered_at": start.isoformat(), "market_phase_history": [{"phase": "Broken", "entered_at": start.isoformat()}]}

    first = apply_market_phase(strong, prior, start + timedelta(minutes=1))
    second = apply_market_phase(strong, {**strong, **first}, start + timedelta(minutes=2))
    third = apply_market_phase(strong, {**strong, **second}, start + timedelta(minutes=3))

    assert first["market_phase"] == "Broken"
    assert second["market_phase"] == "Broken"
    assert third["market_phase"] == "Emerging"


def test_apply_scanner_v2_attaches_persistent_market_phase_to_records():
    scan_time = datetime(2026, 7, 24, 12, tzinfo=timezone.utc)
    output = apply_scanner_v2([base_record()], {}, scan_time)

    assert output[0]["market_phase"] == "Emerging"
    assert output[0]["market_phase_entered_at"] == scan_time.isoformat()
    assert output[0]["market_phase_history"][0]["phase"] == "Emerging"


def test_radar_table_displays_market_phase_alongside_tier():
    df = radar_table([base_record(market_phase="Momentum")])

    assert df.loc[0, "Tier"] == "STRONG"
    assert df.loc[0, "Phase"] == "Momentum"
