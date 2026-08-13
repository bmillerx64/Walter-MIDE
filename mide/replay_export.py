"""Portable, read-only replay export for Walter Flight Recorder evidence."""

from __future__ import annotations

from mide.replay_audit import audit_scan_replayability


def build_replay_export(recorder) -> dict:
    """Export recorder scans plus replay-integrity metadata for offline review."""
    scans = recorder.scans()
    return {
        "format": "walter-flight-replay-v1",
        "scan_count": len(scans),
        "audits": [audit_scan_replayability(scan) for scan in scans],
        "flight_recorder": scans,
    }
