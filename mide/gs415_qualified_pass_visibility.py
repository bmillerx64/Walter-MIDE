"""GS415: keep qualified legacy-PASS records in the trader display path.

Walter's current architecture separates qualification from the legacy generic
``status`` field.  A record can therefore be legitimately qualified/ranked while
still carrying ``status == "PASS"`` from an older scoring layer.  PASS is not an
entry authorization and it is not a rejection state.

This module is deliberately presentation-only.  It does not classify a setup,
promote watch/entry/alert qualification, manufacture an Opportunity State, or
change any VWAP, SuperTrend, participation, expansion, scoring, execution, or
order rule.  It only removes PASS from the old final display-status veto; the
existing actionable/visibility wrappers and Opportunity State interpreter remain
authoritative.
"""
from __future__ import annotations


def legacy_status_visible(record: dict) -> bool:
    """Return whether the old generic status permits default display.

    ``Removed`` retains the exact legacy veto it had before GS415.  ``PASS`` is
    intentionally neutral here because qualification/actionability has already
    been decided upstream.
    """
    return record.get("status") != "Removed"


def default_actionable_display_records(records: list[dict]) -> list[dict]:
    """Apply only the legacy Removed veto to an already-actionable collection."""
    return [record for record in records if legacy_status_visible(record)]
