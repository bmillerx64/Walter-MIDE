"""Authoritative Walter Next Replay / Validation boundary.

Stable recorder/outcome classes remain direct imports. Replaceable validation
functions resolve dynamically so warm Streamlit reruns cannot retain stale wrappers.
"""

from __future__ import annotations

from mide.flight_recorder import FlightRecorder
from mide.mission_outcomes import MissionOutcomeStore


def prefilter_decision(*args, **kwargs):
    from mide import flight_recorder
    return flight_recorder.prefilter_decision(*args, **kwargs)


def scan_integrity_report(*args, **kwargs):
    from mide import data_integrity
    return data_integrity.scan_integrity_report(*args, **kwargs)


__all__ = [
    "FlightRecorder",
    "MissionOutcomeStore",
    "prefilter_decision",
    "scan_integrity_report",
]
