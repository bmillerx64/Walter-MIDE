"""Compatibility facade for authoritative 3m SuperTrend retest truth.

Current/replay retest evidence is owned by mide.authorities.market_evidence.
Trader-facing interpretation is owned by mide.authorities.thesis_state.
This historical module remains so installer order and older imports stay stable.
"""

from __future__ import annotations


def three_minute_st_retest_truth(record: dict) -> dict:
    from .authorities import market_evidence
    return market_evidence.three_minute_st_retest_truth(record)


def state_with_3m_st_truth(original, record: dict) -> dict:
    from .authorities import thesis_state
    return thesis_state.state_with_3m_st_truth(original, record)


def install() -> None:
    from .authorities import thesis_state
    thesis_state.install_3m_st_retest_truth()


__all__ = ["three_minute_st_retest_truth", "state_with_3m_st_truth", "install"]
