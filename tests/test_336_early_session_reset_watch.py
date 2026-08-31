from datetime import datetime
from zoneinfo import ZoneInfo

from mide.gs336_early_session_reset_watch import constructive_reset, operator_override

NY = ZoneInfo("America/New_York")


def _base(**overrides):
    row = {
        "symbol": "TEST",
        "pct_change": 30.0,
        "vwap_distance_pct": 2.0,
        "vwap_relation": "above",
        "supertrend_bullish": True,
        "participation_score": 60,
        "expansion_score": 60,
        "evaluated_at": datetime(2026, 8, 31, 10, 35, tzinfo=NY),
    }
    row.update(overrides)
    return row


def test_constructive_reset_requires_structure_and_scores():
    assert constructive_reset(_base()) is True
    assert constructive_reset(_base(vwap_distance_pct=7.0)) is False
    assert constructive_reset(_base(supertrend_bullish=False)) is False
    assert constructive_reset(_base(participation_score=40)) is False
    assert constructive_reset(_base(expansion_score=40)) is False


def test_early_extended_mover_is_reset_required():
    row = _base(
        pct_change=90.0,
        vwap_distance_pct=10.0,
        participation_score=30,
        expansion_score=40,
        evaluated_at=datetime(2026, 8, 31, 10, 5, tzinfo=NY),
    )
    result = operator_override(row)
    assert result["label"] == "EARLY SESSION · RESET REQUIRED"
    assert "Watch only" in result["guidance"]


def test_post_1030_constructive_rebuild_is_second_entry_watch():
    row = _base(evaluated_at=datetime(2026, 8, 31, 10, 35, tzinfo=NY))
    result = operator_override(row)
    assert result["label"] == "SECOND ENTRY FORMING"
    assert "not an automatic entry signal" in result["guidance"]


def test_no_override_for_ordinary_post_open_record():
    row = _base(
        participation_score=20,
        expansion_score=20,
        evaluated_at=datetime(2026, 8, 31, 11, 0, tzinfo=NY),
    )
    assert operator_override(row) is None
