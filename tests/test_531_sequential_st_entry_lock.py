from datetime import datetime, timedelta, timezone

from mide.scanner_v2 import (
    _fresh_sequential_st_confirmation,
    trigger_diagnostics,
)


def _record(now, *, quality=63, surge=88, vwap=1.7):
    return {
        "symbol": "IMCC",
        "price": 4.35,
        "vwap_distance_pct": vwap,
        "strengthening_vwap_gate": {"distance_pct": vwap},
        "participation_surge_diagnostics": {"participation_score": surge},
        "expansion_quality": quality,
        "supertrend_flip": False,
        "trend_confirmation_sequence": {
            "progression_count": 4,
            "events": [
                {
                    "timeframe": "30s",
                    "event": "confirmed",
                    "confirmed_at": (now - timedelta(seconds=30)).isoformat(),
                },
                {
                    "timeframe": "1m",
                    "event": "confirmed",
                    "confirmed_at": (now - timedelta(seconds=20)).isoformat(),
                },
                {
                    "timeframe": "3m",
                    "event": "confirmed",
                    "confirmed_at": (now - timedelta(seconds=10)).isoformat(),
                },
            ],
        },
    }


def test_fresh_ordered_1m_3m_maturation_satisfies_only_st_lock():
    now = datetime(2026, 9, 22, 18, 38, 52, tzinfo=timezone.utc)
    result = trigger_diagnostics(_record(now), {}, now)

    assert result["passed"] is True
    assert result["supertrend_trigger_source"] == "ordered_1m_3m_maturation"
    st = next(c for c in result["checks"] if c["condition"] == "supertrend_flip")
    assert st["passed"] is True
    assert "Ordered ST maturation" in st["passed_reason"]


def test_sequential_maturation_does_not_override_vwap_guard():
    now = datetime(2026, 9, 22, 18, 38, 52, tzinfo=timezone.utc)
    result = trigger_diagnostics(_record(now, vwap=4.2), {}, now)

    assert result["passed"] is False
    assert "vwap" in result["failed_conditions"]
    assert result["supertrend_trigger_source"] == "ordered_1m_3m_maturation"


def test_sequential_maturation_does_not_override_participation_or_expansion():
    now = datetime(2026, 9, 22, 18, 38, 52, tzinfo=timezone.utc)
    result = trigger_diagnostics(_record(now, surge=42, quality=40), {}, now)

    assert result["passed"] is False
    assert "participation" in result["failed_conditions"]
    assert "expansion_beginning" in result["failed_conditions"]


def test_sequence_must_reach_at_least_3m():
    now = datetime(2026, 9, 22, 18, 38, 52, tzinfo=timezone.utc)
    record = _record(now)
    record["trend_confirmation_sequence"]["progression_count"] = 2

    evidence = _fresh_sequential_st_confirmation(record, now)

    assert evidence["passed"] is False


def test_sequence_confirmation_expires_after_three_minutes():
    now = datetime(2026, 9, 22, 18, 38, 52, tzinfo=timezone.utc)
    record = _record(now)
    for event in record["trend_confirmation_sequence"]["events"]:
        event["confirmed_at"] = (now - timedelta(seconds=181)).isoformat()

    result = trigger_diagnostics(record, {}, now)

    assert result["passed"] is False
    assert "supertrend_flip" in result["failed_conditions"]
    assert result["supertrend_trigger_source"] is None
