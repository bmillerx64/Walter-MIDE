"""GS515: make thesis versus trigger sequencing visually explicit.

Sep. 21 NCPL showed the operator problem clearly: a valid 3m SuperTrend retest was
mistaken for a complete trade setup before VWAP/30s/1m repair had earned the trigger.

GS514 now remembers the retest event. GS515 makes that sequencing impossible to miss
on Walter's existing Opportunity State surfaces by promoting one presentation-only
discipline line:

    THESIS VALIDATED · TRIGGER NOT EARNED

until the already-established VWAP/30s/1m repair sequence is complete.

When repair is present, Walter says:

    THESIS VALIDATED · LOWER-TF REPAIR PRESENT

but still leaves state, readiness, qualification, ranking, entry authority, execution,
orders, and audio unchanged. Existing Opportunity State remains authoritative.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps

from . import gs493_3m_st_retest_truth as gs493

AUTHORITY = "PRESENTATION_DISCIPLINE_ONLY"
_OWNER = "_walter_gs515_thesis_trigger_discipline"


def _sequence_line(sequence: dict) -> str:
    def mark(value: bool) -> str:
        return "✓" if value else "○"

    return (
        f"3m retest {mark(bool(sequence.get('three_minute_retest_held')))} · "
        f"VWAP {mark(bool(sequence.get('vwap_acceptance')))} · "
        f"30s {mark(bool(sequence.get('thirty_second_repaired')))} · "
        f"1m {mark(bool(sequence.get('one_minute_repaired')))}"
    )


def emphasize_discipline(view: dict) -> dict:
    """Add one unmistakable sequencing cue without changing Walter's state."""
    sequence = view.get("discipline_sequence") or {}
    if not isinstance(sequence, dict):
        return view

    state = str(sequence.get("state") or "")
    if state not in {
        "THESIS_HELD_TRIGGER_INCOMPLETE",
        "THESIS_HELD_TRIGGER_REPAIRED",
    }:
        return view

    result = deepcopy(view)
    existing_state = result.get("state")
    existing_color = result.get("color")
    evidence = list(result.get("evidence") or [])

    if state == "THESIS_HELD_TRIGGER_INCOMPLETE":
        result["discipline_label"] = "THESIS VALIDATED · TRIGGER NOT EARNED"
        result["discipline_ready"] = False
        existing_next = str(result.get("next_step") or "").strip()
        discipline_next = (
            "THESIS VALIDATED · TRIGGER NOT EARNED. "
            "The 3m retest held, but lower-timeframe repair is incomplete."
        )
        result["next_step"] = (
            f"{discipline_next} {existing_next}".strip()
            if discipline_next not in existing_next
            else existing_next
        )
        evidence.insert(
            0,
            {
                "label": "Entry sequence",
                "passed": False,
                "detail": _sequence_line(sequence),
            },
        )
    else:
        result["discipline_label"] = "THESIS VALIDATED · LOWER-TF REPAIR PRESENT"
        result["discipline_ready"] = True
        existing_next = str(result.get("next_step") or "").strip()
        discipline_next = (
            "THESIS VALIDATED · LOWER-TF REPAIR PRESENT. "
            "Review the chart, but Walter's existing full entry/readiness rules still control."
        )
        result["next_step"] = (
            f"{discipline_next} {existing_next}".strip()
            if discipline_next not in existing_next
            else existing_next
        )
        evidence.insert(
            0,
            {
                "label": "Entry sequence",
                "passed": True,
                "detail": _sequence_line(sequence),
            },
        )

    result["evidence"] = evidence
    result["discipline_authority"] = AUTHORITY

    # Explicit scope lock: this layer may explain the sequence, never promote it.
    result["state"] = existing_state
    if existing_color is not None:
        result["color"] = existing_color
    return result


def install() -> None:
    """Install immediately after GS514's retest-memory wrapper."""
    current = gs493.state_with_3m_st_truth
    if getattr(current, _OWNER, False):
        return

    @wraps(current)
    def state_with_discipline(original, record: dict) -> dict:
        return emphasize_discipline(current(original, record))

    setattr(state_with_discipline, _OWNER, True)
    state_with_discipline._gs515_original = current
    gs493.state_with_3m_st_truth = state_with_discipline
