"""Health classification for Walter Flight Recorder replay coverage."""

from __future__ import annotations

from mide.replay_audit import audit_scan_replayability


def replay_health(scan: dict) -> dict:
    audit = audit_scan_replayability(scan)
    if audit["invalid_evidence"]:
        status = "FAIL"
    elif audit["replayable"]:
        status = "HEALTHY"
    else:
        status = "LEGACY"
    return {"status": status, **audit}
