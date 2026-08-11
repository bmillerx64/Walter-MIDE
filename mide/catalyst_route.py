"""Route fresh material-news movers around the squeeze-only float ceiling.

The existing <= configured free-float path remains Walter's squeeze lane. This
module adds a separate catalyst-momentum lane: Catalyst Assessment runs before
Free-Float, and a candidate whose float exceeds the squeeze ceiling may proceed
only when the fresh structured-news score is material. Participation, Expansion,
ranking, and every existing trading threshold remain unchanged.
"""
from __future__ import annotations

from typing import Mapping


CATALYST_MOMENTUM_MIN_SCORE = 7.0
_INSTALLED = False


def _material_catalyst(record: Mapping[str, object]) -> bool:
    try:
        score = float(record.get("catalyst_score") or 0)
    except (TypeError, ValueError):
        score = 0.0
    return bool(str(record.get("headline") or "").strip()) and score >= CATALYST_MOMENTUM_MIN_SCORE


def install() -> None:
    """Install the two-lane stage routing once, before app constructs the funnel."""
    global _INSTALLED
    if _INSTALLED:
        return

    from . import architecture

    original_init = architecture.WalterArchitectureV1.__init__
    original_stages = tuple(architecture.STAGES)
    if len(original_stages) != 8:
        return

    architecture.STAGES = (
        original_stages[0],
        original_stages[1],
        original_stages[2],
        "Catalyst Assessment",
        "Free-Float Gate",
        original_stages[5],
        original_stages[6],
        original_stages[7],
    )

    def routed_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        if getattr(self, "_runtime_dispatch", None) is not None:
            return

        catalyst_stage = self.catalyst
        float_stage = self.free_float

        def routed_float(candidates):
            decisions = dict(float_stage(candidates))
            for item in candidates:
                symbol = self._symbol(item)
                decision = decisions.get(symbol)
                if decision is None or decision.passed or not _material_catalyst(item):
                    continue
                updates = dict(decision.updates)
                updates.update(
                    strategy_lane="CATALYST_MOMENTUM",
                    float_gate_bypass=True,
                    squeeze_eligible=False,
                )
                decisions[symbol] = architecture.Decision(
                    True,
                    "Catalyst Momentum Route",
                    "Free float exceeds squeeze ceiling; fresh material catalyst routed to momentum analysis",
                    updates,
                    evidence={
                        "catalyst_score": float(item.get("catalyst_score") or 0),
                        "headline": str(item.get("headline") or ""),
                        "squeeze_float_limit": getattr(self.policy, "max_free_float", None),
                    },
                    provenance=decision.provenance,
                )
            return decisions

        # WalterArchitectureV1.run binds STAGES[3] to self.free_float and
        # STAGES[4] to self.catalyst. Swap the callbacks to match the reordered
        # stage labels, then wrap only the Free-Float callback with the catalyst
        # lane. The squeeze path and all later-stage calculations are untouched.
        self.free_float = catalyst_stage
        self.catalyst = routed_float

    architecture.WalterArchitectureV1.__init__ = routed_init
    _INSTALLED = True
