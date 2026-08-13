"""Gold Standard helpers for attaching immutable evidence to Flight Recorder paths."""

from __future__ import annotations

from mide.decision_time_evidence import capture_decision_time_evidence


def attach_decision_time_evidence(
    path: dict,
    record: dict | None,
    *,
    scan_id: str,
    scan_timestamp,
    data_mode: str | None = None,
) -> dict:
    """Attach a hash-protected decision snapshot without mutating live record state."""
    enriched = dict(path)
    if record:
        enriched["decision_time_evidence"] = capture_decision_time_evidence(
            record,
            scan_id=scan_id,
            scan_timestamp=scan_timestamp,
            data_mode=data_mode,
        )
    return enriched
