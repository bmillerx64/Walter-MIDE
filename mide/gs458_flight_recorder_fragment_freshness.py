"""GS458: hard-bind Flight Recorder freshness inside the fragment lifecycle.

Live validation after GS454 showed repeated Flight Recorder downloads could still
return an older gzip snapshot even while Walter's scans continued. The cause is a
wrapper-boundary problem: GS434/GS350 owns the Flight Recorder Streamlit fragment,
while GS454's version-key wrapper is installed later and therefore sits outside that
fragment. Fragment-only reruns can bypass the outer freshness wrapper entirely.

GS458 re-runs the now late-bind-safe GS350 installer after GS454/455/456/457 are
installed. The resulting outer GS350 fragment calls the complete established inner
download chain on every fragment rerun. That means GS454 recomputes the recorder
identity/size/mtime key at actual download time. A private non-Streamlit sentinel is
consumed by the older nested GS350 instance so no nested fragment is created.

Export/presentation lifecycle only. No recorder persistence, scan cadence, market
data, discovery, participation, qualification, readiness, alert, execution, or order
behavior changes.
"""
from __future__ import annotations

AUTHORITY = "FLIGHT_RECORDER_FRAGMENT_FRESHNESS_ONLY"


def _replay_validation():
    from mide.authorities import replay_validation

    return replay_validation


def install() -> None:
    """Warm-deploy-safe facade for GS458 export lifecycle authority."""
    current = getattr(
        _replay_validation(),
        "install_flight_recorder_fragment_freshness",
        None,
    )
    if callable(current):
        current()
        return

    # Retained-runtime fallback for an older Replay / Validation generation.
    import streamlit as st
    from . import gs350_download_export_reliability as gs350

    gs350.install()
    active = st.download_button
    active._gs458_flight_recorder_fragment_freshness = True
    active._gs458_authority = AUTHORITY
    active._gs458_trading_logic_changed = False
