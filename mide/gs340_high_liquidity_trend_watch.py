"""Compatibility facade for GS340 high-liquidity trend awareness."""

from __future__ import annotations

from .authorities import market_evidence as _market


LIQUIDITY_TREND_MIN_GAIN_PCT = _market.LIQUIDITY_TREND_MIN_GAIN_PCT
LIQUIDITY_TREND_MIN_VOLUME = _market.LIQUIDITY_TREND_MIN_VOLUME
LIQUIDITY_TREND_MAX_PRICE = _market.LIQUIDITY_TREND_MAX_PRICE
LIQUIDITY_TREND_MAX_RANK = _market.LIQUIDITY_TREND_MAX_RANK
LIQUIDITY_TREND_LIMIT = _market.LIQUIDITY_TREND_LIMIT

high_liquidity_trend_rows = _market.high_liquidity_trend_rows


def install() -> None:
    _market.activate_high_liquidity_trend_watch()


__all__ = [
    "LIQUIDITY_TREND_MIN_GAIN_PCT",
    "LIQUIDITY_TREND_MIN_VOLUME",
    "LIQUIDITY_TREND_MAX_PRICE",
    "LIQUIDITY_TREND_MAX_RANK",
    "LIQUIDITY_TREND_LIMIT",
    "high_liquidity_trend_rows",
    "install",
]
