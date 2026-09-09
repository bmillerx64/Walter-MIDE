"""GS408: keep the last completed trading view visible while the next scan runs.

Live validation on 2026-09-09 exposed a presentation gap in Walter's blocking
Streamlit rerun. app.py reserves the mission-control trading surface with seven
``st.empty()`` placeholders before it enters the live scan. On an autoscan rerun
those eager empty deltas clear the prior completed scan immediately, so an operator
who returns mid-scan can lose the LOOK NOW / Opportunity State context until the
new scan finishes.

GS408 makes only those named top-level dashboard placeholders lazy. The placeholder
is not emitted until app.py actually renders the newly completed view. During the
blocking scan Streamlit therefore leaves the prior completed dashboard mounted.
All unrelated ``st.empty`` calls retain native behavior.

Presentation lifecycle only. No changes to scan cadence, discovery, Webull data,
VWAP, SuperTrend, participation, ranking, qualification, readiness, alert truth,
audio, execution, or orders.
"""
from __future__ import annotations

from functools import wraps
import inspect
import linecache
import re
from typing import Any, Callable


DASHBOARD_SLOT_NAMES = frozenset(
    {
        "mission_header_slot",
        "scan_trust_slot",
        "market_session_slot",
        "early_setup_slot",
        "mission_plan_slot",
        "opportunity_feed_slot",
        "escalation_engine_slot",
    }
)

_SLOT_ASSIGNMENT = re.compile(
    r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*st\.empty\(\s*\)\s*$"
)


def dashboard_slot_name(filename: str, source_line: str) -> str | None:
    """Return a GS408 slot name only for the exact app.py placeholder assignment."""
    normalized = str(filename or "").replace("\\", "/")
    if not normalized.endswith("/app.py") and normalized != "app.py":
        return None
    match = _SLOT_ASSIGNMENT.match(str(source_line or ""))
    if not match:
        return None
    name = match.group("name")
    return name if name in DASHBOARD_SLOT_NAMES else None


def _dashboard_slot_name_from_callsite() -> str | None:
    """Inspect only the direct ``st.empty`` caller; never infer by call count."""
    frame = inspect.currentframe()
    try:
        caller = frame.f_back.f_back if frame and frame.f_back else None
        if caller is None:
            return None
        filename = str(caller.f_code.co_filename or "")
        source_line = linecache.getline(filename, caller.f_lineno)
        return dashboard_slot_name(filename, source_line)
    finally:
        del frame


class LazyEmptySlot:
    """Delay one native Streamlit placeholder until it is first actually used."""

    def __init__(self, factory: Callable[[], Any], slot_name: str):
        self._factory = factory
        self._slot_name = slot_name
        self._resolved = None

    @property
    def resolved(self) -> bool:
        return self._resolved is not None

    def _resolve(self):
        if self._resolved is None:
            self._resolved = self._factory()
        return self._resolved

    def __enter__(self):
        return self._resolve().__enter__()

    def __exit__(self, exc_type, exc, tb):
        return self._resolve().__exit__(exc_type, exc, tb)

    def __getattr__(self, name: str):
        return getattr(self._resolve(), name)


def install(st_module=None) -> None:
    """Defer only Walter's seven top-level trading-surface placeholders."""
    if st_module is None:
        import streamlit as st_module  # type: ignore[no-redef]

    current_empty = st_module.empty
    if getattr(current_empty, "_gs408_preserve_completed_scan", False):
        return

    @wraps(current_empty)
    def sticky_completed_scan_empty(*args, **kwargs):
        # Native ``st.empty`` accepts no meaningful call-site identity, so use the
        # exact app.py assignment text rather than brittle invocation counting.
        if not args and not kwargs:
            slot_name = _dashboard_slot_name_from_callsite()
            if slot_name:
                return LazyEmptySlot(current_empty, slot_name)
        return current_empty(*args, **kwargs)

    sticky_completed_scan_empty._gs408_preserve_completed_scan = True
    sticky_completed_scan_empty._gs408_original = current_empty
    st_module.empty = sticky_completed_scan_empty
