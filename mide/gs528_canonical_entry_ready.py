"""Compatibility shim for the canonical Walter Next Entry Authority.

GS528 originally established Walter's executable Entry Ready vocabulary. That
behavior now lives in mide.authorities.entry_authority. This module remains so
existing imports, regression tests, and historical installer paths continue to work
without creating a second source of entry meaning.
"""

from __future__ import annotations

from .authorities.entry_authority import (
    canonical_candidate_status,
    entry_contract,
    install,
    state_with_entry_contract,
)

__all__ = [
    "canonical_candidate_status",
    "entry_contract",
    "install",
    "state_with_entry_contract",
]
