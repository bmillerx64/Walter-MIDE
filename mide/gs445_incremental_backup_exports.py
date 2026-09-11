"""GS445: remove growing backup recompression from the pre-scan rerun path.

Live Flight Recorder validation on 2026-09-11 isolated a repeatable cadence defect:
Walter's scheduler recognized a 60-second deadline promptly, but the next scan attempt
was increasingly delayed after that observation. The delay grew from roughly 1-2
seconds early in the session to 13-14 seconds after several hours.

The cause is operational, not trading logic. ``app.py`` renders the Candidate History
download before it reaches the scan-dispatch boundary. GS364 correctly compresses large
JSONL backups, but its cache is keyed to exact file size/mtime. Candidate History is
append-only and changes after every scan, so the next full-app rerun recompressed the
*entire growing file* before Walter could stamp the new scan attempt.

GS445 preserves GS364's public export contract while making large append-only exports
incremental. The compressor state and already-produced gzip prefix are retained by file
identity. On the next export only newly appended bytes are read/compressed; a copied
compressor state is finalized to produce an exact standalone gzip payload for the
browser download. File replacement, truncation, or same-size mutation safely rebuilds
from byte zero. Small files keep the established raw-bytes contract.

This changes export materialization only. It does not alter scheduler deadlines,
watchdog ownership, provider requests, market-data values, discovery, VWAP, SuperTrend,
participation, expansion, scoring, ranking, qualification, alerts/audio, execution, or
orders.
"""
from __future__ import annotations

from pathlib import Path
import threading
import zlib
from typing import Any


AUTHORITY = "EXPORT_MATERIALIZATION_ONLY"
_CHUNK_BYTES = 1024 * 1024
_CACHE_LOCK = threading.RLock()
_CACHE: dict[str, dict[str, Any]] = {}
_STATS: dict[str, dict[str, Any]] = {}
_INSTALL_GENERATION = object()


