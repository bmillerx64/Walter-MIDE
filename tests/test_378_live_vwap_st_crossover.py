import pandas as pd

from mide import discovery
from mide import gs348_st_vwap_operator_priority as gs348
from mide import gs378_live_vwap_contract as contract
from mide import gs378_live_vwap_st_crossover as gs378


def _frame(index, prices, volumes):
    return pd.DataFrame(
        {
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "volume": volumes,
        },
        index=pd.DatetimeIndex(index),
    )


def test_primary_vwap_resets_at_0930_et_without_discarding_premarket_context():
    frame = _frame(
        pd.to_datetime(
            [
                "2026-09-04T08:00:00Z",  # 04:00 ET
                "2026-09-04T13:29:00Z",  # 09:29 ET
                "2026-09-04T13:30:00Z",  # 09:30 ET
                "2026-09-04T13:31:00Z",
            ],
            utc=True,
        ),
        [1.00, 1.00, 2.00, 2.20],
        [1_000_000, 1_000_000, 100, 100],
    )

    context = gs378.primary_vwap_context(frame)

    assert context["anchor_mode"] == "RTH_09:30_ET"
    assert context["anchor_time"].hour == 9
    assert context["anchor_time"].minute == 30
    assert context["premarket_value"] == 1.0
    assert round(context["value"], 6) == 2.1


def test_primary_vwap_remains_premarket_anchored_before_regular_open():
    frame = _frame(
        pd.to_datetime(
            ["2026-09-04T08:00:00Z", "2026-09-04T13:29:00Z"],
            utc=True,
        ),
        [1.00, 1.20],
        [100, 100],
    )

    context = gs378.primary_vwap_context(frame)

    assert context["anchor_mode"] == "PREMARKET_04:00_ET"
    assert context["anchor_time"].hour == 4
    assert round(context["value"], 6) == 1.1


def test_bar_history_reconstructs_cross_that_latest_scan_snapshot_can_miss(monkeypatch):
    index = pd.date_range(
        "2026-09-04 09:30:00",
        periods=3,
        freq="min",
        tz="America/New_York",
    )
    day = _frame(index, [0.98, 1.05, 1.02], [900_000, 1_000_000, 1_100_000])
    primary = pd.Series([1.00, 1.00, 1.00], index=index, dtype=float)

    def fake_supertrend(frame, period, multiplier):
        assert period == 10
        assert multiplier == 3
        # The line crosses above VWAP on 09:31, then is below again by 09:32.
        # A detector comparing only the 09:30 and 09:32 snapshots sees below/below.
        line = pd.Series([0.95, 1.02, 0.98], index=frame.index, dtype=float)
        trend = pd.Series([False, True, True], index=frame.index, dtype=bool)
        return line, trend

    monkeypatch.setattr(gs378, "supertrend", fake_supertrend)
    event = gs378.st_vwap_timeframe_event(
        day,
        "1m",
        primary_context={"day": day, "series": primary},
    )

    assert event["crossed"] is True
    assert event["timestamp"].startswith("2026-09-04T09:31:00")
    assert event["age_seconds"] == 60.0
    assert event["recent"] is True
    assert event["new"] is True


def _bar_cross_record(**overrides):
    record = {
        "symbol": "OLOX",
        "price": 1.05,
        "vwap_value": 1.00,
        "vwap_distance_pct": 5.0,
        "vwap_relation": "above",
        # Deliberately below VWAP now: the old scan-to-scan line detector cannot
        # manufacture a cross from this one snapshot.
        "supertrend_value": 0.98,
        "supertrend_bullish": True,
        "volume": 900_000,
        "volume_acceleration": 1.8,
        "participation_score": 28,
        "expansion_score": 48,
        "st_vwap_cross_recent": True,
        "st_vwap_cross_new": True,
        "st_vwap_cross_signature": "1m@2026-09-04T09:31:00-04:00",
        "st_vwap_cross_events": {
            "1m": {
                "new": True,
                "recent": True,
                "timestamp": "2026-09-04T09:31:00-04:00",
            },
            "3m": {"new": False, "recent": False, "timestamp": None},
        },
    }
    record.update(overrides)
    return record


def test_gs348_accepts_new_bar_derived_cross_without_requiring_prior_scan_snapshot():
    gs348.reset_state()
    record = _bar_cross_record()

    assert gs348.observe_crosses([record], now=100.0) == ["OLOX"]
    assert gs348.active_cross("OLOX", now=101.0) is True

    # The same bar event must not be treated as a new event again.
    assert gs348.observe_crosses([record], now=101.0) == []


def test_bar_derived_cross_cannot_bypass_gs348_thin_volume_support_gate():
    gs348.reset_state()
    record = _bar_cross_record(
        symbol="THIN",
        volume=160_000,
        headline="",
    )

    assert gs348.observe_crosses([record], now=200.0) == []
    assert gs348.active_cross("THIN", now=201.0) is False


def test_legacy_cross_field_keeps_existing_semantics_with_corrected_vwap_truth():
    assert contract._legacy_cross_value(
        {"vwap_reclaimed_last_10m": True, "supertrend_bullish": True}
    ) is True
    assert contract._legacy_cross_value(
        {"vwap_reclaimed_last_10m": False, "supertrend_bullish": True}
    ) is False


def test_gs378_runtime_wrappers_are_installed_after_package_initialization():
    assert getattr(
        discovery.analyze_candidates,
        "_gs378_live_vwap_st_crossover",
        False,
    ) is True
    assert getattr(
        discovery.analyze_candidates,
        "_gs378_live_vwap_contract",
        False,
    ) is True
    assert getattr(gs348.observe_crosses, "_gs378_bar_cross_handoff", False) is True
