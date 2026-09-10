"""GS413: give one Streamlit session process-wide AutoScan cadence authority.

Live validation after GS412 showed the remaining cross-session failure mode: two
Streamlit sessions could share the same completed Webull evidence yet still own
independent scheduler state.  Both sessions could therefore reach the same AutoScan
deadline, one would win the process watchdog, and the other would show
"Another Walter session is scanning" or drift onto a completion-based cadence.

GS413 is orchestration only.  It does not change Webull market data, discovery,
VWAP, SuperTrend, 30s/1m/3m authority, participation, expansion, ranking,
qualification, LOOK NOW / Entry Ready semantics, alerts, execution, or orders.

The contract is deliberately narrow:
* one live Streamlit session owns automatic scheduling for this Python process;
* the session that actually acquires an automatic/initial scan becomes owner;
* passive sessions adopt the owner's real scan-start baseline and never manufacture
  a second automatic request;
* manual Run live scan requests remain explicit and are never cleared;
* an abandoned owner lease can be taken over after a bounded idle period;
* the existing process watchdog remains the final no-overlap authority.
"""
from __future__ import annotations

import copy
from datetime import datetime
import threading
import time
from typing import Any, MutableMapping
from uuid import uuid4


SESSION_TOKEN_KEY = "_walter_gs413_session_token"
OWNER_LEASE_SECONDS = 120.0
PASSIVE_POLL_SECONDS = 10

_PROCESS_CADENCE_LOCK = threading.RLock()
_PROCESS_CADENCE_OWNER: str | None = None
_PROCESS_CADENCE_HEARTBEAT = 0.0
_PROCESS_LAST_SCAN_START: datetime | None = None


def _now_local() -> datetime:
    return datetime.now().astimezone()


def _now_monotonic() -> float:
    return time.monotonic()


def _session_state():
    """Return the active Streamlit session state, never a bare-test proxy."""
    try:
        import streamlit as st
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        if get_script_run_ctx(suppress_warning=True) is None:
            return None
        state = st.session_state
        state.get(SESSION_TOKEN_KEY)
        return state
    except Exception:
        return None


def _process_scan_running() -> bool:
    try:
        from .watchdog import PROCESS_SCAN_WATCHDOG

        return bool(PROCESS_SCAN_WATCHDOG.is_running)
    except Exception:
        return False


def _session_token(state: MutableMapping[str, Any]) -> str:
    token = str(state.get(SESSION_TOKEN_KEY) or "").strip()
    if not token:
        token = uuid4().hex
        state[SESSION_TOKEN_KEY] = token
    return token


def _owner_is_stale(now_monotonic: float) -> bool:
    if _PROCESS_CADENCE_OWNER is None:
        return True
    return now_monotonic - _PROCESS_CADENCE_HEARTBEAT >= OWNER_LEASE_SECONDS


def cadence_owner_allows(
    state: MutableMapping[str, Any],
    *,
    process_scan_running: bool | None = None,
    now_monotonic: float | None = None,
) -> bool:
    """Return whether this session owns (or may safely take over) AutoScan."""
    global _PROCESS_CADENCE_OWNER, _PROCESS_CADENCE_HEARTBEAT

    token = _session_token(state)
    now_value = _now_monotonic() if now_monotonic is None else float(now_monotonic)
    running = _process_scan_running() if process_scan_running is None else bool(
        process_scan_running
    )
    with _PROCESS_CADENCE_LOCK:
        if _PROCESS_CADENCE_OWNER is None:
            # A scan may have acquired the watchdog a few instructions before its
            # on_acquired callback records ownership. Never let a second session
            # claim cadence authority inside that tiny boundary.
            if running:
                return False
            _PROCESS_CADENCE_OWNER = token
            _PROCESS_CADENCE_HEARTBEAT = now_value
            return True
        if _PROCESS_CADENCE_OWNER == token:
            _PROCESS_CADENCE_HEARTBEAT = now_value
            return True
        if _owner_is_stale(now_value) and not running:
            _PROCESS_CADENCE_OWNER = token
            _PROCESS_CADENCE_HEARTBEAT = now_value
            return True
        return False


def passive_cadence_session(
    state: MutableMapping[str, Any],
    *,
    process_scan_running: bool | None = None,
    now_monotonic: float | None = None,
) -> bool:
    """Identify a live session that must observe but must not schedule AutoScan."""
    global _PROCESS_CADENCE_HEARTBEAT

    token = _session_token(state)
    now_value = _now_monotonic() if now_monotonic is None else float(now_monotonic)
    running = _process_scan_running() if process_scan_running is None else bool(
        process_scan_running
    )
    with _PROCESS_CADENCE_LOCK:
        if _PROCESS_CADENCE_OWNER is None:
            return running
        if _PROCESS_CADENCE_OWNER == token:
            _PROCESS_CADENCE_HEARTBEAT = now_value
            return False
        if _owner_is_stale(now_value) and not running:
            return False
        return True


