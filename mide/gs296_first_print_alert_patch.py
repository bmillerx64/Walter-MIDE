"""GS296: make GS295 first-print urgency audible exactly once per scan event.

This patch changes only display/audible escalation event reporting. It does not
change discovery, scoring, qualification, readiness, trigger, or execution logic.
"""
from __future__ import annotations


def install() -> None:
    from . import escalation
    from .gs295_first_print_ignition import first_print_ignition

    if getattr(escalation, "_gs296_installed", False):
        return

    original_changes = escalation.escalation_state_changes

    def escalation_state_changes(records: list[dict]) -> list[dict]:
        """Include a synthetic New -> Watch Closely event for true first prints.

        GS295 intentionally has no prior opportunity pulse. The legacy transition
        detector therefore cannot produce a dedup signature for that event. This
        observer adds only the missing alert event; it does not alter candidate
        state or any trading predicate.
        """
        changes = list(original_changes(records))
        changed_symbols = {
            str(item.get("symbol") or "").upper() for item in changes
        }

        for record in records:
            if record.get("opportunity_pulse_previous"):
                continue
            ignition = first_print_ignition(record)
            if not ignition.get("promoted"):
                continue
            symbol = str(record.get("symbol") or "").upper()
            if not symbol or symbol in changed_symbols:
                continue
            changes.append(
                {
                    "symbol": symbol,
                    "from": "New",
                    "to": escalation.WATCH_CLOSELY,
                    "event": "first_print_ignition",
                }
            )
            changed_symbols.add(symbol)
        return changes

    escalation.escalation_state_changes = escalation_state_changes
    escalation._gs296_installed = True
