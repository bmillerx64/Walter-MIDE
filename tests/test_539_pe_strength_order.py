from pathlib import Path

from mide import gs310_unified_opportunity_state as unified
from mide import gs539_pe_strength_order as gs539


def _record(symbol, participation, expansion, **extra):
    return {
        "symbol": symbol,
        "participation_surge_score": participation,
        "expansion_quality": expansion,
        **extra,
    }


def test_pe_strength_is_mean_of_visible_participation_and_expansion():
    edva = _record("EDVA", 85, 62)
    avat = _record("AVAT", 32, 63)

    assert gs539.pe_strength_score(edva) == 73.5
    assert gs539.pe_strength_score(avat) == 47.5


def test_sept23_edva_outranks_avat_by_visible_pe_strength():
    edva = _record("EDVA", 85, 62)
    avat = _record("AVAT", 32, 63)

    ordered = gs539.ordered_pe_strength_records(
        [avat, edva],
        baseline_order=lambda rows: list(rows),
    )

    assert [row["symbol"] for row in ordered] == ["EDVA", "AVAT"]


def test_entry_ready_remains_absolute_first_and_halted_last():
    ready = _record("READY", 60, 55, qualified_for_entry=True)
    stronger = _record("STRONGER", 99, 99)
    halted = _record("HALT", 100, 100, halted=True)

    ordered = gs539.ordered_pe_strength_records(
        [halted, stronger, ready],
        baseline_order=lambda rows: list(rows),
    )

    assert [row["symbol"] for row in ordered] == ["READY", "STRONGER", "HALT"]


def test_missing_pe_evidence_preserves_prior_tie_order():
    first = {"symbol": "FIRST"}
    second = {"symbol": "SECOND"}

    ordered = gs539.ordered_pe_strength_records(
        [second, first],
        baseline_order=lambda rows: [first, second],
    )

    assert ordered == [first, second]


def test_state_wrapper_explains_strength_without_changing_color_or_state():
    record = _record("EDVA", 85, 62)

    def original(_record):
        return {
            "state": unified.WATCH_FOR_ENTRY,
            "color": "#4ade80",
            "reason": "VWAP, trend, participation, and expansion are aligned now.",
        }

    view = gs539.state_with_pe_strength(original, record)

    assert view["state"] == unified.WATCH_FOR_ENTRY
    assert view["color"] == "#4ade80"
    assert view["pe_strength_score"] == 73.5
    assert view["reason"].startswith("P/E Strength 74/100 ·")


def test_scope_lock_is_presentation_only():
    source = Path("mide/gs539_pe_strength_order.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "participation_surge_score =",
        "participation_score =",
        "expansion_quality =",
        "expansion_score =",
        "mission_rank =",
        "place_order(",
        "submit_order(",
        "play_alert(",
    )
    assert not any(token in source for token in forbidden)
