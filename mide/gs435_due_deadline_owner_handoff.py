"""GS435: hand AutoScan ownership to a live session when the cadence is already due.

The first Flight Recorder exported from the clean GS434 runtime isolated the remaining
long-cadence defect.  The scan body was only ~20-25 seconds, and the Streamlit session
was waking/rerunning repeatedly, but a 60-second AutoScan deadline was not recognized
for another ~81 seconds.  GS413's process-wide owner lease is 120 seconds: after a
hot deploy/reconnect, a live session can therefore remain passive behind an abandoned
owner until the lease expires even though the process watchdog is idle.

GS435 preserves GS413's single-process/no-overlap contract while removing that stale-
owner deadline penalty.  The normal GS413 owner still gets first authority.  If the
current session is passive, the process is idle, the shared *actual scan-start*
baseline is already due under the existing cadence predicate, and the recorded owner
has not just refreshed its heartbeat, the live session atomically becomes cadence
owner and lets the existing due path proceed.  Whichever session wins the same GS413
lock becomes the only scheduler owner; the process watchdog remains final authority.

This is orchestration latency only.  No discovery, provider request, market-data
value, VWAP, SuperTrend, participation, expansion, score, ranking, qualification,
alert/audio, execution, or order behavior changes.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, MutableMapping


AUTHORITY = "ORCHESTRATION_LATENCY_ONLY"
# A live owner that has just evaluated its own scheduler gets a small race guard.
# A genuinely abandoned owner in the observed failure is quiet for tens of seconds.
OWNER_HEARTBEAT_RACE_GUARD_SECONDS = 2.0
DIAGNOSTIC_KEY = "_walter_gs435_due_deadline_owner_handoff"
_INSTALL_GENERATION = object()


def _inherit_gs_markers(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def _same_scan_start(left: datetime | None, right: datetime | None) -> bool:
    if left is None or right is None:
        return left is right
    try:
        return abs((left - right).total_seconds()) < 0.001
    except (TypeError, ValueError):
        return False


def _claim_due_owner(
    state: MutableMapping[str, Any],
    *,
    expected_scan_start: datetime,
    now_monotonic: float | None = None,
) -> bool:
    """Atomically claim cadence authority only if the process is still idle/due."""
    from . import gs413_single_process_autoscan_authority as gs413

    if gs413._process_scan_running():
        return False

    token = gs413._session_token(state)
    clock = gs413._now_monotonic() if now_monotonic is None else float(now_monotonic)

    with gs413._PROCESS_CADENCE_LOCK:
        # A scan may have started between the caller's due calculation and this lock.
        # Never transfer ownership across a changed process scan baseline.
        if not _same_scan_start(gs413._PROCESS_LAST_SCAN_START, expected_scan_start):
            return False
        if gs413._process_scan_running():
            return False

        previous_owner = gs413._PROCESS_CADENCE_OWNER
        if previous_owner == token:
            gs413._PROCESS_CADENCE_HEARTBEAT = clock
            return True

        # If another owner has *just* touched its scheduler, give that owner the tiny
        # watchdog-acquisition window instead of stealing cadence authority mid-handoff.
        heartbeat = float(gs413._PROCESS_CADENCE_HEARTBEAT or 0.0)
        if previous_owner is not None and heartbeat > 0.0:
            owner_quiet = clock - heartbeat
            if 0.0 <= owner_quiet < OWNER_HEARTBEAT_RACE_GUARD_SECONDS:
                return False

        gs413._PROCESS_CADENCE_OWNER = token
        gs413._PROCESS_CADENCE_HEARTBEAT = clock
        state[DIAGNOSTIC_KEY] = {
            "authority": AUTHORITY,
            "reason": "shared process cadence deadline was due while prior owner was inactive",
            "previous_owner_present": previous_owner is not None,
            "process_scan_start": expected_scan_start.isoformat(),
            "trading_logic_changed": False,
        }
        return True


def install() -> None:
    """Install outside GS413 so a due passive session can safely take ownership."""
    from . import gs413_single_process_autoscan_authority as gs413
    from . import session_controls

    current_due = session_controls.autoscan_request_due
    if getattr(current_due, "_gs435_install_generation", None) is _INSTALL_GENERATION:
        return
    if not getattr(current_due, "_gs413_single_process_autoscan_authority", False):
        raise RuntimeError("GS435 requires GS413 single-process AutoScan authority")

    # GS413 wraps GS411.  Use the inner GS411 callable only after a takeover is
    # justified so the real due observation is retained in Flight Recorder timing.
    observed_due = getattr(current_due, "_gs413_original", None)
    raw_due = getattr(observed_due, "_gs411_original", None)
    if not callable(observed_due) or not callable(raw_due):
        raise RuntimeError("GS435 requires the GS411 -> GS413 AutoScan due chain")

    def due_with_deadline_owner_handoff(
        refresh_seconds: int,
        last_updated: datetime | None,
        last_scan_attempt: datetime | None,
        *,
        retry_seconds: int = 5,
        now: datetime | None = None,
    ) -> bool:
        # Healthy/current GS413 ownership remains completely authoritative.
        if current_due(
            refresh_seconds,
            last_updated,
            last_scan_attempt,
            retry_seconds=retry_seconds,
            now=now,
        ):
            return True

        state = gs413._session_state()
        if state is None:
            return False

        # Manual requests have their own explicit timestamp/lifecycle and must never
        # be converted into a scheduler-owned request by this recovery path.
        if state.get(session_controls.SCAN_REQUESTED_AT_KEY) is not None:
            return False
        if gs413._process_scan_running():
            return False

        process_start = gs413._process_scan_start()
        if process_start is None:
            return False

        # Ask the exact pre-GS411 cadence predicate whether the shared actual process
        # start is due.  This avoids both GS413 ownership rejection and a false GS411
        # due observation before we know that this session may take over.
        if not raw_due(
            refresh_seconds,
            last_updated,
            process_start,
            retry_seconds=retry_seconds,
            now=now,
        ):
            return False

        if not _claim_due_owner(state, expected_scan_start=process_start):
            return False

        # Now run the GS411 observational wrapper once with the same process baseline.
        # It records the due boundary that will be attached to this completed scan.
        return bool(
            observed_due(
                refresh_seconds,
                last_updated,
                process_start,
                retry_seconds=retry_seconds,
                now=now,
            )
        )

    _inherit_gs_markers(due_with_deadline_owner_handoff, current_due)
    due_with_deadline_owner_handoff._gs435_due_deadline_owner_handoff = True
    due_with_deadline_owner_handoff._gs435_install_generation = _INSTALL_GENERATION
    due_with_deadline_owner_handoff._gs435_original = current_due
    session_controls.autoscan_request_due = due_with_deadline_owner_handoff
