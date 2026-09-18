"""GS500: hard-bind GS499 Candidate History containment on warm Streamlit deploys.

GS499 corrected the persistence projection in mide.memory.MemoryStore.append, but
Sept. 18 live validation showed Streamlit can retain the already-imported mide.memory
module across an app.py re-execution. In that case the dashboard build updates while
the old append method survives in memory, so mature candidates continue writing their
full cumulative architecture/ranking/discovery/reevaluation histories.

GS500 patches the retained MemoryStore class from the app.py hard boundary. The
wrapper is idempotent and passes a compact persistence-only copy to whatever append
implementation is currently installed. Cold processes with GS499 already loaded are
safe: applying the projection twice is idempotent.

No live candidate object is mutated. No discovery, provider, market data, score,
ranking, gate, VWAP/ST, qualification, readiness, alert, execution, cadence, or order
behavior changes.
"""
from __future__ import annotations

from collections.abc import Iterable

from .gs499_candidate_history_containment import compact_candidate_history_record


_MARKER = "_gs500_candidate_history_warm_bind"


def install_for_store_class(store_class) -> None:
    current = store_class.append
    if getattr(current, _MARKER, False):
        return

    def append(self, records):
        if not records:
            return current(self, records)
        compacted = [
            compact_candidate_history_record(record)
            for record in records
        ]
        return current(self, compacted)

    append.__name__ = getattr(current, "__name__", "append")
    append.__doc__ = getattr(current, "__doc__", None)
    append._gs500_candidate_history_warm_bind = True
    append._gs500_original = current
    store_class.append = append


def install() -> None:
    from . import memory

    install_for_store_class(memory.MemoryStore)