def _identity(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return int(getattr(stat, "st_dev", 0)), int(getattr(stat, "st_ino", 0))


def _cache_key(path: Path) -> str:
    return str(path.resolve())


def _new_compressor():
    # wbits=31 emits the standard gzip wrapper expected by GS364/download metadata.
    return zlib.compressobj(level=5, method=zlib.DEFLATED, wbits=31)


def _snapshot(prefix: bytes, compressor) -> bytes:
    """Finalize a copy so the live compressor remains appendable for the next scan."""
    clone = compressor.copy()
    return prefix + clone.flush(zlib.Z_FINISH)


def _read_range(path: Path, start: int, stop: int, compressor) -> tuple[bytes, int]:
    """Compress exactly [start, stop), ignoring bytes appended after the opening stat."""
    produced = bytearray()
    remaining = max(0, int(stop) - int(start))
    if remaining <= 0:
        return b"", 0
    read_bytes = 0
    with path.open("rb") as handle:
        handle.seek(start)
        while remaining > 0:
            chunk = handle.read(min(_CHUNK_BYTES, remaining))
            if not chunk:
                break
            read_bytes += len(chunk)
            remaining -= len(chunk)
            encoded = compressor.compress(chunk)
            if encoded:
                produced.extend(encoded)
    # Z_SYNC_FLUSH emits the current incremental boundary while preserving the
    # compressor dictionary/state so later appends continue the same gzip member.
    produced.extend(compressor.flush(zlib.Z_SYNC_FLUSH))
    return bytes(produced), read_bytes


def _record_stat(path: Path, **values: Any) -> None:
    key = _cache_key(path)
    prior = dict(_STATS.get(key, {}))
    prior.update(values)
    prior.setdefault("authority", AUTHORITY)
    prior.setdefault("trading_logic_changed", False)
    _STATS[key] = prior


def export_observation(path: Path) -> dict[str, Any]:
    """Return a copy of GS445 export diagnostics for tests/live instrumentation."""
    with _CACHE_LOCK:
        return dict(_STATS.get(_cache_key(Path(path)), {}))


def reset_state() -> None:
    """Test/deploy helper: drop only GS445's in-process compression state."""
    with _CACHE_LOCK:
        _CACHE.clear()
        _STATS.clear()


def incremental_gzip_export(path: Path) -> bytes:
    """Return an exact raw/small or gzip/large snapshot with append-only O(delta) work."""
    from . import gs364_live_operator_containment as gs364

    path = Path(path)
    if not path.exists():
        return b""

    stat = path.stat()
    threshold = int(gs364.LARGE_EXPORT_BYTES)
    key = _cache_key(path)

    # Preserve GS364's small-file compatibility exactly. Also discard any prior large
    # stream state if a file was rotated/truncated below the compression threshold.
    if stat.st_size < threshold:
        with _CACHE_LOCK:
            _CACHE.pop(key, None)
            _record_stat(
                path,
                mode="raw_small",
                source_size=int(stat.st_size),
                bytes_read_this_call=int(stat.st_size),
            )
        return path.read_bytes()

    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        identity = _identity(path)
        rebuild = bool(
            cached is None
            or cached.get("identity") != identity
            or int(cached.get("offset", 0)) > int(stat.st_size)
            or (
                int(cached.get("offset", 0)) == int(stat.st_size)
                and int(cached.get("mtime_ns", -1)) != int(stat.st_mtime_ns)
            )
        )

        if rebuild:
            compressor = _new_compressor()
            prefix, read_bytes = _read_range(path, 0, int(stat.st_size), compressor)
            payload = _snapshot(prefix, compressor)
            prior_rebuilds = int((_STATS.get(key) or {}).get("rebuild_count", 0))
            prior_extends = int((_STATS.get(key) or {}).get("extend_count", 0))
            _CACHE[key] = {
                "identity": identity,
                "offset": int(stat.st_size),
                "mtime_ns": int(stat.st_mtime_ns),
                "compressor": compressor,
                "prefix": prefix,
                "payload": payload,
            }
            _record_stat(
                path,
                mode="rebuild",
                source_size=int(stat.st_size),
                bytes_read_this_call=read_bytes,
                rebuild_count=prior_rebuilds + 1,
                extend_count=prior_extends,
                compressed_size=len(payload),
            )
            return payload

        offset = int(cached.get("offset", 0))
        if int(stat.st_size) == offset:
            payload = bytes(cached["payload"])
            _record_stat(
                path,
                mode="cache_hit",
                source_size=int(stat.st_size),
                bytes_read_this_call=0,
                compressed_size=len(payload),
            )
            return payload

        compressor = cached["compressor"]
        prefix = bytes(cached["prefix"])
        appended, read_bytes = _read_range(
            path, offset, int(stat.st_size), compressor
        )
        prefix += appended
        payload = _snapshot(prefix, compressor)
        cached.update(
            {
                "identity": identity,
                "offset": int(stat.st_size),
                "mtime_ns": int(stat.st_mtime_ns),
                "compressor": compressor,
                "prefix": prefix,
                "payload": payload,
            }
        )
        _record_stat(
            path,
            mode="extend",
            source_size=int(stat.st_size),
            bytes_read_this_call=read_bytes,
            rebuild_count=int((_STATS.get(key) or {}).get("rebuild_count", 0)),
            extend_count=int((_STATS.get(key) or {}).get("extend_count", 0)) + 1,
            compressed_size=len(payload),
        )
        return payload


def install() -> None:
    """Replace only GS364's large-backup materializer; its wrappers stay authoritative."""
    from . import gs364_live_operator_containment as gs364
    from .flight_recorder import FlightRecorder
    from .memory import MemoryStore

    current = gs364._gzip_export
    if getattr(current, "_gs445_install_generation", None) is _INSTALL_GENERATION:
        return

    if not getattr(MemoryStore.export_bytes, "_gs364_compressed_export", False):
        raise RuntimeError("GS445 requires GS364 MemoryStore export containment")
    if not getattr(FlightRecorder.export_bytes, "_gs364_compressed_export", False):
        raise RuntimeError("GS445 requires GS364 FlightRecorder export containment")

    def incremental_export(path: Path) -> bytes:
        return incremental_gzip_export(Path(path))

    for name, value in getattr(current, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(incremental_export, name):
            setattr(incremental_export, name, value)
    incremental_export._gs445_incremental_backup_exports = True
    incremental_export._gs445_install_generation = _INSTALL_GENERATION
    incremental_export._gs445_original = current
    gs364._gzip_export = incremental_export
