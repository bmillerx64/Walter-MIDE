"""Route fresh material-news movers around the squeeze-only float ceiling.

Walter keeps its published eight-stage contract unchanged. The free-float stage
performs a catalyst preflight so a fresh, material company-specific event from a
trusted source can classify a larger-float name into the Catalyst Momentum lane
before the squeeze-only ceiling is enforced. The formal Catalyst Assessment then
consumes the cached preflight decisions, so news is fetched once and the audit
trail retains Walter's existing stage order.
"""
from __future__ import annotations

from typing import Mapping


CATALYST_MOMENTUM_MIN_SCORE = 7.0
TRUSTED_SOURCE_FLAG = "source_quality:trusted"
_INSTALLED = False


def _material_catalyst(record: Mapping[str, object]) -> bool:
    """Require trusted structured news, a headline, and a material positive score."""
    try:
        score = float(record.get("catalyst_score") or 0)
    except (TypeError, ValueError):
        score = 0.0
    flags = {
        str(flag or "").strip().casefold()
        for flag in (record.get("news_flags") or [])
    }
    return (
        bool(str(record.get("headline") or "").strip())
        and score >= CATALYST_MOMENTUM_MIN_SCORE
        and TRUSTED_SOURCE_FLAG in flags
    )


def install() -> None:
    """Install the two-lane catalyst preflight once before Walter is constructed."""
    global _INSTALLED
    if _INSTALLED:
        return

    from . import architecture

    original_init = architecture.WalterArchitectureV1.__init__

    def routed_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        if getattr(self, "_runtime_dispatch", None) is not None:
            return

        catalyst_stage = self.catalyst
        float_stage = self.free_float
        catalyst_cache: dict[str, architecture.Decision] = {}

        def catalyst_preflight_float(candidates):
            """Fetch catalyst evidence once, then enforce float by strategy lane."""
            catalyst_decisions = dict(catalyst_stage(candidates))
            hydrated = []
            for item in candidates:
                symbol = self._symbol(item)
                decision = catalyst_decisions.get(symbol)
                if decision is None:
                    raise architecture.ArchitectureViolation(
                        f"Catalyst preflight must decide candidate {symbol}"
                    )
                catalyst_cache[symbol] = decision
                record = dict(item)
                record.update(decision.updates)
                hydrated.append(record)

            decisions = dict(float_stage(hydrated))
            for item in hydrated:
                symbol = self._symbol(item)
                decision = decisions.get(symbol)
                if decision is None:
                    continue

                # Never use catalyst routing to excuse missing/unverified float.
                # The exception is only for a KNOWN float above the squeeze ceiling.
                over_squeeze_ceiling = (
                    not decision.passed
                    and "exceeds configured limit" in str(decision.reason).lower()
                )
                if not over_squeeze_ceiling or not _material_catalyst(item):
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
                    "Known free float exceeds squeeze ceiling; trusted fresh material catalyst routed to momentum analysis",
                    updates,
                    evidence={
                        "catalyst_score": float(item.get("catalyst_score") or 0),
                        "headline": str(item.get("headline") or ""),
                        "source_quality": "trusted",
                        "squeeze_float_limit": getattr(self.policy, "max_free_float", None),
                        "strategy_lane": "CATALYST_MOMENTUM",
                    },
                    provenance=decision.provenance,
                )
            return decisions

        def cached_catalyst(candidates):
            """Publish the already-fetched catalyst evidence at Stage 5."""
            missing = [
                item for item in candidates
                if self._symbol(item) not in catalyst_cache
            ]
            if missing:
                fresh = dict(catalyst_stage(missing))
                catalyst_cache.update(fresh)
            return {
                self._symbol(item): catalyst_cache[self._symbol(item)]
                for item in candidates
            }

        self.free_float = catalyst_preflight_float
        self.catalyst = cached_catalyst

    architecture.WalterArchitectureV1.__init__ = routed_init
    _INSTALLED = True
