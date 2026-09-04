"""GS377: keep strategy-relevant Webull leaders in the operator conversation.

Live validation on 2026-09-04 exposed a first-move awareness gap distinct from
GS376's reclaim-watch case. OFAL remained a current Webull Day Gainer near the
small-cap price range, and PMI accelerated from a sub-$5 reference price through
Walter's configured trading ceiling, yet neither necessarily survived the trade
funnel long enough to stay obvious on the operator screen.

This module extends only the persisted GS334 attention-only Market Events snapshot.
It intentionally does not wrap ``market_event_rows``: GS334's extreme-mover limit
and GS340's high-liquidity classification are established contracts and must remain
unchanged for their direct callers. Instead GS377 observes the already-fetched
native Webull rows after the provider's existing assets wrapper has completed, then
adds only missing strategy leaders to the presentation snapshot.

A current Webull DAY_GAINER is retained as operator context when it is a top-10
leader, is up at least 15%, and either trades at/below the established $5 Walter
small-cap ceiling or can be shown from the same Webull row to have begun the move
from a <=$5 previous-close reference. The latter is calculated from current price
and percentage change; no extra provider call is made.

The lane is presentation-only. It does not add a symbol to the candidate ledger,
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


def merge_strategy_leader_events(
    baseline_events: Iterable[dict] | None,
    native_rows: Iterable[dict] | None,
) -> list[dict]:
    """Append missing GS377 leaders without reclassifying established events."""
    combined = [dict(event) for event in baseline_events or [] if isinstance(event, dict)]
    seen = {
        str(event.get("symbol") or "").strip().upper()
        for event in combined
        if str(event.get("symbol") or "").strip()
    }
    for event in strategy_leader_rows(native_rows):
        symbol = str(event.get("symbol") or "").strip().upper()
        if not symbol or symbol in seen:
            continue
        combined.append(dict(event))
        seen.add(symbol)
    return combined


def publish_strategy_leader_awareness(provider, native_rows: Iterable[dict] | None) -> list[dict]:
    """Persist the awareness overlay after GS334/GS340 have built their snapshot."""
    from . import gs334_market_event_lane as lane

    diagnostics = getattr(provider, "diagnostics", None)
    lane_diagnostics = (
        diagnostics.get("market_event_lane")
        if isinstance(diagnostics, dict)
        else None
    )
    if isinstance(lane_diagnostics, dict):
        baseline = lane_diagnostics.get("events") or []
    else:
        baseline = lane._LATEST_MARKET_EVENTS

    combined = merge_strategy_leader_events(baseline, native_rows)
    lane._LATEST_MARKET_EVENTS = [dict(event) for event in combined]

    if isinstance(diagnostics, dict):
        updated = dict(lane_diagnostics or {})
        updated.setdefault("source", "Webull native DAY_GAINERS")
        updated["attention_only"] = True
        updated["events"] = [dict(event) for event in combined]
        updated["strategy_leader_awareness"] = {
            "min_gain_pct": STRATEGY_LEADER_MIN_GAIN_PCT,
            "max_day_gainer_rank": STRATEGY_LEADER_MAX_DAY_GAINER_RANK,
            "price_ceiling": STRATEGY_LEADER_PRICE_CEILING,
            "limit": STRATEGY_LEADER_LIMIT,
        }
        diagnostics["market_event_lane"] = updated
    return combined


def install() -> None:
    """Overlay the persisted operator snapshot without changing lane semantics."""
    from . import webull_connection as connection
    from .webull_live import LiveWebullProvider

    current_assets = LiveWebullProvider.assets
    if getattr(current_assets, "_gs377_strategy_leader_awareness", False):
        return

    @wraps(current_assets)
    def assets_with_strategy_leader_awareness(self):
        assets = current_assets(self)
        native_rows = list((getattr(self, "_native_radar_prices", {}) or {}).values())
        publish_strategy_leader_awareness(self, native_rows)
        return assets

    assets_with_strategy_leader_awareness._gs377_strategy_leader_awareness = True
    assets_with_strategy_leader_awareness._gs377_original = current_assets
    LiveWebullProvider.assets = assets_with_strategy_leader_awareness

    # GS263/GS334 intentionally expose the same discovery callable through this
    # legacy seam. Preserve that identity after adding presentation observation.
    if getattr(connection, "_webull_native_assets", None) is current_assets:
        connection._webull_native_assets = assets_with_strategy_leader_awareness
