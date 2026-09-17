"""GS478: admit sparse but usable current-session movers without synthetic bars.

Sep. 17 PAAI validation exposed a history-sufficiency mismatch, not a scanner-threshold
problem. Stage 6 fetches Webull 1-minute bars from 04:00 ET and has two different
minimums: an older outer guard drops any symbol with fewer than 20 returned bars,
while the actual session analyzer already treats 12 current-session bars as usable.
A formerly quiet symbol can therefore erupt with 12-19 genuine traded minutes and be
silently discarded before Walter evaluates the move.

GS478 bridges only that 12-19-bar gap. During the existing ``stage6_current_session``
request it fetches real completed Webull 1-minute history for the sparse symbols and
prepends only enough prior-session rows to satisfy the obsolete 20-row outer guard.
The base analyzer immediately filters the frame back to the latest trading date; since
there are already at least 12 real current-session rows, its legacy ``<12`` fallback
never runs. VWAP, SuperTrend, volume acceleration, participation, price path, session
high/low and every trading decision therefore remain based on today's real bars.
GS378 likewise filters captured history to the latest Eastern trading date.

If fewer than 12 real current-session bars exist, GS478 does nothing: Walter keeps the
existing insufficient-data behavior rather than manufacturing evidence. No synthetic
or fill-forward bars are created, no 30-second fallback is introduced, and no scanner,
qualification, readiness, ranking, alert, execution or order rule changes.
"""
from __future__ import annotations

from datetime import timedelta
from functools import wraps
from typing import Any

import pandas as pd

AUTHORITY = "HISTORY_SUFFICIENCY_BRIDGE_ONLY"
CURRENT_REASON = "stage6_current_session"
PROFILE_REASON = "stage6_historical_profile"
BRIDGE_REASON = "stage6_sparse_history_bridge"
MIN_REAL_SESSION_BARS = 12
LEGACY_OUTER_GATE_BARS = 20
PROFILE_LOOKBACK_DAYS = 14
PROFILE_HISTORY_BARS = 1200
_OWNER = "_walter_gs478_sparse_history_bridge_owner"


def _symbols(values) -> list[str]:
    return list(dict.fromkeys(
        str(value or "").strip().upper()
        for value in values or []
        if str(value or "").strip()
    ))


def _frame(client, rows) -> pd.DataFrame:
    try:
        frame = client.bars_frame(list(rows or []))
    except Exception:
        return pd.DataFrame()
    if frame is None or getattr(frame, "empty", True):
        return pd.DataFrame()
    return frame.sort_index()


def _current_bar_count(client, rows) -> int:
    frame = _frame(client, rows)
    if frame.empty:
        return 0
    latest_date = frame.index[-1].date()
    return int((frame.index.date == latest_date).sum())


def _bridge_rows(client, prior_rows, current_rows) -> tuple[list[dict], int]:
    """Prepend the minimum real prior rows needed to clear the legacy 20-row guard."""
    current = list(current_rows or [])
    current_count = _current_bar_count(client, current)
    if not (MIN_REAL_SESSION_BARS <= current_count < LEGACY_OUTER_GATE_BARS):
        return current, 0

    prior = list(prior_rows or [])
    if not prior:
        return current, 0
    needed = LEGACY_OUTER_GATE_BARS - current_count
    seed = prior[-needed:]
    if len(seed) < needed:
        return current, 0
    return seed + current, len(seed)


