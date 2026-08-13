"""Compact audit summaries for Walter historical decision replay."""

from __future__ import annotations

from mide.decision_time_evidence import verify_decision_time_evidence


def audit_scan_replayability(scan: dict) -> dict:
    """Summarize immutable-evidence coverage and integrity for one recorded scan."""
    symbols = scan.get("symbols", [])
    evidenced = [p for p in symbols if p.get("decision_time_evidence")]
    valid = [p for p in evidenced if verify_decision_time_evidence(p["decision_time_evidence"])]
    invalid = [p for p in evidenced if not verify_decision_time_evidence(p["decision_time_evidence"])]
    return {
        "scan_id": scan.get("scan_id"),
        "symbols": len(symbols),
        "replayable": len(valid),
        "invalid_evidence": len(invalid),
        "legacy_without_evidence": len(symbols) - len(evidenced),
        "replayable_symbols": [p.get("symbol") for p in valid],
        "invalid_symbols": [p.get("symbol") for p in invalid],
    }
