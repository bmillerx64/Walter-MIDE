"""GS428: remove obsolete post-scan deadtime after GS413 owns AutoScan authority.

Sep. 10 live Flight Recorder timing showed a repeatable ~15-21 second gap between a
completed scan and the next scan attempt even though the configured 60-second cadence
had already expired while the prior scan was still running. Ten seconds of that gap is
an intentional GS412 cross-session handoff guard added before GS413 established one
process-wide AutoScan cadence owner.

GS413 now prevents passive Streamlit sessions from manufacturing automatic scan
requests and the process watchdog still prevents overlap. Keeping the old successful-
completion guard on the production singleton therefore adds deadtime without adding a
new exclusion guarantee.

GS428 leaves the ScanWatchdog class/default contract untouched for standalone callers
and tests. It changes only the production PROCESS_SCAN_WATCHDOG singleton, and only
after GS413 is demonstrably installed. No market data, discovery, indicators, gates,
scoring, ranking, alerts, execution, or orders are changed.
"""
from __future__ import annotations

AUTHORITY = "ORCHESTRATION_LATENCY_ONLY"
_INSTALLED = False


def install() -> None:
    """Disable only the obsolete successful-completion guard on Walter's singleton."""
    global _INSTALLED
    if _INSTALLED:
        return

    from . import session_controls, watchdog

    # Do not weaken GS412 in a runtime that does not have GS413's single-process
    # scheduler ownership. This makes the change conditional on the newer guardrail.
    if not getattr(
        session_controls.autoscan_request_due,
        "_gs413_single_process_autoscan_authority",
        False,
    ):
        raise RuntimeError("GS428 requires GS413 single-process AutoScan authority")

    process_watchdog = watchdog.PROCESS_SCAN_WATCHDOG
    previous = float(getattr(process_watchdog, "completed_handoff_guard_seconds", 0.0))
    process_watchdog._walter_gs428_previous_handoff_guard_seconds = previous
    process_watchdog.completed_handoff_guard_seconds = 0.0
    process_watchdog._walter_gs428_scheduler_deadtime_release = True
    process_watchdog._walter_gs428_authority = AUTHORITY
    _INSTALLED = True
