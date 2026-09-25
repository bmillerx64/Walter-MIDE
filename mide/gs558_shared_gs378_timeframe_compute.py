"""GS558: share deterministic GS378 timeframe computation within one scan.

GS557 live evidence isolated roughly 15.7 seconds per scan inside
gs378.apply_live_vwap_truth. That path recomputes the same 1m/3m SuperTrend,
resampled frames, and projected primary-VWAP series several times for confirmation,
literal crossover reconstruction, and alignment.

GS558 adds a scan-local cache around those *pure local calculations* only. It does
not cache across scans, symbols, provider responses, or source-bar updates. Existing
functions still own every formula and threshold; this module only reuses an already
computed return value when the exact same in-memory frame/series object and arguments
are requested again during the same apply_live_vwap_truth call.

The cache is ContextVar-scoped, restored in finally blocks, and observationally
reports hit/miss counts so live CAB evidence can verify the performance effect.
"""
from __future__ import annotations

from contextvars import ContextVar
from functools import wraps
from time import perf_counter
from typing import Any


AUTHORITY = "LOCAL_COMPUTE_REUSE_ONLY"
DIAGNOSTIC_KEY = "gs558_shared_gs378_timeframe_compute"
_APPLY_OWNER = "_walter_gs558_shared_gs378_apply_cache"
_ST_OWNER = "_walter_gs558_shared_gs378_supertrend_cache"
_FRAME_OWNER = "_walter_gs558_shared_gs378_frame_cache"
_VWAP_OWNER = "_walter_gs558_shared_gs378_vwap_cache"

_CACHE: ContextVar[dict[str, Any] | None] = ContextVar(
    "walter_gs558_gs378_cache",
    default=None,
)


def _new_cache() -> dict[str, Any]:
    return {
        "supertrend": {},
        "timeframe_frame": {},
        "timeframe_vwap": {},
        "stats": {
            "supertrend_requests": 0,
            "supertrend_hits": 0,
            "supertrend_misses": 0,
            "timeframe_frame_requests": 0,
            "timeframe_frame_hits": 0,
            "timeframe_frame_misses": 0,
            "timeframe_vwap_requests": 0,
            "timeframe_vwap_hits": 0,
            "timeframe_vwap_misses": 0,
        },
    }


def _same_object_lookup(bucket: dict, key, source):
    cached = bucket.get(key)
    if (
        isinstance(cached, tuple)
        and len(cached) == 2
        and cached[0] is source
    ):
        return True, cached[1]
    return False, None


def _install_supertrend_cache(gs378) -> bool:
    current = gs378.supertrend
    if getattr(current, _ST_OWNER, False):
        return False

    @wraps(current)
    def shared_supertrend(frame, period=10, multiplier=3.0):
        cache = _CACHE.get()
        if cache is None:
            return current(frame, period, multiplier)

        stats = cache["stats"]
        stats["supertrend_requests"] += 1
        key = (id(frame), int(period), float(multiplier))
        hit, value = _same_object_lookup(
            cache["supertrend"],
            key,
            frame,
        )
        if hit:
            stats["supertrend_hits"] += 1
            return value

        stats["supertrend_misses"] += 1
        value = current(frame, period, multiplier)
        cache["supertrend"][key] = (frame, value)
        return value

    setattr(shared_supertrend, _ST_OWNER, True)
    shared_supertrend._gs558_original = current
    gs378.supertrend = shared_supertrend
    return True


def _install_timeframe_frame_cache(gs378) -> bool:
    current = gs378._timeframe_frame
    if getattr(current, _FRAME_OWNER, False):
        return False

    @wraps(current)
    def shared_timeframe_frame(day, label):
        cache = _CACHE.get()
        if cache is None:
            return current(day, label)

        stats = cache["stats"]
        stats["timeframe_frame_requests"] += 1
        key = (id(day), str(label))
        hit, value = _same_object_lookup(
            cache["timeframe_frame"],
            key,
            day,
        )
        if hit:
            stats["timeframe_frame_hits"] += 1
            return value

        stats["timeframe_frame_misses"] += 1
        value = current(day, label)
        cache["timeframe_frame"][key] = (day, value)
        return value

    setattr(shared_timeframe_frame, _FRAME_OWNER, True)
    shared_timeframe_frame._gs558_original = current
    gs378._timeframe_frame = shared_timeframe_frame
    return True


def _install_timeframe_vwap_cache(gs378) -> bool:
    current = gs378._timeframe_vwap
    if getattr(current, _VWAP_OWNER, False):
        return False

    @wraps(current)
    def shared_timeframe_vwap(primary_series, label):
        cache = _CACHE.get()
        if cache is None:
            return current(primary_series, label)

        stats = cache["stats"]
        stats["timeframe_vwap_requests"] += 1
        key = (id(primary_series), str(label))
        hit, value = _same_object_lookup(
            cache["timeframe_vwap"],
            key,
            primary_series,
        )
        if hit:
            stats["timeframe_vwap_hits"] += 1
            return value

        stats["timeframe_vwap_misses"] += 1
        value = current(primary_series, label)
        cache["timeframe_vwap"][key] = (primary_series, value)
        return value

    setattr(shared_timeframe_vwap, _VWAP_OWNER, True)
    shared_timeframe_vwap._gs558_original = current
    gs378._timeframe_vwap = shared_timeframe_vwap
    return True


def _install_apply_scope(gs378) -> bool:
    current = gs378.apply_live_vwap_truth
    if getattr(current, _APPLY_OWNER, False):
        return False

    @wraps(current)
    def apply_with_shared_timeframe_compute(
        records,
        current_session_raw,
        current_session_30s_raw,
        client,
    ):
        existing = _CACHE.get()
        if existing is not None:
            return current(
                records,
                current_session_raw,
                current_session_30s_raw,
                client,
            )

        cache = _new_cache()
        token = _CACHE.set(cache)
        started = perf_counter()
        try:
            return current(
                records,
                current_session_raw,
                current_session_30s_raw,
                client,
            )
        finally:
            elapsed_ms = (perf_counter() - started) * 1000.0
            stats = dict(cache["stats"])
            diagnostics = getattr(client, "diagnostics", None)
            if isinstance(diagnostics, dict):
                diagnostics[DIAGNOSTIC_KEY] = {
                    "authority": AUTHORITY,
                    "apply_elapsed_ms": round(elapsed_ms, 3),
                    **stats,
                    "cache_lifetime": "one apply_live_vwap_truth call",
                    "cross_scan_cache": False,
                    "extra_provider_calls": 0,
                    "market_data_values_changed": False,
                    "indicator_formulas_changed": False,
                    "trading_logic_changed": False,
                }
            _CACHE.reset(token)

    setattr(apply_with_shared_timeframe_compute, _APPLY_OWNER, True)
    apply_with_shared_timeframe_compute._gs558_original = current
    gs378.apply_live_vwap_truth = apply_with_shared_timeframe_compute
    return True


def install() -> bool:
    """Install scan-local GS378 compute reuse on the currently retained graph."""
    from mide import gs378_live_vwap_st_crossover as gs378

    changed = False
    changed = _install_supertrend_cache(gs378) or changed
    changed = _install_timeframe_frame_cache(gs378) or changed
    changed = _install_timeframe_vwap_cache(gs378) or changed
    changed = _install_apply_scope(gs378) or changed
    return changed


__all__ = ["AUTHORITY", "DIAGNOSTIC_KEY", "install"]
