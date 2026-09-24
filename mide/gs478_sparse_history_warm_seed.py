"""GS478: warm-deploy-safe compatibility facade for sparse-history sufficiency.

Phase 31 moves the validated Stage-6 sparse-history bridge into Walter Next's
authoritative Market Evidence component. GS478 remains at the historical startup
location and preserves the helper/constant seams used by live regression tests.

The facade resolves Market Evidence lazily. If a warm Streamlit process retains an
older authority generation, install() leaves the already-active legacy GS478 wrapper
in place instead of failing startup. A clean runtime binds the consolidated bridge.

Contract unchanged: only 12-19 genuine current-session 1-minute bars are eligible;
one bounded real-history bridge may use {"timeframe": "1Min"} with a 14-day lookback
and 32-bar limit; fewer than 12 real current-session bars remain insufficient; no
synthetic bars, 30-second fallback, scanner threshold, qualification, ranking,
readiness, alert, execution, or order semantics change.
"""
from __future__ import annotations


AUTHORITY = "HISTORY_SUFFICIENCY_BRIDGE_ONLY"
CURRENT_REASON = "stage6_current_session"
BRIDGE_REASON = "stage6_sparse_history_bridge"
MIN_REAL_SESSION_BARS = 12
LEGACY_OUTER_GATE_BARS = 20
BRIDGE_LOOKBACK_DAYS = 14
BRIDGE_HISTORY_BARS = 32
_OWNER = "_walter_gs478_sparse_history_bridge_owner"


def _market():
    from mide.authorities import market_evidence

    return market_evidence


def _symbols(values) -> list[str]:
    current = getattr(_market(), "sparse_history_symbols", None)
    if not callable(current):
        return list(
            dict.fromkeys(
                str(value or "").strip().upper()
                for value in values or []
                if str(value or "").strip()
            )
        )
    return current(values)


def _frame(client, rows):
    current = getattr(_market(), "sparse_history_frame", None)
    if not callable(current):
        raise RuntimeError(
            "Current Market Evidence generation does not yet expose GS478"
        )
    return current(client, rows)


def _current_bar_count(client, rows) -> int:
    current = getattr(_market(), "sparse_history_current_bar_count", None)
    if not callable(current):
        raise RuntimeError(
            "Current Market Evidence generation does not yet expose GS478"
        )
    return current(client, rows)


def _bridge_rows(client, prior_rows, current_rows) -> tuple[list[dict], int]:
    current = getattr(_market(), "bridge_sparse_history_rows", None)
    if not callable(current):
        raise RuntimeError(
            "Current Market Evidence generation does not yet expose GS478"
        )
    return current(client, prior_rows, current_rows)


def install() -> None:
    current = getattr(_market(), "install_sparse_history_bridge", None)
    if not callable(current):
        # Warm-deploy safety: pre-Phase-31 GS478 may already own this wrapper.
        return
    current()


def __getattr__(name: str):
    try:
        return getattr(_market(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "AUTHORITY",
    "CURRENT_REASON",
    "BRIDGE_REASON",
    "MIN_REAL_SESSION_BARS",
    "LEGACY_OUTER_GATE_BARS",
    "BRIDGE_LOOKBACK_DAYS",
    "BRIDGE_HISTORY_BARS",
    "install",
]
