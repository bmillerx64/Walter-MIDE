"""Restore Walter's intended broad prefilter semantics.

The prefilter is a cheap discovery gate, not the final participation gate.
A symbol should survive when it has either a meaningful price move OR meaningful
session participation.  Downstream bar analysis, participation, structure, float,
and entry-state logic remain responsible for trade qualification.
"""
from __future__ import annotations


def install() -> None:
    from . import flight_recorder

    if getattr(flight_recorder.prefilter_decision, "_walter_gain_or_participation", False):
        return

    def gain_or_participation(symbol: str, snapshot: dict, settings) -> dict:
        trade = snapshot.get("latestTrade") or {}
        quote = snapshot.get("latestQuote") or {}
        daily = snapshot.get("dailyBar") or {}
        previous = snapshot.get("prevDailyBar") or {}

        price = float(trade.get("p") or daily.get("c") or 0)
        prev_close = float(previous.get("c") or 0)
        volume = float(daily.get("v") or 0)
        pct_change = ((price / prev_close) - 1) * 100 if prev_close else 0.0
        bid = float(quote.get("bp") or 0)
        ask = float(quote.get("ap") or 0)
        spread = (
            ((ask - bid) / ((ask + bid) / 2) * 100)
            if bid and ask and ask >= bid
            else 99.0
        )
        dollar_volume = price * volume

        thresholds = {
            "min_price": settings.min_price,
            "max_price": settings.max_price,
            "min_pct_change": settings.min_pct_change,
            "min_day_volume": settings.min_day_volume,
        }
        measured = {
            "price": price,
            "pct_change": pct_change,
            "volume": volume,
            "dollar_volume": dollar_volume,
            "spread_pct": spread,
        }

        if not settings.min_price <= price <= settings.max_price:
            failed_rule = "Price outside threshold"
            failed_metrics = [{
                "metric": "price",
                "measured": price,
                "operator": "outside",
                "threshold": [settings.min_price, settings.max_price],
            }]
            reason = (
                f"price {price:g} outside "
                f"[{settings.min_price:g}, {settings.max_price:g}]"
            )
        elif pct_change < settings.min_pct_change and volume < settings.min_day_volume:
            # Preserve the recorder's historical label for compatibility.  The
            # behavior is still OR semantics: only symbols failing both routes stop.
            failed_rule = "Percent change and average volume below thresholds"
            failed_metrics = [
                {
                    "metric": "pct_change",
                    "measured": pct_change,
                    "operator": "<",
                    "threshold": settings.min_pct_change,
                },
                {
                    "metric": "volume",
                    "measured": volume,
                    "operator": "<",
                    "threshold": settings.min_day_volume,
                },
            ]
            reason = (
                f"pct_change {pct_change:.4g} < {settings.min_pct_change:g} and "
                f"volume {volume:g} < {settings.min_day_volume:g}"
            )
        else:
            failed_rule = None
            failed_metrics = []
            route = "price move" if pct_change >= settings.min_pct_change else "participation"
            reason = f"passed prefilter via {route}"

        return {
            "symbol": symbol,
            "passed": failed_rule is None,
            "reason": reason,
            "failed_rule": failed_rule,
            "failed_metrics": failed_metrics,
            "measured_values": measured,
            "thresholds": thresholds,
        }

    gain_or_participation._walter_gain_or_participation = True
    flight_recorder.prefilter_decision = gain_or_participation