def _record_actual_scan_start(
    state: MutableMapping[str, Any],
    *,
    automatic: bool,
    started_at: datetime | None = None,
    now_monotonic: float | None = None,
) -> datetime:
    """Publish the one process-wide cadence baseline only after watchdog acquire."""
    global _PROCESS_CADENCE_OWNER, _PROCESS_CADENCE_HEARTBEAT
    global _PROCESS_LAST_SCAN_START

    started = _now_local() if started_at is None else started_at
    token = _session_token(state)
    heartbeat = _now_monotonic() if now_monotonic is None else float(now_monotonic)
    with _PROCESS_CADENCE_LOCK:
        _PROCESS_LAST_SCAN_START = started
        if automatic:
            _PROCESS_CADENCE_OWNER = token
            _PROCESS_CADENCE_HEARTBEAT = heartbeat
        elif _PROCESS_CADENCE_OWNER == token:
            _PROCESS_CADENCE_HEARTBEAT = heartbeat
    # app.py historically writes last_scan_attempt before attempting the watchdog.
    # Overwrite that speculative value here with the actual acquisition boundary.
    state["last_scan_attempt"] = started
    return started


def _process_scan_start() -> datetime | None:
    with _PROCESS_CADENCE_LOCK:
        return _PROCESS_LAST_SCAN_START


def _sync_process_scan_start(state: MutableMapping[str, Any]) -> datetime | None:
    """Make every observing session use the actual process scan-start baseline."""
    started = _process_scan_start()
    if started is not None:
        state["last_scan_attempt"] = started
    return started


def _clear_passive_autoscan_request(state: MutableMapping[str, Any]) -> None:
    """Clear scheduler-owned work only; preserve explicit manual requests."""
    from .session_controls import SCAN_REQUESTED_AT_KEY, SCAN_REQUESTED_KEY

    if bool(state.get(SCAN_REQUESTED_KEY, False)) and state.get(
        SCAN_REQUESTED_AT_KEY
    ) is None:
        state[SCAN_REQUESTED_KEY] = False


def scheduler_scan_projection(
    scan,
    state: MutableMapping[str, Any],
    view: str,
    *,
    process_scan_running: bool | None = None,
    now: datetime | None = None,
    now_monotonic: float | None = None,
):
    """Keep passive sessions out of app.py's legacy completion-time fallback.

    app.py still contains a defensive fallback that asks whether the last completed
    scan is older than refresh_seconds.  That fallback is useful to the cadence
    owner, but a passive Streamlit session must not interpret it as independent
    permission to scan.  For the scheduler view only, return a detached timestamp
    projection whose age is zero.  The real CompletedScan is never mutated and all
    trader-facing views continue to receive its true completion timestamp.
    """
    if scan is None or str(view) != "scheduler" or getattr(scan, "provider", None) is None:
        return scan
    if cadence_owner_allows(
        state,
        process_scan_running=process_scan_running,
        now_monotonic=now_monotonic,
    ):
        return scan

    _clear_passive_autoscan_request(state)
    try:
        projected = copy.copy(scan)
        object.__setattr__(projected, "completed_at", now or _now_local())
        return projected
    except Exception:
        # The projection is a secondary guard. The process watchdog still prevents
        # overlap if an unexpected object cannot be copied.
        return scan


