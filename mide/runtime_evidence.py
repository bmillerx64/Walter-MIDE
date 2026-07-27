"""Safe, read-only exports of Walter's persisted runtime evidence."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

SENSITIVE_FRAGMENTS = ("api_key", "secret", "authorization", "auth_header", "account")


def _safe(value: Any) -> Any:
    """Recursively remove credential-like keys from an export payload."""
    if isinstance(value, dict):
        return {
            key: _safe(item)
            for key, item in value.items()
            if not any(fragment in str(key).lower() for fragment in SENSITIVE_FRAGMENTS)
        }
    if isinstance(value, list):
        return [_safe(item) for item in value]
    return value


def json_bytes(value: Any) -> bytes:
    return json.dumps(_safe(value), indent=2, default=str, sort_keys=True).encode()


def runtime_file(path: str | Path) -> tuple[bytes | None, str]:
    path = Path(path)
    if not path.is_file():
        return None, f"Runtime file is absent: {path.as_posix()}"
    # Re-serialize JSONL so historical files cannot accidentally expose secrets.
    clean_lines = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            clean_lines.append(json.dumps(_safe(json.loads(line)), default=str))
        except (ValueError, TypeError):
            continue
    return ("\n".join(clean_lines) + ("\n" if clean_lines else "")).encode(), ""


def read_scans(path: str | Path) -> list[dict]:
    data, _ = runtime_file(path)
    if not data:
        return []
    scans = []
    for line in data.decode().splitlines():
        try:
            scans.append(json.loads(line))
        except ValueError:
            continue
    return sorted(scans, key=lambda scan: scan.get("timestamp", ""))


def current_scan_export(scan: dict | None) -> dict:
    if not scan:
        return {"scan_id": None, "scan_timestamp": None, "records": []}
    return _safe(
        {
            "scan_id": scan.get("scan_id"),
            "scan_timestamp": scan.get("timestamp"),
            "records": [path.get("evidence", {}) for path in scan.get("symbols", [])],
        }
    )


def symbol_history(scans: list[dict], symbol: str) -> list[dict]:
    """Return every scan chronologically, explicitly marking disappearances."""
    symbol = symbol.strip().upper()
    history = []
    seen = False
    previous_state = None
    milestones: set[str] = set()
    for scan in scans:
        path = next(
            (item for item in scan.get("symbols", []) if item.get("symbol") == symbol),
            None,
        )
        if path is None:
            if seen:
                history.append(
                    {
                        "symbol": symbol,
                        "scan_timestamp": scan.get("timestamp"),
                        "scan_id": scan.get("scan_id"),
                        "event": "disappearance",
                        "disappeared": True,
                        "previous_workflow_state": previous_state,
                    }
                )
            continue
        evidence = dict(path.get("evidence") or {})
        state = evidence.get("workflow_state")
        events = path.get("events") or []
        evidence.update(
            {
                "scan_id": scan.get("scan_id"),
                "scan_timestamp": scan.get("timestamp"),
                "first_discovery": not seen,
                "first_prefilter_pass": evidence.get("snapshot_prefilter_result")
                is True
                and "prefilter" not in milestones,
                "first_watch_list_appearance": state in {"Watching", "Watch List"}
                and not ({"Watching", "Watch List"} & milestones),
                "first_strengthening_appearance": state == "Strengthening"
                and "Strengthening" not in milestones,
                "first_entry_ready_appearance": state == "Entry Ready"
                and "Entry Ready" not in milestones,
                "transition": (
                    f"{previous_state} -> {state}"
                    if previous_state is not None and state != previous_state
                    else None
                ),
                "disappeared": False,
                "first_failed_rule": next(
                    (
                        event.get("reason")
                        for event in events
                        if not event.get("passed")
                    ),
                    None,
                ),
            }
        )
        history.append(_safe(evidence))
        seen = True
        if evidence.get("snapshot_prefilter_result") is True:
            milestones.add("prefilter")
        if state:
            milestones.add(state)
            previous_state = state
    return history


def symbol_summary(history: list[dict], symbol: str) -> dict | None:
    present = [item for item in history if not item.get("disappeared")]
    if not present:
        return None
    states = {item.get("workflow_state") for item in present}
    latest = present[-1]
    return {
        "symbol": symbol.strip().upper(),
        "first_recorded_timestamp": present[0].get("scan_timestamp"),
        "last_recorded_timestamp": present[-1].get("scan_timestamp"),
        "scans_retained": len(present),
        "latest_workflow_state": latest.get("workflow_state"),
        "latest_rejection_or_blocker": latest.get("latest_rejection_or_blocker"),
        "ever_reached": {
            "Candidate": bool(present),
            "Watch": bool(states & {"Watching", "Watch List"}),
            "Strengthening": "Strengthening" in states,
            "Entry Ready": "Entry Ready" in states,
        },
    }
