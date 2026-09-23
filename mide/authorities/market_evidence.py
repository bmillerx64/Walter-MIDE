"""Authority boundary for Market Evidence.

This component owns the seam where raw/derived market observations are assembled.
During Phase 1 it delegates to the current validated analyzers without changing
thresholds, formulas, ordering, or evidence semantics.
"""

from mide.discovery import analyze_candidates
from mide.decision_engine import expansion_candidate_diagnostic
from mide.scanner_v2 import (
    apply_scanner_v2,
    participation_gate_rejection_diagnostics,
    strengthening_diagnostics,
)

__all__ = [
    "analyze_candidates",
    "apply_scanner_v2",
    "expansion_candidate_diagnostic",
    "participation_gate_rejection_diagnostics",
    "strengthening_diagnostics",
]
