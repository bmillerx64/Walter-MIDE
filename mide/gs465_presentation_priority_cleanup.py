"""GS465: warm-deploy-safe facade for presentation priority cleanup.

Presentation + Audio already owns GS465's state-contiguous card ordering, truthful
extreme-mover labels, and single-banner extreme WATCH continuity. Phase 36 removes
the remaining eager authority binding and duplicate compatibility helper bodies from
this historical module.

The numeric bands remain local constants because they are part of GS465's validated
public surface and do not require an authority module to be current at import time.
All replaceable behavior resolves Presentation + Audio lazily. A stale warm Streamlit
generation that does not yet expose a Phase-36-compatible installer safely keeps its
already-installed legacy wrapper instead of failing startup.

This remains presentation-only: no discovery, provider, indicator, threshold,
qualification, readiness, alert permission, execution, or order behavior changes.
"""
from __future__ import annotations


_ORDER_OWNER_ATTR = "_walter_gs465_state_contiguous_order_owner"
_EXTREME_OWNER_ATTR = "_walter_gs465_extreme_semantics_owner"
_EXTREME_SELECTION_OWNER_ATTR = (
    "_walter_gs465_extreme_selection_continuity_owner"
)

WATCH_FOR_ENTRY_BAND = 60
LOOK_NOW_BAND = 50
DEVELOPING_BAND = 40
CHASE_WAIT_BAND = 30
HALTED_BAND = 20
OTHER_BAND = 10


def _presentation():
    from mide.authorities import presentation_audio

    return presentation_audio


def strict_state_band(record: dict) -> int:
    current = getattr(_presentation(), "strict_state_band", None)
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation does not yet expose GS465"
        )
    return current(record)


def attention_tiebreak(record: dict) -> tuple[int, float, float]:
    current = getattr(_presentation(), "attention_tiebreak", None)
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation does not yet expose GS465"
        )
    return current(record)


def ordered_state_contiguous_records(
    records: list[dict],
    baseline_order=None,
) -> list[dict]:
    current = getattr(
        _presentation(),
        "ordered_state_contiguous_records",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation does not yet expose GS465"
        )
    return current(
        records,
        baseline_order=baseline_order,
    )


def _specific_look_now(view: dict) -> bool:
    current = getattr(
        _presentation(),
        "_specific_extreme_look_now",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation does not yet expose GS465"
        )
    return current(view)


def cleaned_extreme_event(original, record: dict) -> dict | None:
    current = getattr(_presentation(), "cleaned_extreme_event", None)
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation does not yet expose GS465"
        )
    return current(original, record)


def _non_extreme_actionable_symbols(
    rows: list[dict],
    extreme_symbols: set[str],
) -> set[str]:
    current = getattr(
        _presentation(),
        "_non_extreme_actionable_symbols",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation does not yet expose GS465"
        )
    return current(rows, extreme_symbols)


def prioritized_extreme_with_watch_continuity(
    original,
    records,
    *,
    now=None,
):
    current = getattr(
        _presentation(),
        "prioritized_extreme_with_watch_continuity",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation does not yet expose GS465"
        )
    return current(
        original,
        records,
        now=now,
    )


def _install_order() -> None:
    current = getattr(
        _presentation(),
        "activate_operator_order_stage",
        None,
    )
    if callable(current):
        current("state_contiguous")


def _install_extreme_semantics() -> None:
    current = getattr(
        _presentation(),
        "activate_extreme_event_stage",
        None,
    )
    if callable(current):
        current("cleanup")


def _install_extreme_selection_continuity() -> None:
    current = getattr(
        _presentation(),
        "install_extreme_selection_continuity",
        None,
    )
    if callable(current):
        current()


def install() -> None:
    """Install each GS465 presentation slice when its warm generation supports it."""
    _install_order()
    _install_extreme_semantics()
    _install_extreme_selection_continuity()


def __getattr__(name: str):
    try:
        return getattr(_presentation(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "WATCH_FOR_ENTRY_BAND",
    "LOOK_NOW_BAND",
    "DEVELOPING_BAND",
    "CHASE_WAIT_BAND",
    "HALTED_BAND",
    "OTHER_BAND",
    "strict_state_band",
    "attention_tiebreak",
    "ordered_state_contiguous_records",
    "cleaned_extreme_event",
    "prioritized_extreme_with_watch_continuity",
    "install",
]
