"""Intraday relative-strength measurements used only for candidate ranking."""

from __future__ import annotations

from typing import Any

SMALL_CAP_MARKET_CAP = 2_000_000_000
SMALL_CAP_FLOAT_SHARES = 20_000_000
RS_RANKING_WEIGHT = 0.08


def benchmark_for(candidate: dict) -> str:
    """Choose IWM for identifiable small caps and SPY for other candidates."""
    market_cap = candidate.get("market_cap")
    if market_cap is not None:
        try:
            return "IWM" if float(market_cap) <= SMALL_CAP_MARKET_CAP else "SPY"
        except (TypeError, ValueError):
            pass
    for key in ("float_shares", "shares_float", "free_float"):
        value = candidate.get(key)
        if value is not None:
            try:
                return "IWM" if float(value) <= SMALL_CAP_FLOAT_SHARES else "SPY"
            except (TypeError, ValueError):
                continue
    return "SPY"


def _performance(closes: Any, periods: int | None) -> float | None:
    if closes is None or len(closes) < 2:
        return None
    start_index = 0 if periods is None else max(0, len(closes) - periods - 1)
    start = float(closes.iloc[start_index])
    end = float(closes.iloc[-1])
    if not start:
        return None
    return (end / start - 1.0) * 100.0


def relative_strength_metrics(candidate_session: Any, benchmark_session: Any) -> dict:
    """Return candidate-minus-benchmark performance for three intraday windows."""
    result = {}
    values = []
    for key, periods in (("5m", 5), ("15m", 15), ("since_open", None)):
        candidate_return = _performance(candidate_session.get("close"), periods)
        benchmark_return = _performance(benchmark_session.get("close"), periods)
        relative = (
            candidate_return - benchmark_return
            if candidate_return is not None and benchmark_return is not None
            else None
        )
        result[f"relative_performance_{key}_pct"] = (
            round(relative, 2) if relative is not None else None
        )
        if relative is not None:
            values.append(relative)
    score = sum(values) / len(values) if values else 0.0
    result["relative_strength_score"] = round(score, 2)
    result["relative_strength_ranking_component"] = round(score * RS_RANKING_WEIGHT, 3)
    return result
