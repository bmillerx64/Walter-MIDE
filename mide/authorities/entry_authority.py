"""Authority boundary for Entry Authority.

Canonical Entry Ready remains the existing GS528 contract in Phase 1.  Callers use
this stable module so subsequent consolidation can remove installer layering without
creating a second entry decision.
"""

from mide.gs528_canonical_entry_ready import canonical_candidate_status
from mide.scanner_v2 import qualified_for_alert, qualified_for_entry, qualified_for_watch

__all__ = [
    "canonical_candidate_status",
    "qualified_for_alert",
    "qualified_for_entry",
    "qualified_for_watch",
]
