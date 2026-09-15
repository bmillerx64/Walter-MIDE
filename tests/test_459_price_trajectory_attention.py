from pathlib import Path

import pandas as pd

from mide import gs310_unified_opportunity_state as unified
from mide import gs369_escalation_priority_order as gs369
from mide import gs457_maturation_leader_priority as gs457
from mide import gs459_price_trajectory_attention as gs459


def _frame(closes):
    index = pd.date_range("2026-09-15 14:00", periods=len(closes), freq="1min", tz="UTC")
    return pd.DataFrame(
        {
            "open": closes,
            "high": [value * 1.002 for value in closes],
            "low": [value * 0.998 for value in closes],
            "close": closes,
            "volume": [100_000] * len(closes),
        },
        index=index,
    )


def test_price_trajectory_metrics_detects_recent_velocity_acceleration():
    frame = _frame(
        [1.000, 1.002, 1.004, 1.006, 1.008, 1.010, 1.012, 1.020, 1.035, 1.055, 1.080]
    )
    metrics = gs459.price_trajectory_metrics(frame)

    assert metrics["price_trajectory_available"] is True
    assert metrics["price_change_3m_pct"] > 5.0
    assert metrics["price_velocity_3m_pct_per_min"] > metrics["price_velocity_prior_7m_pct_per_min"]
    assert metrics["price_path_acceleration_pct_per_min"] > 1.0
    assert metrics["positive_close_ratio_5m"] == 1.0
    assert metrics["giveback_from_5m_high_pct"] < 1.0


def test_price_trajectory_metrics_requires_enough_bars():
    metrics = gs459.price_trajectory_metrics(_frame([1.0] * 10))
    assert metrics["price_trajectory_available"] is False
    assert metrics["price_path_acceleration_pct_per_min"] == 0.0


def _signal_record(**updates):
    record = {
        "price_trajectory_available": True,
        "price_change_3m_pct": 2.4,
        "price_change_5m_path_pct": 3.1,
        "price_path_acceleration_pct_per_min": 0.45,
        "positive_close_ratio_5m": 0.8,
        "giveback_from_5m_high_pct": 0.4,
        "volume_acceleration_3m": 1.6,
        "dollar_flow_acceleration_3m": 1.4,
        "higher_lows": True,
        "near_hod": True,
    }
    record.update(updates)
    return record


def test_trajectory_attention_needs_path_flow_and_structure(monkeypatch):
    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda record: {"state": record.get("_state", unified.DEVELOPING)},
    )

    assert gs459.trajectory_attention(_signal_record())["active"] is True
    assert gs459.trajectory_attention(
        _signal_record(
            volume_acceleration_3m=1.0,
            dollar_flow_acceleration_3m=1.0,
            participation_score=0,
            volume_above_preceding_15m_pace=False,
            broke_previous_15m_high_with_volume=False,
        )
    )["active"] is False
    assert gs459.trajectory_attention(
        _signal_record(higher_lows=False, near_hod=False)
    )["active"] is False
    assert gs459.trajectory_attention(
        _signal_record(_state=unified.HALTED)
    )["active"] is False


def test_one_bar_spike_does_not_look_like_persistent_sparkline_ignition(monkeypatch):
    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda record: {"state": unified.DEVELOPING},
    )
    metrics = gs459.price_trajectory_metrics(
        _frame([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.05])
    )
    record = _signal_record(**metrics)
    detail = gs459.trajectory_attention(record)
    assert detail["positive_close_ratio_5m"] < gs459._MIN_POSITIVE_CLOSE_RATIO
    assert detail["active"] is False


def test_trajectory_band_sits_below_look_now_and_above_recent_confirmation(monkeypatch):
    records = [
        {"symbol": "DEV"},
        {"symbol": "TRAJ"},
        {"symbol": "RECENT"},
        {"symbol": "LOOK"},
        {"symbol": "FRESH"},
        {"symbol": "READY"},
    ]
    base_bands = {
        "READY": 50,
        "FRESH": 45,
        "LOOK": 40,
        "RECENT": 35,
        "TRAJ": 30,
        "DEV": 30,
    }
    monkeypatch.setattr(
        gs457,
        "maturation_attention",
        lambda record: {"band": base_bands[record["symbol"]]},
    )
    monkeypatch.setattr(
        gs459,
        "trajectory_attention",
        lambda record: {
            "active": record["symbol"] == "TRAJ",
            "acceleration_pct_per_min": 0.8 if record["symbol"] == "TRAJ" else 0.0,
            "change_3m_pct": 2.0 if record["symbol"] == "TRAJ" else 0.0,
            "positive_close_ratio_5m": 0.8 if record["symbol"] == "TRAJ" else 0.0,
        },
    )

    ordered = gs459.ordered_trajectory_records(
        records,
        baseline_order=lambda rows: list(rows),
    )
    assert [record["symbol"] for record in ordered] == [
        "READY",
        "FRESH",
        "LOOK",
        "TRAJ",
        "RECENT",
        "DEV",
    ]


def test_trajectory_priority_does_not_rewrite_record_state_or_entry_fields(monkeypatch):
    record = {
        "symbol": "PATH",
        "candidate_status": "Watching",
        "qualified_for_entry": False,
        "qualified_for_alert": False,
    }
    original = dict(record)
    monkeypatch.setattr(gs457, "maturation_attention", lambda row: {"band": 30})
    monkeypatch.setattr(
        gs459,
        "trajectory_attention",
        lambda row: {
            "active": True,
            "acceleration_pct_per_min": 0.5,
            "change_3m_pct": 2.0,
            "positive_close_ratio_5m": 0.8,
        },
    )
    gs459.ordered_trajectory_records([record], baseline_order=lambda rows: list(rows))
    assert record == original


def test_discovery_metric_wrapper_adds_path_evidence_without_provider_work(monkeypatch):
    from mide import discovery

    def baseline(frame):
        return {"existing": 1}

    monkeypatch.setattr(discovery, "intraday_participation_metrics", baseline)
    gs459._install_discovery_metrics()
    installed = discovery.intraday_participation_metrics
    result = installed(
        _frame([1.000, 1.002, 1.004, 1.006, 1.008, 1.010, 1.012, 1.020, 1.035, 1.055, 1.080])
    )
    assert result["existing"] == 1
    assert result["price_trajectory_available"] is True
    assert getattr(installed, "_gs459_price_trajectory_metrics", False) is True

    gs459._install_discovery_metrics()
    assert discovery.intraday_participation_metrics is installed


def test_operator_order_installer_is_idempotent(monkeypatch):
    def baseline(records):
        return list(records)

    monkeypatch.setattr(gs369, "ordered_escalation_records", baseline)
    gs459._install_operator_order()
    installed = gs369.ordered_escalation_records
    assert installed is not baseline
    assert getattr(installed, "_gs459_price_trajectory_attention", False) is True

    gs459._install_operator_order()
    assert gs369.ordered_escalation_records is installed


def test_gs459_installs_after_gs448_before_final_order():
    source = Path("mide/startup.py").read_text(encoding="utf-8")
    assert "gs459_price_trajectory_attention" in source
    assert source.index("install_gs448()") < source.index("install_gs459()")
    assert source.index("install_gs459()") < source.index("install_final_order()")


def test_gs459_scope_lock_is_attention_only():
    source = Path("mide/gs459_price_trajectory_attention.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "request_scan(",
        "place_order(",
        "submit_order(",
        "TRIGGER_",
        "PARTICIPATION_MIN_",
    )
    for token in forbidden:
        assert token not in source
    assert "price_trajectory_metrics" in source
    assert "TRAJECTORY_BAND = 38" in source
