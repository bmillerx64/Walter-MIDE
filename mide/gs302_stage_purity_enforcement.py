"""GS302: enforce stage-owned field boundaries without changing gate logic.

Some production stage functions return a full enriched candidate snapshot inside
``Decision.updates``. WalterArchitectureV1 already declares several upstream
fields as owned by earlier stages, but historically it only *reported* the
violation and then still applied the forbidden update. In live diagnostics this
appeared as Participation Assessment rewriting ``price``.

This patch strips only fields the architecture already declares forbidden for the
current stage before the authoritative record is updated. The stage's pass/fail
result, evidence, provenance, scoring fields, thresholds, and all permitted
updates are preserved unchanged.
"""
from __future__ import annotations

from collections.abc import Mapping

_STAGE_FORBIDDEN = {
    "Catalyst Assessment": {"price", "free_float", "mission_rank", "ranking"},
    "Participation Assessment": {"price", "free_float", "catalyst", "mission_rank", "ranking"},
    "Expansion Assessment": {"price", "free_float", "catalyst", "mission_rank", "ranking"},
}


def _sanitize_decision(stage: str, decision):
    forbidden = _STAGE_FORBIDDEN.get(stage, set())
    updates = decision.updates
    if not forbidden or not isinstance(updates, Mapping):
        return decision
    cleaned = {key: value for key, value in updates.items() if key not in forbidden}
    if len(cleaned) == len(updates):
        return decision

    from .architecture import Decision

    return Decision(
        decision.passed,
        decision.category,
        decision.reason,
        cleaned,
        decision.evidence,
        decision.provenance,
    )


def install() -> None:
    from .architecture import WalterArchitectureV1

    original = WalterArchitectureV1._assess
    if getattr(original, "_gs302_installed", False):
        return

    def _assess(self, stage, candidates, operation):
        forbidden = _STAGE_FORBIDDEN.get(stage, set())
        if not forbidden:
            return original(self, stage, candidates, operation)

        def owned_operation(records):
            decisions = operation(records)
            return {
                symbol: _sanitize_decision(stage, decision)
                for symbol, decision in decisions.items()
            }

        return original(self, stage, candidates, owned_operation)

    _assess._gs302_installed = True
    _assess._gs302_original = original
    WalterArchitectureV1._assess = _assess
