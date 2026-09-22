from datetime import datetime, timezone

from mide import scanner_v2


def _record(*, distance=1.1, participation=78.8, expansion=70.6, bullish=True):
    return {
        "symbol": "TEST",
        "supertrend_bullish": bullish,
        "supertrend_flip": False,
        "strengthening_vwap_gate": {
            "distance_pct": distance,
            "fresh_reclaim": False,
        },
        "participation_surge_diagnostics": {
            "participation_score": participation,
            "expansion_quality": expansion,
        },
        "expansion_quality": expansion,
    }


def test_sequential_progression_can_satisfy_only_st_trigger(monkeypatch):
    monkeypatch.setattr(
        scanner_v2,
        "sequential_trend_confirmation",
        lambda record, prior=None, scan_time=None: {
            "progression_count": 4,
            "conflict_count": 0,
        },
    )
    result = scanner_v2.trigger_diagnostics(
        _record(),
        {},
        datetime.now(timezone.utc),
    )

    assert result["passed"] is True
    st = next(c for c in result["checks"] if c["condition"] == "supertrend_flip")
    assert st["passed"] is True
    assert "Sequential ST progression 4 rungs" in st["passed_reason"]


def test_two_rungs_do_not_replace_fresh_flip(monkeypatch):
    monkeypatch.setattr(
        scanner_v2,
        "sequential_trend_confirmation",
        lambda record, prior=None, scan_time=None: {
            "progression_count": 2,
            "conflict_count": 0,
        },
    )
    result = scanner_v2.trigger_diagnostics(
        _record(),
        {},
        datetime.now(timezone.utc),
    )

    assert result["passed"] is False
    assert result["failed_conditions"] == ["supertrend_flip"]


def test_progression_never_bypasses_vwap_antichase(monkeypatch):
    monkeypatch.setattr(
        scanner_v2,
        "sequential_trend_confirmation",
        lambda record, prior=None, scan_time=None: {
            "progression_count": 4,
            "conflict_count": 0,
        },
    )
    result = scanner_v2.trigger_diagnostics(
        _record(distance=7.6),
        {},
        datetime.now(timezone.utc),
    )

    assert result["passed"] is False
    assert "vwap" in result["failed_conditions"]
    st = next(c for c in result["checks"] if c["condition"] == "supertrend_flip")
    assert st["passed"] is True


def test_progression_never_bypasses_participation_or_expansion(monkeypatch):
    monkeypatch.setattr(
        scanner_v2,
        "sequential_trend_confirmation",
        lambda record, prior=None, scan_time=None: {
            "progression_count": 4,
            "conflict_count": 0,
        },
    )
    result = scanner_v2.trigger_diagnostics(
        _record(participation=45, expansion=50),
        {},
        datetime.now(timezone.utc),
    )

    assert result["passed"] is False
    assert "participation" in result["failed_conditions"]
    assert "expansion_beginning" in result["failed_conditions"]
