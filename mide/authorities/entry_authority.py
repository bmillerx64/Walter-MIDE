"""Authority boundary for Entry Authority.

Canonical Entry Ready remains the existing GS528 contract in Phase 1.  Callers use
this stable module so subsequent consolidation can remove installer layering without
creating a second entry decision.
"""

from mide.gs528_canonical_entry_ready import canonical_candidate_status, entry_contract
from mide.gs532_retest_entry_shadow import retest_entry_shadow
from mide.scanner_v2 import (
    qualified_for_alert,
    qualified_for_entry,
    qualified_for_watch,
    trigger_diagnostics,
)

__all__ = [
    "canonical_candidate_status",
    "entry_contract",
    "qualified_for_alert",
    "qualified_for_entry",
    "qualified_for_watch",
    "retest_entry_shadow",
    "trigger_diagnostics",
]
