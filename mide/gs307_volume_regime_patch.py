"""Install GS307 fresh volume-regime urgency into the display/alert layer only."""
from __future__ import annotations


def install() -> None:
    from . import escalation
    from .gs307_volume_regime_urgency import volume_regime_urgency

    if getattr(escalation, "_gs307_installed", False):
        return

    original_state = escalation.escalation_state
    original_snapshot = escalation.escalation_snapshot

    def escalation_state(record: dict) -> str:
        # Preserve all pre-existing authoritative states and hard extension stops.
        existing = original_state(record)
        if existing != escalation.MONITOR:
            return existing
        if volume_regime_urgency(record)["promoted"]:
            return escalation.WATCH_CLOSELY
        return existing

    def escalation_snapshot(record: dict) -> dict:
        snapshot = original_snapshot(record)
        snapshot["volume_regime_urgency"] = volume_regime_urgency(record)
        snapshot["state"] = escalation_state(record)
        return snapshot

    escalation.escalation_state = escalation_state
    escalation.escalation_snapshot = escalation_snapshot
    escalation.volume_regime_urgency = volume_regime_urgency
    escalation._gs307_installed = True
