"""GS478: warm-seed lagging 1m indicators when today's traded bars are sparse.

Sep. 17 PAAI validation exposed an acquisition/indicator-continuity gap rather than a
scanner-threshold problem. Stage 6 requests Webull 1-minute history from the current
04:00 ET session and currently drops a candidate when fewer than 20 populated bars are
returned. A formerly quiet symbol can therefore become a major live mover before it
has accumulated twenty actual minute bars, even though Walter already has legitimate
completed-session Webull history for the same symbol.

GS478 uses only real official-provider 1m bars. For a symbol with 1-19 current-session
bars, it keeps up to 80 completed prior-session bars as a bounded seed for lagging
1-minute SuperTrend and EMA65 calculation. Primary/session VWAP, participation,
volume acceleration, price-path evidence, current-session highs/lows and 30-second
truth remain based only on today's live session. No synthetic/fill-forward bars are
created, and slower timeframe confirmation is not manufactured from the seed.

The completed-history request already paid for by Stage 6's volume profile is reused
when available. A bounded batch backfill is made only for a sparse symbol whose
completed-session profile was already cached before GS478 and therefore has no retained
seed rows. The seed cache resets automatically by trading date.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

import pandas as pd

AUTHORITY = "ONE_MINUTE_INDICATOR_CONTINUITY_ONLY"
MIN_INDICATOR_BARS = 20
SEED_BARS = 80
SEED_HISTORY_LIMIT = 240
CACHE_ATTR = "_walter_gs478_sparse_indicator_seed"
HISTORY_REASON = "stage6_sparse_indicator_seed"


def _state(client, session_key) -> dict:
    state = getattr(client, CACHE_ATTR, None)
    anchor = str(session_key)
    if not isinstance(state, dict) or state.get("anchor") != anchor:
        state = {"anchor": anchor, "frames": {}}
        setattr(client, CACHE_ATTR, state)
    return state


def _frame(client, rows) -> pd.DataFrame:
    try:
        frame = client.bars_frame(list(rows or []))
    except Exception:
        return pd.DataFrame()
    if frame is None or getattr(frame, "empty", True):
        return pd.DataFrame()
    return frame.sort_index()


def _prior_seed(client, rows, session_start) -> pd.DataFrame:
    frame = _frame(client, rows)
    if frame.empty:
        return frame
    try:
        boundary = pd.Timestamp(session_start)
        prior = frame.loc[frame.index < boundary].copy()
    except Exception:
        prior = frame.copy()
    return prior.tail(SEED_BARS).copy()


def _remember_frame(state: dict, symbol: str, frame: pd.DataFrame) -> None:
    if frame is None or frame.empty:
        return
    state["frames"][symbol] = frame.tail(SEED_BARS).copy()


def prepare_sparse_indicator_seeds(
    client,
    symbols: Iterable[str],
    current_raw: dict[str, list[dict]],
    historical_raw: dict[str, list[dict]],
    *,
    history_start: datetime,
    session_start,
    session_key,
) -> dict:
    """Retain/recover real prior 1m bars only for sparse current-session symbols."""
    wanted = list(dict.fromkeys(
        str(symbol or "").strip().upper() for symbol in symbols if str(symbol or "").strip()
    ))
    state = _state(client, session_key)

    # Reuse the already-paid completed-session history before considering any backfill.
    reused = 0
    for symbol, rows in (historical_raw or {}).items():
        symbol = str(symbol or "").strip().upper()
        if not symbol or symbol not in wanted:
            continue
        seed = _prior_seed(client, rows, session_start)
        if not seed.empty:
            _remember_frame(state, symbol, seed)
            reused += 1

    sparse: list[str] = []
    for symbol in wanted:
        current = _frame(client, (current_raw or {}).get(symbol) or [])
        if 0 < len(current) < MIN_INDICATOR_BARS:
            sparse.append(symbol)

    missing_seed = [symbol for symbol in sparse if symbol not in state["frames"]]
    backfill = {}
    if missing_seed:
        try:
            backfill = client.bars(
                missing_seed,
                start=history_start,
                end=pd.Timestamp(session_start).to_pydatetime(),
                timeframe="1Min",
                limit=SEED_HISTORY_LIMIT,
                force_batch=True,
                history_reason=HISTORY_REASON,
            )
        except Exception as exc:
            warnings = getattr(client, "warnings", None)
            if isinstance(warnings, list):
                warnings.append(f"Sparse 1m indicator seed unavailable: {exc}")
            backfill = {}
        for symbol in missing_seed:
            seed = _prior_seed(client, (backfill or {}).get(symbol) or [], session_start)
            if not seed.empty:
                _remember_frame(state, symbol, seed)

    available = [symbol for symbol in sparse if symbol in state["frames"]]
    diagnostics = getattr(client, "diagnostics", None)
    if isinstance(diagnostics, dict):
        diagnostics["gs478_sparse_history_warm_seed"] = {
            "authority": AUTHORITY,
            "current_symbols": len(wanted),
            "sparse_symbols": list(sparse),
            "seed_available_symbols": list(available),
            "reused_profile_history_symbols": reused,
            "backfill_requested_symbols": list(missing_seed),
            "backfill_returned_symbols": sorted(
                symbol for symbol in missing_seed if symbol in state["frames"]
            ),
            "seed_bars_max": SEED_BARS,
            "minimum_indicator_bars": MIN_INDICATOR_BARS,
            "synthetic_bars": 0,
            "vwap_seeded": False,
            "participation_seeded": False,
            "thirty_second_seeded": False,
            "slower_timeframes_seeded": False,
        }
    return state


def indicator_frame_for_session(
    client,
    symbol: str,
    session: pd.DataFrame,
    *,
    session_key,
) -> tuple[pd.DataFrame, dict]:
    """Return seeded 1m indicator history while leaving the live session untouched."""
    symbol = str(symbol or "").strip().upper()
    current_count = len(session) if session is not None else 0
    detail = {
        "used": False,
        "current_session_bars": current_count,
        "prior_seed_bars": 0,
        "indicator_bars": current_count,
        "source": "current_session_only",
        "authority": AUTHORITY,
    }
    if session is None or session.empty or current_count >= MIN_INDICATOR_BARS:
        return session, detail

    state = _state(client, session_key)
    seed = state["frames"].get(symbol)
    if seed is None or seed.empty:
        detail["source"] = "insufficient_real_history"
        return session, detail

    combined = pd.concat([seed.tail(SEED_BARS), session]).sort_index()
    combined = combined[~combined.index.duplicated(keep="last")]
    detail.update({
        "prior_seed_bars": len(seed.tail(SEED_BARS)),
        "indicator_bars": len(combined),
        "source": "completed_webull_1m_plus_current_session",
    })
    if len(combined) < MIN_INDICATOR_BARS:
        return session, detail

    detail["used"] = True
    return combined, detail


def reset_sparse_indicator_seed(client) -> None:
    """Test/operator helper; ordinary production reset is automatic by session key."""
    if hasattr(client, CACHE_ATTR):
        delattr(client, CACHE_ATTR)
