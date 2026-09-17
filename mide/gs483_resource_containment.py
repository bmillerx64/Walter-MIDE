"""GS483: bound Flight Recorder read-side memory without changing evidence.

FR #84/#85 showed the append-only recorder had grown large enough that ordinary
``latest_scan()`` calls could transiently materialize the entire JSONL file plus a
split-lines copy on every Streamlit rerun.  The recorder is diagnostic-only, so
read-side containment can be isolated from all scanner/trading semantics.

GS483 replaces only FlightRecorder read helpers:
* ``latest_scan`` reads backwards in bounded chunks until it finds one valid JSON row;
* ``scans`` streams one JSONL row at a time instead of ``read_text().splitlines()``;
* ``history_for_symbol`` streams the file directly and never materializes every scan.

The on-disk JSONL schema, append behavior, download bytes, replay evidence, market
data, discovery, indicators, scoring, ranking, qualification, alerts, execution and
orders are unchanged.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator


AUTHORITY = "RESOURCE_CONTAINMENT_ONLY"
TAIL_CHUNK_BYTES = 64 * 1024
_INSTALL_GENERATION = object()


def _decode_json_line(raw: bytes):
    raw = raw.strip()
    if not raw:
        return None
    try:
        value = json.loads(raw.decode("utf-8", errors="ignore"))
    except (UnicodeError, ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def _iter_valid_scans(path: Path) -> Iterator[dict]:
    """Stream valid JSONL records without materializing the whole file."""
    if not path.exists():
        return
    with path.open("rb") as handle:
        for raw in handle:
            value = _decode_json_line(raw)
            if value is not None:
                yield value


def bounded_latest_scan(path: Path, *, chunk_bytes: int = TAIL_CHUNK_BYTES) -> dict | None:
    """Return the newest valid JSONL object using bounded reverse reads."""
    if not path.exists():
        return None
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if size <= 0:
        return None

    chunk_bytes = max(1024, int(chunk_bytes))
    with path.open("rb") as handle:
        position = size
        carry = b""
        while position > 0:
            take = min(chunk_bytes, position)
            position -= take
            handle.seek(position)
            block = handle.read(take) + carry
            parts = block.split(b"\n")
            if position > 0:
                carry = parts.pop(0) if parts else block
            else:
                carry = b""
            for raw in reversed(parts):
                value = _decode_json_line(raw)
                if value is not None:
                    return value
        if carry:
            return _decode_json_line(carry)
    return None


def streaming_scans(path: Path) -> list[dict]:
    """Preserve the historical list contract with lower transient memory."""
    return list(_iter_valid_scans(path))


def streaming_symbol_history(path: Path, symbol: str) -> list[dict]:
    """Return one symbol's trace without first building a full scan list."""
    wanted = str(symbol or "").strip().upper()
    if not wanted:
        return []
    history: list[dict] = []
    for scan in _iter_valid_scans(path):
        symbol_path = next(
            (
                item
                for item in scan.get("symbols", [])
                if str(item.get("symbol", "")).upper() == wanted
            ),
            None,
        )
        if symbol_path:
            history.append(
                {
                    "scan_id": scan.get("scan_id"),
                    "timestamp": scan.get("timestamp"),
                    "scanner_version": scan.get("scanner_version"),
                    **symbol_path,
                }
            )
    return history


def resource_snapshot(recorder) -> dict:
    """Small diagnostics payload; never reads recorder contents."""
    path = Path(recorder.path)
    try:
        file_bytes = int(path.stat().st_size) if path.exists() else 0
    except OSError:
        file_bytes = 0
    rss_mb = None
    try:
        import resource

        raw = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        # Linux reports KiB; macOS reports bytes. Walter production is Linux.
        rss_mb = round(raw / 1024.0, 1) if raw < 10_000_000 else round(raw / (1024.0 * 1024.0), 1)
    except Exception:
        pass
    return {
        "authority": AUTHORITY,
        "flight_recorder_bytes": file_bytes,
        "flight_recorder_mb": round(file_bytes / (1024.0 * 1024.0), 2),
        "process_max_rss_mb": rss_mb,
        "trading_logic_changed": False,
    }


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    from .flight_recorder import FlightRecorder

    current_latest = FlightRecorder.latest_scan
    if getattr(current_latest, "_gs483_install_generation", None) is not _INSTALL_GENERATION:
        def latest_scan(self):
            return bounded_latest_scan(Path(self.path))

        _inherit(latest_scan, current_latest)
        latest_scan._gs483_resource_containment = True
        latest_scan._gs483_install_generation = _INSTALL_GENERATION
        latest_scan._gs483_original = current_latest
        FlightRecorder.latest_scan = latest_scan

    current_scans = FlightRecorder.scans
    if getattr(current_scans, "_gs483_install_generation", None) is not _INSTALL_GENERATION:
        def scans(self):
            return streaming_scans(Path(self.path))

        _inherit(scans, current_scans)
        scans._gs483_resource_containment = True
        scans._gs483_install_generation = _INSTALL_GENERATION
        scans._gs483_original = current_scans
        FlightRecorder.scans = scans

    current_history = FlightRecorder.history_for_symbol
    if getattr(current_history, "_gs483_install_generation", None) is not _INSTALL_GENERATION:
        def history_for_symbol(self, symbol: str):
            return streaming_symbol_history(Path(self.path), symbol)

        _inherit(history_for_symbol, current_history)
        history_for_symbol._gs483_resource_containment = True
        history_for_symbol._gs483_install_generation = _INSTALL_GENERATION
        history_for_symbol._gs483_original = current_history
        FlightRecorder.history_for_symbol = history_for_symbol
