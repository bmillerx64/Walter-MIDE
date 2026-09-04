"""GS377: keep strategy-relevant Webull leaders in the operator conversation.

Live validation on 2026-09-04 exposed a first-move awareness gap distinct from
GS376's reclaim-watch case.  OFAL remained a current Webull Day Gainer near the
small-cap price range, and PMI accelerated from a sub-$5 reference price through
Walter's configured trading ceiling, yet neither necessarily survived the trade
funnel long enough to stay obvious on the operator screen.

This module extends only the existing GS334 attention-only Market Events lane.
A current Webull DAY_GAINER is retained as operator context when it is a top-10
leader, is up at least 15%, and either trades at/below the established $5 Walter
small-cap ceiling or can be shown from the same Webull row to have begun the move
from a <=$5 previous-close reference.  The latter is calculated from current
price and percentage change; no extra provider call is made.

The lane is presentation-only.  It does not add a symbol to the candidate ledger,
change Price/Float/Participation/Expansion gates, alter scores or ranking, grant
watch/entry/alert authority, or touch execution/orders.
"""
from __future__ import annotations

from functools import wraps
from typing import Iterable

STRATEGY_LEADER_MIN_GAIN_PCT = 15.0
STRATEGY_LEADER_MAX_DAY_GAINER_RANK = 10
STRATEGY_LEADER_PRICE_CEILING = 5.0
STRATEGY_LEADER_LIMIT = 5


def _number(value, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def implied_previous_close(price: float | None, pct_change: float | None) -> float | None:
    """Recover the prior-close reference from the native Day Gainer row."""
    if price is None or pct_change is None:
        return None
    denominator = 1.0 + float(pct_change) / 100.0
    if price <= 0 or denominator <= 0:
        return None
    return float(price) / denominator


def strategy_leader_rows(
    native_rows: Iterable[dict] | None,
    *,
    min_gain_pct: float = STRATEGY_LEADER_MIN_GAIN_PCT,
    max_rank: int = STRATEGY_LEADER_MAX_DAY_GAINER_RANK,
    price_ceiling: float = STRATEGY_LEADER_PRICE_CEILING,
    limit: int = STRATEGY_LEADER_LIMIT,
) -> list[dict]:
    """Return current strategy-relevant Day Gainers as attention-only records."""
    leaders: list[dict] = []
    for source in native_rows or []:
        symbol = str(source.get("symbol") or "").strip().upper()
        sources = {str(value or "") for value in source.get("sources") or []}
        if not symbol or "day_gainers" not in sources:
            continue

        pct_change = _number(source.get("change_ratio"))
        price = _number(source.get("price"))
        volume = _number(source.get("volume"))
        ranks = source.get("ranks") or {}
        rank = _number(ranks.get("day_gainers"), default=999.0) or 999.0
        if pct_change is None or pct_change < float(min_gain_pct):
            continue
        if rank > int(max_rank):
            continue

        prior_close = implied_previous_close(price, pct_change)
        currently_in_range = price is not None and 0 < price <= float(price_ceiling)
        launched_from_range = (
            prior_close is not None and 0 < prior_close <= float(price_ceiling)
        )
        if not (currently_in_range or launched_from_range):
            continue

        leaders.append(
            {
                "symbol": symbol,
                "pct_change": round(float(pct_change), 2),
                "rank": int(rank),
                "price": price,
                "volume": volume,
                "sources": sorted(sources),
                "attention_only": True,
                "event_type": "strategy_leader",
                "strategy_price_reference": (
                    "current_price" if currently_in_range else "implied_previous_close"
                ),
                "implied_previous_close": (
                    round(prior_close, 4) if prior_close is not None else None
                ),
            }
        )

    leaders.sort(key=lambda row: (row["rank"], -row["pct_change"], row["symbol"]))
    return leaders[: max(0, int(limit))]


def install() -> None:
    """Extend GS334/GS340 Market Events without touching the trade funnel."""
    from . import gs334_market_event_lane as lane

    current_rows = lane.market_event_rows
    if getattr(current_rows, "_gs377_strategy_leader_awareness", False):
        return

    @wraps(current_rows)
    def rows_with_strategy_leaders(
        native_rows,
        *,
        threshold=lane.EXTREME_MOVER_PCT,
        limit=lane.MARKET_EVENT_LIMIT,
    ):
        rows = list(native_rows or [])
        baseline = current_rows(rows, threshold=threshold, limit=limit)
        extras = strategy_leader_rows(rows)
        seen = {str(event.get("symbol") or "").strip().upper() for event in baseline}
        combined = list(baseline)
        for event in extras:
            symbol = str(event.get("symbol") or "").strip().upper()
            if symbol and symbol not in seen:
                combined.append(event)
                seen.add(symbol)
        return combined

    rows_with_strategy_leaders._gs377_strategy_leader_awareness = True
    rows_with_strategy_leaders._gs377_original = current_rows
    lane.market_event_rows = rows_with_strategy_leaders
