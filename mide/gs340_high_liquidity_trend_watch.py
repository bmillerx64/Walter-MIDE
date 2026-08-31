"""GS340: keep exceptional high-liquidity trends visible without widening trade gates.

The 2026-08-31 live session exposed a useful exception to Walter's small-float
attention model. GPRO carried a much larger float than Walter's normal target but
traded extraordinary absolute volume while building a persistent intraday trend.
That is useful operator context, but it is not a reason to weaken free-float,
VWAP, participation, expansion, readiness, or execution rules.

GS340 therefore extends the existing GS334 attention-only Market Events lane. In
addition to +75% extreme movers, a sub-$5 Webull DAY_GAINER may remain visible as
a high-liquidity trend when it is up at least 30%, trades at least 50M shares, and
is ranked in Webull's top 10 Day Gainers. The rule is presentation-only: it does
not add symbols to the candidate ledger, change discovery or qualification, alter
scores or thresholds, or authorize an entry.
"""
from __future__ import annotations

from functools import wraps
from typing import Iterable

LIQUIDITY_TREND_MIN_GAIN_PCT = 30.0
LIQUIDITY_TREND_MIN_VOLUME = 50_000_000.0
LIQUIDITY_TREND_MAX_PRICE = 5.0
LIQUIDITY_TREND_MAX_RANK = 10
LIQUIDITY_TREND_LIMIT = 2


def _number(value, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def high_liquidity_trend_rows(
    native_rows: Iterable[dict] | None,
    *,
    min_gain_pct: float = LIQUIDITY_TREND_MIN_GAIN_PCT,
    min_volume: float = LIQUIDITY_TREND_MIN_VOLUME,
    max_price: float = LIQUIDITY_TREND_MAX_PRICE,
    max_rank: int = LIQUIDITY_TREND_MAX_RANK,
    limit: int = LIQUIDITY_TREND_LIMIT,
) -> list[dict]:
    """Return GPRO-like liquid trends as attention-only event records."""
    events: list[dict] = []
    for source in native_rows or []:
        symbol = str(source.get("symbol") or "").strip().upper()
        sources = {str(value or "") for value in source.get("sources") or []}
        pct_change = _number(source.get("change_ratio"))
        price = _number(source.get("price"))
        volume = _number(source.get("volume"))
        ranks = source.get("ranks") or {}
        rank = _number(ranks.get("day_gainers"), default=999.0) or 999.0

        if not symbol or "day_gainers" not in sources:
            continue
        if pct_change is None or pct_change < float(min_gain_pct):
            continue
        # GS334 already owns the extraordinary +75% path. Keep this rule focused
        # on the otherwise-missed strong, highly liquid trend class.
        if pct_change >= 75.0:
            continue
        if price is None or price <= 0 or price > float(max_price):
            continue
        if volume is None or volume < float(min_volume):
            continue
        if rank > int(max_rank):
            continue

        events.append(
            {
                "symbol": symbol,
                "pct_change": round(pct_change, 2),
                "rank": int(rank),
                "price": price,
                "volume": volume,
                "sources": sorted(sources),
                "attention_only": True,
                "event_type": "high_liquidity_trend",
            }
        )

    events.sort(key=lambda row: (row["rank"], -row["pct_change"], row["symbol"]))
    return events[: max(0, int(limit))]


def install() -> None:
    """Extend GS334's attention lane without touching qualification or trading."""
    from . import gs334_market_event_lane as lane

    current_rows = lane.market_event_rows
    if getattr(current_rows, "_gs340_high_liquidity_trend_watch", False):
        return

    @wraps(current_rows)
    def rows_with_liquidity_trends(native_rows, *, threshold=lane.EXTREME_MOVER_PCT, limit=lane.MARKET_EVENT_LIMIT):
        rows = list(native_rows or [])
        baseline = current_rows(rows, threshold=threshold, limit=limit)
        extras = high_liquidity_trend_rows(rows)
        seen = {str(event.get("symbol") or "").upper() for event in baseline}
        combined = list(baseline)
        for event in extras:
            symbol = str(event.get("symbol") or "").upper()
            if symbol not in seen:
                combined.append(event)
                seen.add(symbol)
        return combined

    rows_with_liquidity_trends._gs340_high_liquidity_trend_watch = True
    rows_with_liquidity_trends._gs340_original = current_rows
    lane.market_event_rows = rows_with_liquidity_trends
