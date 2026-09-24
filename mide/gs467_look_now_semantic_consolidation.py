"""Compatibility shim for Walter Next's authoritative LOOK NOW semantics.

GS467's meaning lives in Thesis / State. Phase 37 keeps this historical import/install
surface but resolves the authority lazily so a warm Streamlit process retaining an
older Thesis / State generation cannot fail startup merely because newer GS467
exports are absent.

No acquisition, indicator, score, qualification, readiness, alert, execution, or
order authority changes.
"""
from __future__ import annotations


_LOOK_NOW_OWNER_ATTR = "_walter_gs467_look_now_semantics_owner"
_PROVENANCE = "GS467_LOOK_NOW_SEMANTICS"


def _thesis():
    from mide.authorities import thesis_state

    return thesis_state


def legacy_1m_ignition_look_now(view: dict) -> bool:
    current = getattr(
        _thesis(),
        "legacy_1m_ignition_look_now",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Thesis / State generation does not yet expose GS467"
        )
    return current(view)


def bottom_up_urgency(record: dict) -> dict:
    current = getattr(_thesis(), "bottom_up_urgency", None)
    if not callable(current):
        raise RuntimeError(
            "Current Thesis / State generation does not yet expose GS467"
        )
    return current(record)


def consolidated_look_now(original, record: dict) -> dict:
    current = getattr(_thesis(), "consolidated_look_now", None)
    if not callable(current):
        raise RuntimeError(
            "Current Thesis / State generation does not yet expose GS467"
        )
    return current(original, record)


def install() -> None:
    current = getattr(
        _thesis(),
        "install_look_now_semantics",
        None,
    )
    if callable(current):
        current()


def __getattr__(name: str):
    try:
        return getattr(_thesis(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "bottom_up_urgency",
    "consolidated_look_now",
    "install",
    "legacy_1m_ignition_look_now",
]