def _inherit_gs_markers(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Install after GS411 at the existing GS410 safe late-runtime boundary."""
    from . import completed_scan, session_controls, watchdog

    current_initialize = session_controls.initialize_session_controls
    if not getattr(current_initialize, "_gs413_single_process_autoscan_authority", False):
        def initialize_with_process_authority(
            state,
            *,
            default_mode: str,
            scan_running: bool | None = None,
        ) -> None:
            current_initialize(
                state,
                default_mode=default_mode,
                scan_running=scan_running,
            )
            _sync_process_scan_start(state)
            if passive_cadence_session(
                state,
                process_scan_running=scan_running,
            ):
                _clear_passive_autoscan_request(state)

        _inherit_gs_markers(initialize_with_process_authority, current_initialize)
        initialize_with_process_authority._gs413_single_process_autoscan_authority = True
        initialize_with_process_authority._gs413_original = current_initialize
        session_controls.initialize_session_controls = initialize_with_process_authority

    current_wait = session_controls.autoscan_wait_seconds
    if not getattr(current_wait, "_gs413_single_process_autoscan_authority", False):
        def wait_with_process_authority(
            refresh_seconds: int,
            last_updated: datetime | None,
            last_scan_attempt: datetime | None,
            *,
            retry_seconds: int = 5,
            now: datetime | None = None,
        ) -> int:
            state = _session_state()
            effective_attempt = last_scan_attempt
            if state is not None:
                process_start = _sync_process_scan_start(state)
                if process_start is not None:
                    effective_attempt = process_start
                if not cadence_owner_allows(state):
                    return min(
                        max(1, int(refresh_seconds)),
                        PASSIVE_POLL_SECONDS,
                    )
            return current_wait(
                refresh_seconds,
                last_updated,
                effective_attempt,
                retry_seconds=retry_seconds,
                now=now,
            )

        _inherit_gs_markers(wait_with_process_authority, current_wait)
        wait_with_process_authority._gs413_single_process_autoscan_authority = True
        wait_with_process_authority._gs413_original = current_wait
        session_controls.autoscan_wait_seconds = wait_with_process_authority

    # GS411 already wraps this callable. GS413 stays outside it so passive sessions
    # are rejected before GS411 records a false scheduler-due observation.
    current_due = session_controls.autoscan_request_due
    if not getattr(current_due, "_gs413_single_process_autoscan_authority", False):
        def due_with_process_authority(
            refresh_seconds: int,
            last_updated: datetime | None,
            last_scan_attempt: datetime | None,
            *,
            retry_seconds: int = 5,
            now: datetime | None = None,
        ) -> bool:
            state = _session_state()
            effective_attempt = last_scan_attempt
            if state is not None:
                process_start = _sync_process_scan_start(state)
                if process_start is not None:
                    effective_attempt = process_start
                if not cadence_owner_allows(state):
                    _clear_passive_autoscan_request(state)
                    return False
            return current_due(
                refresh_seconds,
                last_updated,
                effective_attempt,
                retry_seconds=retry_seconds,
                now=now,
            )

        _inherit_gs_markers(due_with_process_authority, current_due)
        due_with_process_authority._gs413_single_process_autoscan_authority = True
        due_with_process_authority._gs413_original = current_due
        session_controls.autoscan_request_due = due_with_process_authority

    # GS411's begin wrapper is intentionally inside this boundary. Setting the
    # actual process start first makes its Flight Recorder timing truth observe the
    # same baseline that GS413 gives to every session.
    current_begin = session_controls.begin_scheduled_scan
    if not getattr(current_begin, "_gs413_single_process_autoscan_authority", False):
        def begin_with_process_authority(state) -> None:
            manual = state.get(session_controls.SCAN_REQUESTED_AT_KEY) is not None
            _record_actual_scan_start(state, automatic=not manual)
            return current_begin(state)

        _inherit_gs_markers(begin_with_process_authority, current_begin)
        begin_with_process_authority._gs413_single_process_autoscan_authority = True
        begin_with_process_authority._gs413_original = current_begin
        session_controls.begin_scheduled_scan = begin_with_process_authority

    current_view = completed_scan.completed_scan_for_view
    if not getattr(current_view, "_gs413_single_process_autoscan_authority", False):
        def completed_scan_with_process_authority(state, view):
            scan = current_view(state, view)
            if scan is not None and getattr(scan, "provider", None) is not None:
                _sync_process_scan_start(state)
            return scheduler_scan_projection(
                scan,
                state,
                str(view),
                process_scan_running=_process_scan_running(),
            )

        _inherit_gs_markers(completed_scan_with_process_authority, current_view)
        completed_scan_with_process_authority._gs413_single_process_autoscan_authority = True
        completed_scan_with_process_authority._gs413_original = current_view
        completed_scan.completed_scan_for_view = completed_scan_with_process_authority

    # Final safety belt: if a manual request or a deployment-boundary race still
    # loses the watchdog, erase only a scheduler-owned request and repair the local
    # speculative app.py timestamp to the actual process baseline.
    process_watchdog = watchdog.PROCESS_SCAN_WATCHDOG
    current_run = process_watchdog.run
    if not getattr(current_run, "_gs413_single_process_autoscan_authority", False):
        def run_with_process_authority(*args, **kwargs):
            try:
                return current_run(*args, **kwargs)
            except watchdog.ScanAlreadyRunning:
                state = _session_state()
                if state is not None:
                    _sync_process_scan_start(state)
                    _clear_passive_autoscan_request(state)
                raise

        run_with_process_authority._gs413_single_process_autoscan_authority = True
        run_with_process_authority._gs413_original = current_run
        process_watchdog.run = run_with_process_authority


def _reset_process_authority_for_tests() -> None:
    """Reset only GS413 globals for deterministic regression tests."""
    global _PROCESS_CADENCE_OWNER, _PROCESS_CADENCE_HEARTBEAT
    global _PROCESS_LAST_SCAN_START
    with _PROCESS_CADENCE_LOCK:
        _PROCESS_CADENCE_OWNER = None
        _PROCESS_CADENCE_HEARTBEAT = 0.0
        _PROCESS_LAST_SCAN_START = None
