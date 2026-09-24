"""GS466: warm-deploy-safe facade for current-extreme awareness continuity.

Presentation + Audio owns GS466's awareness-only stale-source-bar exception. Phase 36
keeps this historical import/install point but resolves the authority lazily so a warm
Streamlit process retaining an older authority generation cannot fail merely because
the newer GS466 authority functions are not present yet.

No trade freshness, discovery, qualification, readiness, execution, or order authority
is changed.
"""
from __future__ import annotations


def _presentation():
    from mide.authorities import presentation_audio

    return presentation_audio


def extreme_awareness_continuity(
    record: dict,
    *,
    base_reason: str,
) -> bool:
    current = getattr(
        _presentation(),
        "extreme_awareness_continuity",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation does not yet expose GS466"
        )
    return current(
        record,
        base_reason=base_reason,
    )


def install() -> None:
    current = getattr(
        _presentation(),
        "install_extreme_awareness_continuity",
        None,
    )
    if callable(current):
        current()


def __getattr__(name: str):
    try:
        return getattr(_presentation(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = ["extreme_awareness_continuity", "install"]
