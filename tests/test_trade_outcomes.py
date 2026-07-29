from pathlib import Path
import subprocess
import sys

import pytest

from mide.trade_outcomes import OUTCOME_LABELS, TradeOutcomeStore


def test_ui_loads_with_empty_legacy_flight_recorder(tmp_path):
    """A cached recorder from before Trade Outcomes must not break the tab."""
    repo_path = Path(__file__).parents[1]
    app_path = str(repo_path / "app.py")
    script = f"""
from streamlit.testing.v1 import AppTest
from mide import flight_recorder

CurrentRecorder = flight_recorder.FlightRecorder
class EmptyLegacyFlightRecorder(CurrentRecorder):
    def __init__(self):
        super().__init__({str(tmp_path / 'flight_recorder.jsonl')!r})
        del self.outcomes

flight_recorder.FlightRecorder = EmptyLegacyFlightRecorder
app = AppTest.from_file({app_path!r}, default_timeout=20).run()
if app.exception:
    raise AssertionError([exception.value for exception in app.exception])
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_register_mark_and_persist_complete_trade_outcome(tmp_path):
    store = TradeOutcomeStore(tmp_path / "outcomes.json")
    alert = store.register_alert(
        {
            "symbol": "abcd",
            "timestamp": "2026-07-29T13:15:00+00:00",
            "price": 2.0,
            "quality_grade": "A",
            "float_millions": 1.5,
            "rvol_proxy": 9.2,
            "setup_type": "VWAP reclaim",
        }
    )

    result = store.mark(
        alert["alert_id"],
        outcome="Winner",
        entry_price=2,
        exit_price=2.5,
        mfe=30,
        mae=-4,
    )

    assert result["symbol"] == "ABCD"
    assert result["pl_pct"] == 25.0
    assert result["mfe"] == 30
    assert result["mae"] == -4
    assert TradeOutcomeStore(store.path).all() == [result]
    assert set(OUTCOME_LABELS) == {
        "No Trade",
        "Winner",
        "Loser",
        "Missed Winner",
        "Bad Alert",
    }


def test_register_is_idempotent_and_mark_validates_label(tmp_path):
    store = TradeOutcomeStore(tmp_path / "outcomes.json")
    alert = {"symbol": "ONE", "timestamp": "2026-07-29T10:00:00Z", "price": 1}
    first = store.register_alert(alert)
    second = store.register_alert(alert)

    assert first == second
    assert len(store.all()) == 1
    with pytest.raises(ValueError):
        store.mark(first["alert_id"], outcome="Maybe")


def test_analytics_cover_every_requested_dimension_and_exclude_nontrades(tmp_path):
    store = TradeOutcomeStore(tmp_path / "outcomes.json")
    for index, outcome in enumerate(("Winner", "Winner", "Loser", "No Trade")):
        alert = store.register_alert(
            {
                "alert_id": str(index),
                "symbol": f"S{index}",
                "timestamp": f"2026-07-29T10:0{index}:00Z",
                "price": 1.5,
                "quality_grade": "A",
                "float_millions": 1.2,
                "rvol_proxy": 9,
                "setup_type": "Breakout",
            }
        )
        store.mark(alert["alert_id"], outcome=outcome, exit_price=2)

    analytics = store.analytics()
    assert set(analytics) == {
        "alert_grade",
        "time_of_day",
        "float_bucket",
        "rvol_bucket",
        "price_bucket",
        "setup_type",
    }
    grade = analytics["alert_grade"][0]
    assert grade == {"bucket": "A", "wins": 2, "trades": 3, "win_rate": 66.7}
    assert analytics["float_bucket"][0]["bucket"] == "<2M"
    assert analytics["rvol_bucket"][0]["bucket"] == ">8"
    assert "66.7% win rate over the last 3 trades" in store.recommendations(3)[0]


def test_flight_recorder_export_and_session_replay_include_outcomes(tmp_path):
    from mide.flight_recorder import FlightRecorder
    from mide.session_replay import build_session_replay

    recorder = FlightRecorder(tmp_path / "flights.jsonl")
    alert = recorder.outcomes.register_alert(
        {"symbol": "PLAY", "timestamp": "2026-07-29T10:00:00Z", "price": 3}
    )
    recorder.outcomes.mark(alert["alert_id"], outcome="Loser", exit_price=2.7)

    exported = recorder.export_with_outcomes()
    assert exported["trade_outcomes"][0]["outcome"] == "Loser"
    replay = build_session_replay(
        {
            "symbol": "PLAY",
            "flight_recorder": [],
            "trade_outcomes": exported["trade_outcomes"],
        }
    )
    assert replay["latest_outcome"]["outcome"] == "Loser"
    assert replay["latest_outcome"]["pl_pct"] == -10.0
