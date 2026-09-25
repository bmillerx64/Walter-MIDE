"""GS559: scan-local semantic reuse for identical SuperTrend inputs.

GS558 proved that exact-object reuse inside GS378 removes some duplicate work, but the
first live GS558 CAB still showed ~14.0s median inside gs378.apply_live_vwap_truth.
The same OHLC sequence is also rebuilt into distinct DataFrame objects across the base
analyzer, timeframe alignment, and GS378. SuperTrend depends only on ordered high/low/
close values plus period and multiplier, so those repeated calculations can be safely
shared inside one analyze_candidates call even when the DataFrame objects differ.

GS559 computes a strong digest of the exact high/low/close float64 bytes and reuses
only matching SuperTrend numeric outputs for the duration of one analyzer call. Returned
Series are rebuilt on the caller's own index, so timezone/index representation remains
caller-correct. Nothing survives across scans.
"""
from __future__ import annotations

from contextvars import ContextVar
from functools import wraps
import hashlib
from typing import Any

import numpy as np
import pandas as pd


AUTHORITY = "LOCAL_COMPUTE_REUSE_ONLY"
DIAGNOSTIC_KEY = "gs559_scan_local_supertrend_reuse"
_SCOPE_OWNER = "_walter_gs559_supertrend_scope"
_WRAPPER_OWNER = "_walter_gs559_supertrend_wrapper"

_STATE: ContextVar[dict[str, Any] | None] = ContextVar(
    "walter_gs559_supertrend_state",
    default=None,
)


def _ohlc_key(frame, period: int, multiplier: float) -> tuple | None:
    if frame is None:
        return None
    try:
        values = frame.loc[:, ["high", "low", "close"]].to_numpy(
            dtype=np.float64,
            copy=False,
        )
    except Exception:
        return None
    contiguous = np.ascontiguousarray(values, dtype=np.float64)
    digest = hashlib.blake2b(
        contiguous.tobytes(order="C"),
        digest_size=20,
    ).digest()
    return (
        int(contiguous.shape[0]),
        int(contiguous.shape[1]),
        int(period),
        float(multiplier),
        digest,
    )


def _wrap_supertrend(function, label: str):
    if getattr(function, _WRAPPER_OWNER, False):
        return function, False

    @wraps(function)
    def shared_supertrend(frame, period=10, multiplier=3.0):
        state = _STATE.get()
        if state is None:
            return function(frame, period, multiplier)

        stats = state["stats"]
        stats["requests"] += 1
        key = _ohlc_key(frame, period, multiplier)
        if key is None:
            stats["unkeyed"] += 1
            return function(frame, period, multiplier)

        cached = state["cache"].get(key)
        if cached is not None:
            stats["hits"] += 1
            stats["hits_by_alias"][label] = (
                stats["hits_by_alias"].get(label, 0) + 1
            )
            st_values, trend_values = cached
            return (
                pd.Series(
                    st_values.copy(),
                    index=frame.index,
                    dtype=float,
                ),
                pd.Series(
                    trend_values.copy(),
                    index=frame.index,
                    dtype=bool,
                ),
            )

        stats["misses"] += 1
        st, trend = function(frame, period, multiplier)
        state["cache"][key] = (
            st.to_numpy(dtype=float, copy=True),
            trend.to_numpy(dtype=bool, copy=True),
        )
        return st, trend

    setattr(shared_supertrend, _WRAPPER_OWNER, True)
    shared_supertrend._gs559_original = function
    shared_supertrend._gs559_alias = label
    return shared_supertrend, True


def _patch_alias(module, attribute: str, label: str) -> bool:
    current = getattr(module, attribute, None)
    if not callable(current):
        return False
    wrapped, changed = _wrap_supertrend(current, label)
    if changed:
        setattr(module, attribute, wrapped)
    return changed


def install() -> bool:
    """Install one-scan SuperTrend reuse across the active analyzer aliases."""
    from mide import discovery
    from mide import gs378_live_vwap_st_crossover as gs378
    from mide import timeframe_alignment

    changed = False
    changed = _patch_alias(
        discovery,
        "supertrend",
        "discovery.supertrend",
    ) or changed
    changed = _patch_alias(
        timeframe_alignment,
        "supertrend",
        "timeframe_alignment.supertrend",
    ) or changed
    changed = _patch_alias(
        gs378,
        "supertrend",
        "gs378.supertrend",
    ) or changed

    current = discovery.analyze_candidates
    if getattr(current, _SCOPE_OWNER, False):
        return changed

    @wraps(current)
    def analyze_with_scan_local_supertrend(
        client,
        candidates,
        news_index,
        discovery_reasons,
    ):
        existing = _STATE.get()
        if existing is not None:
            return current(
                client,
                candidates,
                news_index,
                discovery_reasons,
            )

        state = {
            "cache": {},
            "stats": {
                "requests": 0,
                "hits": 0,
                "misses": 0,
                "unkeyed": 0,
                "hits_by_alias": {},
            },
        }
        token = _STATE.set(state)
        try:
            return current(
                client,
                candidates,
                news_index,
                discovery_reasons,
            )
        finally:
            stats = dict(state["stats"])
            diagnostics = getattr(client, "diagnostics", None)
            if isinstance(diagnostics, dict):
                diagnostics[DIAGNOSTIC_KEY] = {
                    "authority": AUTHORITY,
                    **stats,
                    "unique_computations": int(stats["misses"]),
                    "cache_entries": len(state["cache"]),
                    "cache_lifetime": "one analyze_candidates call",
                    "cross_scan_cache": False,
                    "digest_columns": ["high", "low", "close"],
                    "digest_algorithm": "blake2b-160",
                    "extra_provider_calls": 0,
                    "market_data_values_changed": False,
                    "indicator_formula_changed": False,
                    "trading_logic_changed": False,
                }
            _STATE.reset(token)

    setattr(analyze_with_scan_local_supertrend, _SCOPE_OWNER, True)
    analyze_with_scan_local_supertrend._gs559_original = current
    discovery.analyze_candidates = analyze_with_scan_local_supertrend
    return True


__all__ = ["AUTHORITY", "DIAGNOSTIC_KEY", "install"]
