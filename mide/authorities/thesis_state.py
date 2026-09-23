"""Authority boundary for Thesis / State.

Phase 1 centralizes imports only.  Existing state, escalation, behavioral decision,
and ranking implementations remain authoritative behind this seam until they are
consolidated one behavior at a time.
"""

from mide.decision_engine import behavioral_decision, evaluate
from mide.escalation import (
    escalation_alert_phrase,
    escalation_snapshot,
    escalation_state_changes,
)
from mide.gs310_unified_opportunity_state import (
    CHASE_WAIT,
    DEVELOPING,
    HALTED,
    LOOK_NOW,
    WATCH_FOR_ENTRY,
    opportunity_state,
)
from mide.gs498_mission_ranking_direction import mission_ranked_records
from mide.ui import walter_mission_control

__all__ = [
    "CHASE_WAIT",
    "DEVELOPING",
    "HALTED",
    "LOOK_NOW",
    "WATCH_FOR_ENTRY",
    "behavioral_decision",
    "escalation_alert_phrase",
    "escalation_snapshot",
    "escalation_state_changes",
    "evaluate",
    "mission_ranked_records",
    "opportunity_state",
    "walter_mission_control",
]
