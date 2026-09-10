"""GS424: stop re-downloading the entire trading day on every warm scan.

Sep. 10 live validation after GS421-423 showed that Walter's convergence recorder was
no longer the dominant cost: warm scans still spent roughly 77 seconds inside the
same Stage-6 path that requests current-session 1-minute history for every candidate
on every scan.  The provider object survives Streamlit reruns, but that already-read
history was thrown away after each scan.

GS424 adds a provider-local current-session history cache for the two Stage-6 live
1-minute consumers (candidate analysis and relative-strength benchmarks). The first
request for a symbol/session remains the established full 04:00 ET seed. Subsequent
warm scans request only an overlap from the oldest cached last bar and merge the
returned delta into the immutable session history before analysis. New symbols still
receive a full seed. A new session anchor automatically clears the cache.

This changes acquisition efficiency only. It does not change discovery, snapshots,
bar values, VWAP anchoring, SuperTrend, participation/expansion, scoring, ranking,
qualification, alerts, execution, orders, or the GS421-423 observational contract.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import wraps
import math
from typing import Any, Callable, Iterable

from .webull_live import LiveWebullProvider


AUTHORITY = "ACQUISITION_OPTIMIZATION_ONLY"
INCREMENTAL_HISTORY_REASONS = frozenset(
    {"stage6_current_session", "stage6_benchmark"}
)
OVERLAP = timedelta(minutes=3)
_INSTALL_GENERATION = object()


def _utc_datetime(value: Any) -> datetime | None:
    """Normalize the timestamp forms returned by the Webull SDK."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)

    try:
        number = float(value)
    except (TypeError, ValueError):
        number = None
    if number is not None and math.isfinite(number):
        magnitude = abs(number)
        if magnitude >= 1e17:
            number /= 1e9
        elif magnitude >= 1e14:
            number /= 1e6
        elif magnitude >= 1e11:
            number /= 1e3
        try:
            return datetime.fromtimestamp(number, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _row_time(row: dict) -> datetime | None:
    return _utc_datetime(row.get("t") or row.get("timestamp") or row.get("time"))


def _latest_row_time(rows: Iterable[dict]) -> datetime | None:
    values = [stamp for stamp in (_row_time(row) for row in rows or []) if stamp is not None]
    return max(values) if values else None


def _merge_rows(previous: Iterable[dict], delta: Iterable[dict], limit: int) -> list[dict]:
    """Merge overlapping raw bars by timestamp; downstream bars_frame sorts again."""
    by_time: dict[datetime, dict] = {}
    for row in list(previous or []) + list(delta or []):
        if not isinstance(row, dict):
            continue
        stamp = _row_time(row)
        if stamp is not None:
            by_time[stamp] = row
    ordered = [by_time[stamp] for stamp in sorted(by_time)]
    if limit > 0 and len(ordered) > limit:
        ordered = ordered[-limit:]
    return ordered


def _eligible(kwargs: dict) -> bool:
    reason = str(kwargs.get("history_reason") or "")
    timeframe = str(kwargs.get("timeframe") or "1Min").strip().lower()
    return (
        reason in INCREMENTAL_HISTORY_REASONS
        and timeframe in {"1min", "1m", "m1"}
        and kwargs.get("end") is None
        and isinstance(kwargs.get("start"), datetime)
    )


def _cache_state(provider: LiveWebullProvider, anchor: str) -> dict[str, list[dict]]:
    state = getattr(provider, "_walter_gs424_history_cache", None)
    if not isinstance(state, dict) or state.get("anchor") != anchor:
        state = {"anchor": anchor, "rows": {}}
        setattr(provider, "_walter_gs424_history_cache", state)
    return state["rows"]


def cached_current_session_bars(
    provider: LiveWebullProvider,
    original: Callable,
    symbols: Iterable[str],
    **kwargs,
) -> dict[str, list[dict]]:
    """Return full session truth while fetching only a warm-scan delta when safe."""
    wanted = list(dict.fromkeys(
        str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()
    ))
    if not wanted or not _eligible(kwargs):
        return original(provider, wanted, **kwargs)

    start: datetime = kwargs["start"]
    start_utc = start.astimezone(timezone.utc) if start.tzinfo else start.replace(tzinfo=timezone.utc)
    anchor = f"{start_utc.isoformat()}|1Min"
    cache = _cache_state(provider, anchor)
    limit = max(1, int(kwargs.get("limit") or 10_000))

    cached_symbols: list[str] = []
    uncached_symbols: list[str] = []
    latest_by_symbol: dict[str, datetime] = {}
    for symbol in wanted:
        rows = cache.get(symbol) or []
        latest = _latest_row_time(rows)
        if rows and latest is not None:
            cached_symbols.append(symbol)
            latest_by_symbol[symbol] = latest
        else:
            uncached_symbols.append(symbol)

    # New symbols must retain the exact established full-session seed contract.
    if uncached_symbols:
        seeded = original(provider, uncached_symbols, **kwargs)
        for symbol in uncached_symbols:
            rows = list((seeded or {}).get(symbol) or [])
            if rows:
                cache[symbol] = _merge_rows([], rows, limit)

    incremental_start = None
    if cached_symbols:
        # One common start preserves Webull batch efficiency. The oldest cached last
        # bar is authoritative so a quiet symbol can never acquire a gap merely to
        # make the request smaller. Three minutes of overlap makes replacement of a
        # still-forming/revised final bar deterministic.
        oldest_latest = min(latest_by_symbol.values())
        incremental_start = max(start_utc, oldest_latest - OVERLAP)
        delta_kwargs = dict(kwargs)
        delta_kwargs["start"] = incremental_start
        delta = original(provider, cached_symbols, **delta_kwargs)
        for symbol in cached_symbols:
            new_rows = list((delta or {}).get(symbol) or [])
            cache[symbol] = _merge_rows(cache.get(symbol) or [], new_rows, limit)

    diagnostics = getattr(provider, "diagnostics", None)
    if isinstance(diagnostics, dict):
        diagnostics["gs424_warm_scan_history_cache"] = {
            "authority": AUTHORITY,
            "reason": str(kwargs.get("history_reason") or ""),
            "requested_symbols": len(wanted),
            "cache_hits": len(cached_symbols),
            "full_seed_symbols": len(uncached_symbols),
            "incremental_start": incremental_start.isoformat() if incremental_start else None,
            "session_anchor": start_utc.isoformat(),
            "overlap_seconds": int(OVERLAP.total_seconds()),
            "market_data_values_changed": False,
            "trading_logic_changed": False,
        }

    return {
        symbol: list(cache[symbol])
        for symbol in wanted
        if cache.get(symbol)
    }


def install() -> None:
    """Install once on the persistent LiveWebullProvider class."""
    current = LiveWebullProvider.bars
    if getattr(current, "_gs424_install_generation", None) is _INSTALL_GENERATION:
        return
    if getattr(current, "_gs424_warm_scan_history_cache", False):
        return

    @wraps(current)
    def bars_with_warm_scan_cache(self, symbols, **kwargs):
        return cached_current_session_bars(self, current, symbols, **kwargs)

    bars_with_warm_scan_cache._gs424_warm_scan_history_cache = True
    bars_with_warm_scan_cache._gs424_install_generation = _INSTALL_GENERATION
    bars_with_warm_scan_cache._gs424_original = current
    LiveWebullProvider.bars = bars_with_warm_scan_cache
