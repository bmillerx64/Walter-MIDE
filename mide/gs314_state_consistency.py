"""GS314: keep every trader-facing surface on one opportunity-state contract.

GS310 created the authoritative presentation state and GS311 made voice consume it,
but the detailed Radar sections and cards still exposed older scanner-state labels.
That allowed a symbol to sit under ``ENTRY READY`` while the same card said
``MONITOR`` / ``NO TRADE``.  This module changes presentation only: scanner state,
qualification, scoring, thresholds, ranking, and execution remain untouched.
"""
from __future__ import annotations

from copy import deepcopy

from .gs310_unified_opportunity_state import (
    CHASE_WAIT,
    DEVELOPING,
    HALTED,
    LOOK_NOW,
    WATCH_FOR_ENTRY,
    opportunity_state,
)


DISPLAY_ORDER = (
    WATCH_FOR_ENTRY,
    LOOK_NOW,
    DEVELOPING,
    CHASE_WAIT,
    HALTED,
)

# GS310's unified contract depends on evidence that older presentation callers did
# not necessarily provide.  Keep those legacy/minimal callers on their established
# behavior rather than manufacturing a unified state from absent evidence.  Live
# scanner records carry these fields, so current trader-facing output still uses the
# unified contract.
_UNIFIED_EVIDENCE_KEYS = frozenset(
    {
        "participation_surge_score",
        "expansion_quality",
        "vwap_distance_pct",
    }
)


def _has_unified_evidence(record: dict) -> bool:
    """True when a record contains enough GS310-era evidence for unified output."""
    return any(key in record for key in _UNIFIED_EVIDENCE_KEYS)


def presentation_contract(record: dict) -> dict:
    """Return the one display state, section, and compatible user action."""
    view = opportunity_state(record)
    state = view["state"]
    if state in {WATCH_FOR_ENTRY, LOOK_NOW}:
        recommendation = {
            "label": "GET READY",
            "emoji": "🟡",
            "message": view["next_step"],
        }
    else:
        recommendation = {
            "label": "NO TRADE",
            "emoji": "🔴",
            "message": view["next_step"],
        }
    return {
        "state": state,
        "section": state,
        "recommendation": recommendation,
        "reason": view["reason"],
    }


def consistent_display_sections(records: list[dict]) -> dict[str, list[dict]]:
    """Group visible records by GS310 state without mutating scanner records."""
    from . import ui

    sections = {name: [] for name in DISPLAY_ORDER}
    for record in ui.actionable_candidate_records(records):
        state = presentation_contract(record)["section"]
        sections.setdefault(state, []).append(record)
    for records_in_state in sections.values():
        records_in_state.sort(key=ui.automatic_watching_sort_key, reverse=True)
    return sections


def install() -> None:
    """Install the consistency layer after GS310/GS311 presentation patches."""
    from . import ui

    current_sections = ui.scanner_v2_display_sections
    if not getattr(current_sections, "_gs314_state_consistency", False):
        original_sections = current_sections

        def scanner_v2_display_sections(records: list[dict]):
            actionable = ui.actionable_candidate_records(records)
            if actionable and not any(_has_unified_evidence(record) for record in actionable):
                return original_sections(records)
            sections = consistent_display_sections(records)
            return [
                (WATCH_FOR_ENTRY, sections[WATCH_FOR_ENTRY], True),
                (LOOK_NOW, sections[LOOK_NOW], True),
                (DEVELOPING, sections[DEVELOPING], True),
                (CHASE_WAIT, sections[CHASE_WAIT], False),
                (HALTED, sections[HALTED], False),
            ]

        scanner_v2_display_sections._gs314_state_consistency = True
        scanner_v2_display_sections._gs314_original = original_sections
        ui.scanner_v2_display_sections = scanner_v2_display_sections

    current_card = ui.opportunity_card
    if not getattr(current_card, "_gs314_state_consistency", False):
        original_card = current_card

        def opportunity_card(record: dict):
            if not _has_unified_evidence(record):
                return original_card(record)
            detached = deepcopy(record)
            detached["workflow_label"] = presentation_contract(record)["state"]
            return original_card(detached)

        opportunity_card._gs314_state_consistency = True
        opportunity_card._gs314_original = original_card
        ui.opportunity_card = opportunity_card

    current_recommendation = ui.trade_recommendation
    if not getattr(current_recommendation, "_gs314_state_consistency", False):
        original_recommendation = current_recommendation

        # ``opportunity_card`` resolves this module-global function at call time.
        # Replacing the UI-local binding keeps the action compatible with the same
        # presentation state for GS310-era records while retaining the established
        # recommendation for legacy/minimal records that lack unified evidence.
        def trade_recommendation(record: dict) -> dict:
            if not _has_unified_evidence(record):
                return original_recommendation(record)
            return presentation_contract(record)["recommendation"]

        trade_recommendation._gs314_state_consistency = True
        trade_recommendation._gs314_original = original_recommendation
        ui.trade_recommendation = trade_recommendation