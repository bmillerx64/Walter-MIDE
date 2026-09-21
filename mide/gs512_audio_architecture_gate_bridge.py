"""GS512: bridge current Architecture-v1 gate truth into attention audio.

Sep. 21 live LOBO evidence isolated an audio compatibility failure. At 09:31 ET LOBO
was already WATCH NOW, ~0.7% above VWAP, bullish on 30s/1m/3m/5m/10m, and Architecture
v1 had qualified both Participation Assessment and Expansion Assessment. Walter ranked
it, but GS473/GS492 stayed silent because those audio layers still required the legacy
top-level participation_gate / structure_gate dictionaries.

GS303 already defines the authoritative compatibility mapping from Architecture audit
rows for Flight Recorder diagnostics. GS512 reuses that exact mapping for audio only:
explicit live gate dictionaries still win when present; otherwise GS303's audit mapping
supplies the boolean gate truth.

No thresholds, scores, ranks, qualification, opportunity state, entry readiness,
market-data values, execution, or orders change.
"""
from __future__ import annotations


AUTHORITY = "AUDIO_COMPATIBILITY_ONLY"
_OWNER = "_walter_gs512_audio_architecture_gate_bridge"

_STAGE_BY_GATE = {
    "participation_gate": "Participation Assessment",
    "structure_gate": "Expansion Assessment",
}


def authoritative_gate_passed(record: dict, name: str) -> bool:
    """Resolve one audio gate from explicit truth, then Architecture-v1 audit truth."""
    direct = record.get(name)
    if isinstance(direct, dict) and "passed" in direct:
        return direct.get("passed") is True

    evidence = record.get("decision_time_evidence") or {}
    if isinstance(evidence, dict):
        nested = evidence.get(name)
        if isinstance(nested, dict) and "passed" in nested:
            return nested.get("passed") is True

    stage = _STAGE_BY_GATE.get(str(name))
    if not stage:
        return False

    from .gs303_flight_recorder_authoritative_funnel import _gate_from_audit, _stage_audit

    compatibility = _gate_from_audit(_stage_audit(record, stage))
    return compatibility.get("passed") is True


def install() -> None:
    """Bind the authoritative audit fallback into the existing audio layers."""
    from . import gs473_operator_attention_audio as gs473
    from . import gs492_maturation_transition_audio as gs492

    # These helpers are looked up in module globals at call time. Rebinding closes
    # both cold- and warm-runtime compatibility gaps without wrapping phrases or
    # changing alert priority.
    gs473._gate_passed = authoritative_gate_passed
    gs492._gate_passed = authoritative_gate_passed
