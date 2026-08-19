"""Install GS295 first-print ignition into the display/alert urgency layer only."""
from __future__ import annotations


def install() -> None:
    from . import escalation
    from .gs295_first_print_ignition import first_print_ignition

    if getattr(escalation, "_gs295_installed", False):
        return

    original_state = escalation.escalation_state
    original_snapshot = escalation.escalation_snapshot

    def escalation_state(record: dict) -> str:
        # Preserve every pre-existing hard stop and scanner-authoritative state.
        existing = original_state(record)
        if existing != escalation.MONITOR:
            return existing
        if first_print_ignition(record)["promoted"]:
            return escalation.WATCH_CLOSELY
        return existing

    def escalation_snapshot(record: dict) -> dict:
        snapshot = original_snapshot(record)
        ignition = first_print_ignition(record)
        snapshot["first_print_ignition"] = ignition
        snapshot["state"] = escalation_state(record)
        return snapshot

    escalation.escalation_state = escalation_state
    escalation.escalation_snapshot = escalation_snapshot
    escalation.first_print_ignition = first_print_ignition
    escalation._gs295_installed = True
