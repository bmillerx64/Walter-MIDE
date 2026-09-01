"""GS353: make Walter's entry contract explicit at the operator surface.

Presentation-only. This module does not change discovery, scoring, qualification,
readiness thresholds, alerts, execution, orders, or market-data logic. It reads
Walter's existing trigger/structure diagnostics and shows the exact remaining
locks for current developing setups.
"""
from __future__ import annotations

import html

LOCK_ORDER = (
    ("supertrend_flip", "ST FLIP"),
    ("vwap", "VWAP"),
    ("participation", "PARTICIPATION"),
    ("expansion_beginning", "EXPANSION"),
)


def _trigger(record: dict) -> dict:
    trigger = record.get("trigger_diagnostics")
    if isinstance(trigger, dict) and trigger.get("checks"):
        return trigger
    try:
        from .scanner_v2 import trigger_diagnostics
        return trigger_diagnostics(record)
    except Exception:
        return {"passed": False, "checks": [], "thresholds": {}}


def _structure_passed(record: dict) -> bool:
    structure = record.get("structure_gate") or {}
    return bool(structure.get("passed"))


def entry_lock_snapshot(record: dict) -> dict:
    """Return the existing four trigger locks without changing their meaning."""
    trigger = _trigger(record)
    checks = {
        str(check.get("condition") or ""): check
        for check in trigger.get("checks") or []
        if isinstance(check, dict)
    }
    locks = []
    for condition, label in LOCK_ORDER:
        check = checks.get(condition, {})
        locks.append(
            {
                "condition": condition,
                "label": label,
                "passed": bool(check.get("passed")),
                "passed_reason": str(check.get("passed_reason") or ""),
                "failed_reason": str(check.get("failed_reason") or ""),
            }
        )
    passed_count = sum(1 for lock in locks if lock["passed"])
    structure_passed = _structure_passed(record)
    entry_ready = bool(
        structure_passed
        and trigger.get("passed")
        and record.get("qualified_for_entry")
        and (record.get("candidate_status") or record.get("status")) == "Entry Ready"
    )
    armed = bool(not entry_ready and structure_passed and passed_count == len(locks) - 1)
    if entry_ready:
        state = "ENTRY READY"
    elif armed:
        state = "ARMED · ONE LOCK REMAINING"
    else:
        state = "DEVELOPING"
    return {
        "state": state,
        "locks": locks,
        "passed_count": passed_count,
        "total_locks": len(locks),
        "structure_passed": structure_passed,
        "trigger_passed": bool(trigger.get("passed")),
        "entry_ready": entry_ready,
        "armed": armed,
    }


def _compact_reason(lock: dict) -> str:
    text = lock.get("passed_reason") if lock.get("passed") else lock.get("failed_reason")
    text = str(text or "").strip()
    if not text:
        return "pass" if lock.get("passed") else "waiting"
    return text.replace(" (Below trigger threshold)", "").replace(" (Below trigger threshold of ", " (<")


def entry_locks_markup(record: dict) -> str:
    snapshot = entry_lock_snapshot(record)
    state = snapshot["state"]
    state_class = "ready" if snapshot["entry_ready"] else "armed" if snapshot["armed"] else "developing"
    chips = []
    for lock in snapshot["locks"]:
        passed = lock["passed"]
        chips.append(
            "<span class='gs353-chip " + ("pass" if passed else "fail") + "'>"
            + ("✓ " if passed else "○ ")
            + html.escape(lock["label"])
            + " · "
            + html.escape(_compact_reason(lock))
            + "</span>"
        )
    structure = (
        "<span class='gs353-structure pass'>✓ STRUCTURE</span>"
        if snapshot["structure_passed"]
        else "<span class='gs353-structure fail'>○ STRUCTURE</span>"
    )
    return (
        "<div class='gs353-locks'>"
        f"<span class='gs353-state {state_class}'>{html.escape(state)}</span>"
        + structure
        + "".join(chips)
        + "</div>"
    )


def _augment_developing_markup(markup: str, records: list[dict]) -> str:
    if not markup:
        return markup
    try:
        from .gs349_operator_first_layout import developing_records
        rows = developing_records(records)
    except Exception:
        rows = []
    if not rows:
        return markup
    blocks = []
    for record in rows:
        symbol = html.escape(str(record.get("symbol") or "").upper())
        blocks.append(
            "<div class='gs353-symbol-locks'>"
            f"<div class='gs353-symbol'>{symbol} ENTRY LOCKS</div>"
            + entry_locks_markup(record)
            + "</div>"
        )
    addition = (
        "<style>"
        ".gs353-symbol-locks{border-top:1px solid #1e293b;padding:7px 0 2px}"
        ".gs353-symbol{font-size:.68rem;letter-spacing:.09em;font-weight:900;color:#94a3b8;margin-bottom:4px}"
        ".gs353-locks{display:flex;gap:5px;align-items:center;flex-wrap:wrap}"
        ".gs353-state,.gs353-structure,.gs353-chip{font-size:.69rem;font-weight:850;border:1px solid #334155;border-radius:999px;padding:3px 7px;background:#0f172a}"
        ".gs353-state.developing{color:#93c5fd}.gs353-state.armed{color:#fbbf24;border-color:#92400e}.gs353-state.ready{color:#86efac;border-color:#166534}"
        ".gs353-chip.pass,.gs353-structure.pass{color:#86efac}.gs353-chip.fail,.gs353-structure.fail{color:#fca5a5}"
        "</style>"
        + "".join(blocks)
    )
    marker = "</div>"
    idx = markup.rfind(marker)
    if idx < 0:
        return markup + addition
    return markup[:idx] + addition + markup[idx:]


def install() -> None:
    """Augment GS349 DEVELOPING NOW with exact current entry locks."""
    from . import gs349_operator_first_layout as layout

    current = layout.developing_now_markup
    if getattr(current, "_gs353_entry_lock_clarity", False):
        return

    def developing_with_entry_locks(records: list[dict]) -> str:
        return _augment_developing_markup(current(records), records)

    developing_with_entry_locks._gs353_entry_lock_clarity = True
    developing_with_entry_locks._gs353_original = current
    layout.developing_now_markup = developing_with_entry_locks
