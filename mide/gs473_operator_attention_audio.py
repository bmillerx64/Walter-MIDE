"""GS473: warm-deploy-safe Presentation + Audio facade for operator attention audio.

The fresh WATCH NOW / Entry Ready audio semantics now live in Presentation + Audio.
This historical module retains the validated constants and mutable _gate_passed seam
because GS512 rebinds that exact helper at runtime to Architecture-v1 audit truth.

Presentation + Audio deliberately resolves _gate_passed through this facade at
candidate-evaluation time, preserving both cold- and warm-runtime compatibility.
Missing newer authority installers safely no-op rather than failing startup.

No scanner, market-data, qualification, readiness, execution or order authority is
changed.
"""
from __future__ import annotations


_OWNER = "_walter_gs473_operator_attention_audio_owner"
ATTENTION_STATUS = "WATCH NOW"
ATTENTION_CANDIDATE = "ENTRY READY"

CONTRACT = {
    "entry_authority_changed": False,
    "alert_authority_changed": False,
}


def _presentation():
    from mide.authorities import presentation_audio

    return presentation_audio


def _gate_passed(record: dict, name: str) -> bool:
    current = getattr(
        _presentation(),
        "legacy_operator_attention_gate_passed",
        None,
    )
    if not callable(current):
        return False
    return current(record, name)


def operator_attention_candidate(record: dict) -> dict:
    current = getattr(
        _presentation(),
        "operator_attention_candidate",
        None,
    )
    if not callable(current):
        return {
            "active": False,
            "fresh": False,
            "authority": "OPERATOR_ATTENTION_AUDIO_ONLY",
            "entry_authority_changed": False,
            "alert_authority_changed": False,
        }
    return current(record)


def operator_attention_audio_phrase(
    records: list[dict],
) -> str:
    current = getattr(
        _presentation(),
        "operator_attention_audio_phrase",
        None,
    )
    if not callable(current):
        return ""
    return current(records)


def install() -> None:
    current = getattr(
        _presentation(),
        "install_operator_attention_audio",
        None,
    )
    if callable(current):
        current()


def __getattr__(name: str):
    try:
        return getattr(_presentation(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "ATTENTION_STATUS",
    "ATTENTION_CANDIDATE",
    "operator_attention_candidate",
    "operator_attention_audio_phrase",
    "install",
]
