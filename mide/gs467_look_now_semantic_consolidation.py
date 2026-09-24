"""Compatibility shim for Walter Next's authoritative LOOK NOW semantics.

GS467's meaning lives in Thesis / State. Phase 37 keeps this historical import surface
while resolving authority exports lazily through module attribute resolution. On a
current runtime the exported callables are the exact Thesis / State function objects,
preserving the established single-owner identity contract. On a stale warm Streamlit
generation, the historical installer resolves to a safe no-op if that authority export
is absent.

No acquisition, indicator, score, qualification, readiness, alert, execution, or
order authority changes.
"""
from __future__ import annotations


_LOOK_NOW_OWNER_ATTR = "_walter_gs467_look_now_semantics_owner"
_PROVENANCE = "GS467_LOOK_NOW_SEMANTICS"

_EXPORTS = {
    "legacy_1m_ignition_look_now": "legacy_1m_ignition_look_now",
    "bottom_up_urgency": "bottom_up_urgency",
    "consolidated_look_now": "consolidated_look_now",
    "install": "install_look_now_semantics",
}


def _thesis():
    from mide.authorities import thesis_state

    return thesis_state


def _noop_install() -> None:
    return None


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is not None:
        value = getattr(_thesis(), target, None)
        if callable(value):
            return value
        if name == "install":
            return _noop_install
        raise AttributeError(name)
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