def _merge_profile_result(
    wanted: list[str],
    prefetched: dict[str, list[dict]],
    fetched: dict[str, list[dict]],
) -> dict[str, list[dict]]:
    result = {}
    for symbol in wanted:
        if symbol in prefetched:
            result[symbol] = list(prefetched[symbol])
        elif symbol in fetched:
            result[symbol] = list(fetched[symbol])
    return result


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Install outside GS378 and bridge only one Stage-6 history sufficiency mismatch."""
    from . import discovery

    current_analyze = discovery.analyze_candidates
    if getattr(current_analyze, _OWNER, False):
        return

    @wraps(current_analyze)
    def analyze_with_sparse_history_bridge(client, candidates, news_index, discovery_reasons):
        original_bars = getattr(client, "bars", None)
        if not callable(original_bars):
            return current_analyze(client, candidates, news_index, discovery_reasons)

        prefetched_profiles: dict[str, list[dict]] = {}
        bridged: dict[str, int] = {}
        sparse_counts: dict[str, int] = {}
        under_minimum: dict[str, int] = {}
        bridge_request_count = 0
        profile_reuse_count = 0
        had_instance_bars = False
        prior_instance_bars: Any = None
        instance_dict = getattr(client, "__dict__", None)
        if isinstance(instance_dict, dict):
            had_instance_bars = "bars" in instance_dict
            prior_instance_bars = instance_dict.get("bars")

        def bridge_bars(symbols, **kwargs):
            nonlocal bridge_request_count, profile_reuse_count
            wanted = _symbols(symbols)
            reason = str(kwargs.get("history_reason") or "")
            timeframe = str(kwargs.get("timeframe") or "").strip().lower()

            # If Stage 6 later asks for the completed profile history we already
            # fetched for a sparse symbol, reuse that exact payload. Fetch only peers
            # that were not part of the bridge so the normal profile contract remains.
            if reason == PROFILE_REASON and timeframe in {"1min", "1m", "m1"}:
                reusable = [symbol for symbol in wanted if symbol in prefetched_profiles]
                remaining = [symbol for symbol in wanted if symbol not in prefetched_profiles]
                fetched = original_bars(remaining, **kwargs) if remaining else {}
                profile_reuse_count += len(reusable)
                return _merge_profile_result(wanted, prefetched_profiles, fetched or {})

            result = original_bars(wanted, **kwargs)
            if reason != CURRENT_REASON or timeframe not in {"1min", "1m", "m1"}:
                return result

            result = dict(result or {})
            bridge_symbols = []
            for symbol in wanted:
                count = _current_bar_count(client, result.get(symbol) or [])
                if 0 < count < MIN_REAL_SESSION_BARS:
                    under_minimum[symbol] = count
                elif MIN_REAL_SESSION_BARS <= count < LEGACY_OUTER_GATE_BARS:
                    sparse_counts[symbol] = count
                    bridge_symbols.append(symbol)

            if not bridge_symbols:
                return result

            session_start = kwargs.get("start")
            if not isinstance(session_start, pd.Timestamp):
                try:
                    session_start = pd.Timestamp(session_start)
                except Exception:
                    session_start = None
            if session_start is None:
                return result
            if session_start.tzinfo is None:
                session_start = session_start.tz_localize("America/New_York")

            bridge_kwargs = {
                "start": (session_start - timedelta(days=PROFILE_LOOKBACK_DAYS)).to_pydatetime(),
                "end": session_start.to_pydatetime(),
                "timeframe": "1Min",
                "limit": PROFILE_HISTORY_BARS,
                "force_batch": True,
                "history_reason": BRIDGE_REASON,
            }
            try:
                prior = original_bars(bridge_symbols, **bridge_kwargs) or {}
                bridge_request_count += 1
            except Exception as exc:
                warnings = getattr(client, "warnings", None)
                if isinstance(warnings, list):
                    warnings.append(f"Sparse Stage-6 history bridge unavailable: {exc}")
                prior = {}

            for symbol in bridge_symbols:
                prior_rows = list(prior.get(symbol) or [])
                if prior_rows:
                    prefetched_profiles[symbol] = prior_rows
                merged, used = _bridge_rows(
                    client,
                    prior_rows,
                    result.get(symbol) or [],
                )
                if used:
                    result[symbol] = merged
                    bridged[symbol] = used
            return result

        patched = False
        try:
            setattr(client, "bars", bridge_bars)
            patched = True
            records = current_analyze(client, candidates, news_index, discovery_reasons)
        finally:
            if patched:
                try:
                    if had_instance_bars:
                        setattr(client, "bars", prior_instance_bars)
                    else:
                        delattr(client, "bars")
                except Exception:
                    try:
                        setattr(client, "bars", original_bars)
                    except Exception:
                        pass

        diagnostics = getattr(client, "diagnostics", None)
        if isinstance(diagnostics, dict):
            diagnostics["gs478_sparse_history_bridge"] = {
                "authority": AUTHORITY,
                "sparse_current_bar_counts": dict(sorted(sparse_counts.items())),
                "bridged_prior_rows": dict(sorted(bridged.items())),
                "below_safe_minimum_counts": dict(sorted(under_minimum.items())),
                "bridge_history_requests": bridge_request_count,
                "profile_payloads_reused": profile_reuse_count,
                "minimum_real_session_bars": MIN_REAL_SESSION_BARS,
                "legacy_outer_gate_bars": LEGACY_OUTER_GATE_BARS,
                "synthetic_bars": 0,
                "thirty_second_history_added": False,
                "trading_logic_changed": False,
            }
        return records

    _inherit(analyze_with_sparse_history_bridge, current_analyze)
    analyze_with_sparse_history_bridge._gs478_sparse_history_bridge = True
    analyze_with_sparse_history_bridge._gs478_original = current_analyze
    setattr(analyze_with_sparse_history_bridge, _OWNER, True)
    discovery.analyze_candidates = analyze_with_sparse_history_bridge
