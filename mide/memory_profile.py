"""Bounded, dependency-free memory diagnostics for the Streamlit process."""

from __future__ import annotations

from collections import Counter, deque
from datetime import datetime, timezone
import gc
import json
from pathlib import Path
import sys
import tracemalloc
from typing import Any, Mapping

from mide.startup_memory import resident_memory_bytes


PROFILE_PATH = Path("data/memory_profile.json")
_scan_rss: deque[int] = deque(maxlen=5)


def start() -> None:
    """Start allocation tracing once, retaining only one traceback frame."""
    if not tracemalloc.is_tracing():
        tracemalloc.start(1)


def deep_size(value: Any) -> int:
    """Return retained Python size without counting shared objects twice."""
    seen: set[int] = set()
    stack = [value]
    total = 0
    while stack:
        item = stack.pop()
        identity = id(item)
        if identity in seen:
            continue
        seen.add(identity)
        total += sys.getsizeof(item, 0)
        if isinstance(item, dict):
            stack.extend(item.keys())
            stack.extend(item.values())
        elif isinstance(item, (list, tuple, set, frozenset, deque)):
            stack.extend(item)
    return total


def object_counts(limit: int = 20) -> list[dict[str, int | str]]:
    counts = Counter(type(item).__name__ for item in gc.get_objects())
    return [{"type": name, "count": count} for name, count in counts.most_common(limit)]


def profile(label: str, *, session_state: Mapping[str, Any] | None = None,
            structures: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Write a bounded report containing the requested operational diagnostics."""
    start()
    snapshot = tracemalloc.take_snapshot()
    allocations = [
        {"location": str(stat.traceback[0]), "bytes": stat.size, "count": stat.count}
        for stat in snapshot.statistics("lineno")[:20]
    ]
    named = dict(structures or {})
    if session_state is not None:
        named["session_state"] = session_state
    largest = sorted(
        ({"name": name, "bytes": deep_size(value), "type": type(value).__name__}
         for name, value in named.items()),
        key=lambda item: item["bytes"], reverse=True,
    )[:20]
    session_sizes = sorted(
        ({"key": str(key), "bytes": deep_size(value), "type": type(value).__name__}
         for key, value in (session_state or {}).items()),
        key=lambda item: item["bytes"], reverse=True,
    )[:20]
    rss = resident_memory_bytes()
    if label.startswith("scan"):
        _scan_rss.append(rss)
    report = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "rss_bytes": rss,
        "top_20_memory_consumers": allocations,
        "object_counts": object_counts(),
        "largest_data_structures": largest,
        "cache_sizes": {
            "session_cache_bytes": sum(
                deep_size(value) for key, value in (session_state or {}).items()
                if "cache" in str(key).lower()
            ),
            "scan_rss_samples": len(_scan_rss),
            "scan_rss_bytes": list(_scan_rss),
        },
        "session_state": {"bytes": deep_size(session_state or {}), "largest_keys": session_sizes},
        "five_scan_stable": (
            len(_scan_rss) == 5 and max(_scan_rss) - min(_scan_rss) <= 16 * 1024 * 1024
        ),
    }
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        document = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        document = {}
    document[label] = report
    PROFILE_PATH.write_text(json.dumps(document, indent=2), encoding="utf-8")
    del snapshot
    if label.startswith("scan"):
        # Allocation traces are themselves sizeable. A scan report is complete, so
        # do not retain profiler bookkeeping throughout the rest of the session.
        tracemalloc.stop()
    return report


def release_temporaries(*values: Any) -> None:
    """Drop caller-owned temporary containers after it clears its references."""
    # Accepting the values makes cleanup intent explicit; clearing mutable containers
    # releases their element references before the next cyclic collection.
    for value in values:
        if isinstance(value, (dict, list, set)):
            value.clear()
    gc.collect()


PREVIOUS_RECORD_COLUMNS = frozenset({
    "symbol", "status", "candidate_status", "recommendation", "final_decision",
    "current_momentum", "opportunity_score", "scanner_v2_score", "conviction_score",
    "conviction_v2_score", "participation_surge_score", "participation_score",
    "expansion_quality", "dollar_flow_score", "market_dominance_score",
    "vwap_distance_pct", "volume_acceleration", "rvol_proxy", "rvol",
    "qualified_for_ranking", "participation_gate", "structure_gate", "trigger_diagnostics",
})


def compact_previous_record(record: Mapping[str, Any] | None) -> dict[str, Any]:
    """Keep only fields consumed by display comparisons, not a duplicate scan row."""
    return {key: record[key] for key in PREVIOUS_RECORD_COLUMNS if record and key in record}
