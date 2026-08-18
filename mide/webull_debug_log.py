"""Hidden debug logging for raw Webull indicator/snapshot payloads.

Captures the last N raw Webull API responses in a JSONL ring-buffer file so
intermittent 10 % failures can be diagnosed after the fact.  A companion
Streamlit view is gated behind the ``?debug=1`` query parameter; normal users
never see it.

Usage
-----
Enable the hidden debug page by appending ``?debug=1`` to the app URL, e.g.
``https://<your-app>.streamlit.app/?debug=1``.  The **Webull Debug** tab will
appear at the right end of the tab bar.  All output is read-only; no scan or
provider state is modified.

Credential safety
-----------------
Any dict key whose name contains ``key``, ``secret``, ``token``, ``password``,
``auth``, or ``credential`` (case-insensitive) is replaced with ``"[REDACTED]"``
before the entry is written or displayed.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Maximum number of entries kept in the ring-buffer log file.
MAX_LOG_ENTRIES: int = 50

# Default path for the on-disk JSONL ring buffer.
DEFAULT_LOG_PATH: Path = Path("webull_debug_log.jsonl")

_REDACT_PATTERN = re.compile(
    r"(?:key|secret|token|password|auth|credential)",
    re.IGNORECASE,
)

_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Credential redaction
# ---------------------------------------------------------------------------

def _redact(value: Any, depth: int = 0) -> Any:
    """Recursively replace sensitive dict values with ``"[REDACTED]"``."""
    if depth > 20:
        return value
    if isinstance(value, dict):
        return {
            k: "[REDACTED]" if _REDACT_PATTERN.search(str(k)) else _redact(v, depth + 1)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(item, depth + 1) for item in value]
    return value


# ---------------------------------------------------------------------------
# Ring-buffer helpers
# ---------------------------------------------------------------------------

def _read_entries(path: Path) -> list[dict]:
    """Read existing JSONL entries; skip any malformed lines."""
    entries: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return entries
    except OSError:
        return entries
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            if isinstance(entry, dict):
                entries.append(entry)
        except (json.JSONDecodeError, ValueError):
            # Malformed prior log entry — skip it silently.
            pass
    return entries


def _write_entries(path: Path, entries: list[dict]) -> None:
    """Overwrite *path* with *entries* serialised as JSONL."""
    lines = []
    for entry in entries:
        try:
            lines.append(json.dumps(entry, default=str))
        except (TypeError, ValueError):
            pass
    try:
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def append_entry(entry: dict, *, path: Path = DEFAULT_LOG_PATH) -> None:
    """Thread-safe append of *entry* to the JSONL ring buffer.

    The file is trimmed to ``MAX_LOG_ENTRIES`` after each write.
    """
    safe_entry = _redact(entry)
    with _lock:
        existing = _read_entries(path)
        existing.append(safe_entry)
        if len(existing) > MAX_LOG_ENTRIES:
            existing = existing[-MAX_LOG_ENTRIES:]
        _write_entries(path, existing)


def read_entries(*, path: Path = DEFAULT_LOG_PATH) -> list[dict]:
    """Return stored entries newest-first; never raises."""
    with _lock:
        entries = _read_entries(path)
    return list(reversed(entries))


def log_snapshot_attempt(
    *,
    symbols: list[str],
    raw_response: Any,
    normalized: dict | None,
    error: Exception | None,
    fetch_timestamp: str | None = None,
    path: Path = DEFAULT_LOG_PATH,
) -> None:
    """Record one snapshot attempt (success or failure) to the ring buffer.

    Parameters
    ----------
    symbols:
        Ticker symbols requested.
    raw_response:
        The raw value returned by the SDK before Walter normalises it.  Will be
        redacted before storage.
    normalized:
        Walter-normalised snapshot dict, or ``None`` when the call failed.
    error:
        Exception raised, or ``None`` on success.
    fetch_timestamp:
        ISO-8601 timestamp string; defaults to *now* when omitted.
    """
    ts = fetch_timestamp or datetime.now(timezone.utc).isoformat()
    passed = error is None and normalized is not None

    missing_fields: list[str] = []
    error_detail: str | None = None

    if not passed:
        error_detail = f"{type(error).__name__}: {error}" if error else "normalization returned None"
    elif normalized is not None:
        # Check for symbols that were requested but not returned.
        missing_symbols = [s for s in symbols if s not in (normalized or {})]
        if missing_symbols:
            missing_fields = [f"symbol not in response: {s}" for s in missing_symbols[:10]]

    entry: dict = {
        "endpoint": "snapshot",
        "fetch_timestamp": ts,
        "symbols_requested": symbols,
        "symbol_count": len(symbols),
        "validation_passed": passed,
        "symbols_returned": list((normalized or {}).keys()),
        "raw_response": _redact(raw_response),
        "error_detail": error_detail,
        "missing_fields": missing_fields,
        "using_fallback_cache": False,
    }
    append_entry(entry, path=path)


def log_bars_attempt(
    *,
    symbols: list[str],
    timeframe: str,
    raw_response: Any,
    output: dict | None,
    error: Exception | None,
    fetch_timestamp: str | None = None,
    path: Path = DEFAULT_LOG_PATH,
) -> None:
    """Record one bars/history attempt to the ring buffer."""
    ts = fetch_timestamp or datetime.now(timezone.utc).isoformat()
    passed = error is None and output is not None

    entry: dict = {
        "endpoint": "bars",
        "fetch_timestamp": ts,
        "symbols_requested": symbols,
        "symbol_count": len(symbols),
        "timeframe": timeframe,
        "validation_passed": passed,
        "symbols_returned": list((output or {}).keys()),
        "raw_response": _redact(raw_response),
        "error_detail": (f"{type(error).__name__}: {error}" if error else None),
        "missing_fields": [],
        "using_fallback_cache": False,
    }
    append_entry(entry, path=path)


def log_cache_fallback(
    *,
    symbols: list[str],
    endpoint: str,
    original_error: str,
    fetch_timestamp: str | None = None,
    path: Path = DEFAULT_LOG_PATH,
) -> None:
    """Record that a live call failed and the cache fallback was used."""
    ts = fetch_timestamp or datetime.now(timezone.utc).isoformat()
    entry: dict = {
        "endpoint": endpoint,
        "fetch_timestamp": ts,
        "symbols_requested": symbols,
        "symbol_count": len(symbols),
        "validation_passed": False,
        "symbols_returned": [],
        "raw_response": None,
        "error_detail": original_error,
        "missing_fields": [],
        "using_fallback_cache": True,
    }
    append_entry(entry, path=path)
