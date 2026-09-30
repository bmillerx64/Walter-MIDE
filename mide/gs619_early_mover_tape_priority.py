"""GS619: warm-deploy-safe facade for early mover / news-tape priority.

Market Evidence owns native five-minute event semantics. Presentation + Audio owns
the operator-only LOOK NOW promotion and weak-news-tape demotion. No provider call,
scanner qualification, readiness, execution, or order authority is added here.
"""
from __future__ import annotations

from mide.authorities import market_evidence as _market
from mide.authorities import presentation_audio as _presentation


FAST_MOVER_MIN_GAIN_PCT = _market.FAST_MOVER_MIN_GAIN_PCT
FAST_MOVER_MAX_RANK = _market.FAST_MOVER_MAX_RANK
FAST_MOVER_PRICE_CEILING = _market.FAST_MOVER_PRICE_CEILING

early_fast_mover_attention = _presentation.early_fast_mover_attention
news_tape_confirmation = _presentation.news_tape_confirmation
augment_visible_records = _presentation.augment_gs619_visible_records
opportunity_state = _presentation.gs619_opportunity_state


def install() -> None:
    _presentation.install_early_mover_tape_priority()


def __getattr__(name: str):
    try:
        return getattr(_presentation, name)
    except AttributeError:
        try:
            return getattr(_market, name)
        except AttributeError:
            raise AttributeError(name) from None


__all__ = [
    "FAST_MOVER_MIN_GAIN_PCT",
    "FAST_MOVER_MAX_RANK",
    "FAST_MOVER_PRICE_CEILING",
    "early_fast_mover_attention",
    "news_tape_confirmation",
    "augment_visible_records",
    "opportunity_state",
    "install",
]
