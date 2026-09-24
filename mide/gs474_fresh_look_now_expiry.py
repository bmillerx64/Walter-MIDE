"""Compatibility shim for Walter Next freshness semantics owned by Thesis / State.

Phase 40 removes the eager authority import while preserving the historical GS474
module and exact Thesis / State callable identity. Current runtimes resolve the
authoritative freshness function and installer lazily; a stale warm Streamlit
generation safely receives a no-op installer if the newer authority export is absent.

No qualification, alert, execution, order, or market-data authority changes.
"""
from __future__ import annotations


_PROVENANCE = "ST_FLIP_PRICE_COMPRESSION"
_OWNER_ATTR = "_walter_gs474_fresh_look_now_expiry_owner"

_EXPORTS = {
    "_compression_owned": "_compression_owned",
    "fresh_look_now_state": "fresh_look_now_state",
    "install": "install_fresh_look_now_expiry",
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


__all__ = ["fresh_look_now_state", "install"]
