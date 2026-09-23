"""Compatibility facade for proven-leader reset / re-ignition.

Market memory and reset/re-ignition evidence are owned by Market Evidence.
Opportunity State meaning is owned by Thesis / State.
Visible awareness enrichment and audio are owned by Presentation + Audio.
The historical GS477 install/import path remains to preserve runtime ordering.
"""

from __future__ import annotations


_MARKET_EXPORTS = {
    "PROVEN_LEADER_EXTENSION_PCT",
    "NEAR_VWAP_WINDOW_PCT",
    "LEADER_MEMORY_TTL_SECONDS",
    "MAX_REIGNITION_VWAP_DISTANCE_PCT",
    "RESET_WATCH",
    "REIGNITION",
    "THREE_MINUTE_CONFIRMATION",
    "LeaderMemory",
}


def __getattr__(name: str):
    if name in _MARKET_EXPORTS:
        from .authorities import market_evidence
        return getattr(market_evidence, name)
    raise AttributeError(name)


def leader_reset_evidence(record: dict, memory, *, now: float) -> dict:
    from .authorities import market_evidence
    return market_evidence.leader_reset_evidence(record, memory, now=now)


def apply_leader_reset_marks(records: list[dict], *, now: float | None = None) -> list[dict]:
    from .authorities import market_evidence
    return market_evidence.apply_leader_reset_marks(records, now=now)


def reset_leader_memory() -> None:
    from .authorities import market_evidence
    market_evidence.reset_leader_memory()


def leader_reset_opportunity_state(original, record: dict) -> dict:
    from .authorities import thesis_state
    return thesis_state.leader_reset_opportunity_state(original, record)


def augment_leader_reset_records(records: list[dict], visible: list[dict]) -> list[dict]:
    from .authorities import presentation_audio
    return presentation_audio.augment_leader_reset_records(records, visible)


def enrich_visible_records(records: list[dict], actionable_function) -> list[dict]:
    from .authorities import presentation_audio
    return presentation_audio.enrich_visible_records(records, actionable_function)


def leader_reset_audio_phrase(records: list[dict]) -> str:
    from .authorities import presentation_audio
    return presentation_audio.leader_reset_audio_phrase(records)


def install() -> None:
    from .authorities import presentation_audio, thesis_state
    thesis_state.install_leader_reset_state()
    presentation_audio.install_leader_reset_audio()


__all__ = [
    "apply_leader_reset_marks",
    "augment_leader_reset_records",
    "enrich_visible_records",
    "install",
    "leader_reset_audio_phrase",
    "leader_reset_evidence",
    "leader_reset_opportunity_state",
    "reset_leader_memory",
]
