from pathlib import Path

from mide.gs498_mission_ranking_direction import mission_ranked_records
from mide.trader_priority import trader_priority_sort_key


def _record(symbol: str, *, momentum: float, historical: float = 0.0) -> dict:
    return {
        "symbol": symbol,
        "current_momentum": momentum,
        "historical_strength": historical,
        "participation_surge_score": 0.0,
        "relative_strength_score": 0.0,
        "alignment_score": 0.0,
        "timestamp": f"2026-09-18T18:{int(momentum):02d}:00+00:00",
    }


def test_strongest_priority_key_receives_first_position():
    weak = _record("WEAK", momentum=41)
    mid = _record("MID", momentum=48)
    strong = _record("STRONG", momentum=56)

    assert trader_priority_sort_key(strong) > trader_priority_sort_key(mid)
    assert trader_priority_sort_key(mid) > trader_priority_sort_key(weak)

    ranked = mission_ranked_records([weak, strong, mid])
    assert [row["symbol"] for row in ranked] == ["STRONG", "MID", "WEAK"]


def test_historical_tiebreak_remains_higher_is_better():
    lower = _record("LOWER", momentum=50, historical=20)
    higher = _record("HIGHER", momentum=50, historical=80)

    ranked = mission_ranked_records([lower, higher])
    assert [row["symbol"] for row in ranked] == ["HIGHER", "LOWER"]


def test_live_stage8_uses_canonical_descending_helper():
    app = Path("app.py").read_text(encoding="utf-8")

    assert "from mide.gs498_mission_ranking_direction import mission_ranked_records" in app
    assert "ranked_records = mission_ranked_records(records)" in app
    assert "sorted(records, key=trader_priority_sort_key)" not in app


def test_scope_lock_changes_order_only():
    source = Path("mide/gs498_mission_ranking_direction.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "participation_score =",
        "expansion_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "place_order(",
        "submit_order(",
        "play_alert(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in source for token in forbidden)
    assert "reverse=True" in source
