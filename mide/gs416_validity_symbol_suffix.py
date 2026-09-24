"""GS416: warm-deploy-safe compatibility facade for Validity suffix handling.

Phase 28 moves the established Validity Gate security-shape correction into Walter
Next's authoritative Entry Authority. This facade remains at the historical startup
location and resolves the authority lazily so a warm Streamlit process retaining the
prior Entry Authority generation cannot fail at module import time.

Behavior is unchanged: bare trailing W/R/U letters remain valid common-stock ticker
characters; explicit dot/hyphen derivative suffixes, provider security type, ETF
policy, OTC status, inactive status, and legal/operational tradability remain
authoritative.
"""
from __future__ import annotations


def _entry():
    from mide.authorities import entry_authority

    return entry_authority


def supported_security(record: dict, *, include_etfs: bool) -> bool:
    """Delegate the established GS416 security-shape decision to Entry Authority."""
    current = getattr(_entry(), "supported_security", None)
    if not callable(current):
        raise RuntimeError(
            "Current Entry Authority generation does not yet expose GS416"
        )
    return current(record, include_etfs=include_etfs)


def install() -> None:
    """Install lazily and tolerate an older retained Entry Authority generation."""
    current = getattr(_entry(), "install_validity_symbol_suffix", None)
    if not callable(current):
        # Warm-deploy safety: the pre-Phase-28 GS416 wrapper may already be active.
        # Do not crash startup while an older authority generation remains retained.
        return
    current()


def __getattr__(name: str):
    try:
        return getattr(_entry(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = ["supported_security", "install"]
