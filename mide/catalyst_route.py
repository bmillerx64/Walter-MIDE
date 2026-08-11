"""Route fresh material-news movers around the squeeze-only float ceiling.

Walter keeps its published eight-stage contract unchanged. Catalyst evidence is
preflighted only to classify the free-float strategy lane; the formal Catalyst
Assessment still owns catalyst membership and failures.
"""
from __future__ import annotations

from typing import Mapping


CATALYST_MOMENTUM_MIN_SCORE = 7.0
TRUSTED_SOURCE_FLAG = "source_quality:trusted"
_INSTALLED = False


def _material_catalyst(record: Mapping[str, object]) -> bool:
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
    """Install catalyst-aware float routing without changing stage contracts."""
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
            """Preflight catalyst evidence, but let float own only float membership."""
            # If catalyst itself is broken, do not mislabel that failure as a
            # Free-Float failure. Fall back to the ordinary float stage; Stage 5
            # will execute catalyst normally and architecture will attribute the
            # technical failure to Catalyst Assessment.
            try:
                raw = dict(catalyst_stage([dict(item) for item in candidates]))
            except Exception:
                return float_stage(candidates)

            expected = {self._symbol(item) for item in candidates}
            # A preflight must never weaken the architecture's every-and-only
            # membership rule. If the provider adds/removes symbols, leave the
            # ordinary float result untouched and let Stage 5 enforce the contract.
            if set(raw) != expected:
                return float_stage(candidates)

            hydrated = []
            for item in candidates:
                symbol = self._symbol(item)
                decision = raw[symbol]
                catalyst_cache[symbol] = decision
                record = dict(item)
                record.update(decision.updates)
                hydrated.append(record)

            decisions = dict(float_stage(hydrated))
            if set(decisions) != expected:
                return decisions

            for item in hydrated:
                symbol = self._symbol(item)
                decision = decisions[symbol]
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
            """Publish cached evidence only when it exactly covers Stage 5 input."""
            symbols = [self._symbol(item) for item in candidates]
            if all(symbol in catalyst_cache for symbol in symbols):
                return {symbol: catalyst_cache[symbol] for symbol in symbols}
            # Missing cache means the preflight could not safely classify the
            # candidate. Execute the real stage so errors and membership
            # violations are attributed to Catalyst Assessment.
            return catalyst_stage(candidates)

        self.free_float = catalyst_preflight_float
        self.catalyst = cached_catalyst

    architecture.WalterArchitectureV1.__init__ = routed_init
    _INSTALLED = True
