"""GS296/297: make first-print urgency audible without suppressing normal voice.

The GS296 synthetic alert is allowed only when Walter has explicit discovery
provenance proving this record is genuinely the symbol's first observation.
Missing ``opportunity_pulse_previous`` alone is not sufficient because live/UI
record compaction can omit that field on later scans. Treating every such record
as new can keep producing the same escalation signature and suppress Walter's
normal scan voice through the existing dedup path.

This module changes only display/audible escalation event reporting. It does not
change discovery, scoring, qualification, readiness, trigger, or execution logic.
"""
from __future__ import annotations


def _explicit_first_observation(record: dict) -> bool:
    """Return True only when discovery provenance proves a true first sighting."""
    history = record.get("discovery_history") or []
    if history:
        current_scan = record.get("discovery_last_seen_scan")
        same_scan = [
            event for event in history
            if current_scan is None or event.get("scan") == current_scan
        ]
        if same_scan:
            return any(event.get("event") == "first_seen" for event in same_scan) and not any(
                event.get("event") in {"refreshed", "rediscovered"}
                for event in same_scan
            )

    first_seen = record.get("discovery_first_seen_at")
    last_seen = record.get("discovery_last_seen_at")
    if first_seen and last_seen:
        return str(first_seen) == str(last_seen)

    # Fail open for the normal voice path: without explicit first-seen evidence,
    # do not manufacture a synthetic escalation event.
    return False


def install() -> None:
    from . import escalation
    from .gs295_first_print_ignition import first_print_ignition

    if getattr(escalation, "_gs296_installed", False):
        return

    original_changes = escalation.escalation_state_changes

    def escalation_state_changes(records: list[dict]) -> list[dict]:
        """Add New -> Watch Closely only for a proven true first observation."""
        changes = list(original_changes(records))
        changed_symbols = {
            str(item.get("symbol") or "").upper() for item in changes
        }

        for record in records:
            if record.get("opportunity_pulse_previous"):
                continue
            if not _explicit_first_observation(record):
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
