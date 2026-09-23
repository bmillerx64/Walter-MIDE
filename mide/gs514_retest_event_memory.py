"""Compatibility facade for authoritative 3m retest memory.

Held-retest reconstruction and evidence memory are owned by Market Evidence.
Thesis/trigger sequencing and its state explanation are owned by Thesis / State.
The historical GS514 install point remains to preserve validated runtime ordering.

Authority contract retained: PRESENTATION_MEMORY_ONLY.
"""

from __future__ import annotations

AUTHORITY = "PRESENTATION_MEMORY_ONLY"


def _latest_held_retest(tf, st_line, trend, *, observed_at):
    from .authorities import market_evidence
    return market_evidence.latest_held_retest(
        tf, st_line, trend, observed_at=observed_at
    )


def reconstruct_three_minute_retest(raw_rows, client) -> dict:
    from .authorities import market_evidence
    return market_evidence.reconstruct_three_minute_retest(raw_rows, client)


def _memory_truth(original, record: dict) -> dict:
    from .authorities import market_evidence
    return market_evidence.memory_adjusted_retest_truth(original, record)


def discipline_sequence(record: dict, event: dict) -> dict:
    from .authorities import thesis_state
    return thesis_state.discipline_sequence(record, event)


def install() -> None:
    from .authorities import market_evidence, thesis_state
    market_evidence.install_retest_event_memory()
    thesis_state.install_retest_memory_state()


__all__ = [
    "AUTHORITY",
    "discipline_sequence",
    "install",
    "reconstruct_three_minute_retest",
]
