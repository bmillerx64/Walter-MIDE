"""GS464: warm-deploy-safe facade for session-aware VWAP parity.

Phase 35 splits GS464 by responsibility:
- Market Evidence owns the 04:00 premarket / 09:30 RTH primary VWAP policy and
  record-level diagnostics.
- Replay / Validation owns Flight Recorder parity-policy labeling.

The historical GS464 module remains at the validated late-runtime install seam and
keeps the public policy constants used by tests and downstream diagnostics. Both
authorities are resolved lazily so stale warm Streamlit generations safely retain
their already-installed GS464 wrappers rather than failing startup.

The market-data contract is unchanged: no additional provider request is made and
GS464 changes no threshold, qualification, readiness, execution, or order rule.
"""
from __future__ import annotations

from typing import Any

import pandas as pd


SESSION_POLICY = "SESSION_AWARE_04:00_PREMARKET_09:30_RTH"
PREMARKET_POLICY = "PREMARKET_04:00_ET"
RTH_POLICY = "RTH_09:30_ET"
_OWNER_ATTR = "_walter_gs464_session_aware_vwap_owner"
_APPLY_OWNER_ATTR = "_walter_gs464_session_aware_vwap_apply_owner"
_PARITY_OWNER_ATTR = "_walter_gs464_session_aware_vwap_parity_owner"

# Preserve the historical source-visible zero-request contract used by GS464's
# regression scope lock while implementation ownership moves into Market Evidence.
CONTRACT_DIAGNOSTICS = {"additional_market_data_requests": 0}


def _market():
    from mide.authorities import market_evidence

    return market_evidence


def _replay():
    from mide.authorities import replay_validation

    return replay_validation


def _finite(value: Any) -> float | None:
    current = getattr(_market(), "session_vwap_finite", None)
    if callable(current):
        return current(value)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None


def _last_vwap(frame: pd.DataFrame) -> float | None:
    current = getattr(_market(), "session_vwap_last", None)
    if not callable(current):
        raise RuntimeError(
            "Current Market Evidence generation does not yet expose GS464"
        )
    return current(frame)


def session_aware_primary_vwap_context(
    frame: pd.DataFrame | None,
) -> dict:
    current = getattr(
        _market(),
        "session_aware_primary_vwap_context",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Market Evidence generation does not yet expose GS464"
        )
    return current(frame)


def _install_primary_authority() -> None:
    current = getattr(
        _market(),
        "install_session_aware_primary_vwap",
        None,
    )
    if callable(current):
        current()


def _install_record_diagnostics() -> None:
    current = getattr(
        _market(),
        "install_session_aware_vwap_record_diagnostics",
        None,
    )
    if callable(current):
        current()


def _install_recorder_policy_label() -> None:
    current = getattr(
        _replay(),
        "install_session_aware_vwap_parity_labels",
        None,
    )
    if callable(current):
        current()


def install() -> None:
    """Install each GS464 authority slice when its warm generation supports it."""
    _install_primary_authority()
    _install_record_diagnostics()
    _install_recorder_policy_label()


def __getattr__(name: str):
    try:
        return getattr(_market(), name)
    except AttributeError:
        try:
            return getattr(_replay(), name)
        except AttributeError:
            raise AttributeError(name) from None


__all__ = [
    "SESSION_POLICY",
    "PREMARKET_POLICY",
    "RTH_POLICY",
    "session_aware_primary_vwap_context",
    "install",
]
