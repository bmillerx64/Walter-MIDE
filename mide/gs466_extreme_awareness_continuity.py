"""GS466: keep current extreme leaders visible when trading freezes their source bar.

Live validation on 2026-09-16 exposed a visibility contradiction on DLXY. Walter
correctly discovered and analyzed the symbol, recorded +121.7% / 144M shares,
participation 74.7, confluence 82, recent bullish 1m/3m structure, and
``qualified_for_ranking=True``. But the last 1m source bar stopped updating while the
stock was suspended. GS373 then treated the 304-second source-bar age as stale market
evidence and GS375 could not re-admit the record for awareness, so a dominant current
mover disappeared from the live Radar even though fresh Webull snapshots still kept
it in DAY_GAINERS / current-attention discovery.

GS466 separates *trade freshness* from *market-event awareness*. It reuses GS333's
existing extreme-mover definition and only relaxes GS373 when the sole visibility
failure is source-bar age. Far-below-VWAP suppression remains intact. The retained
record still flows through GS375 as awareness-only, so entry/alert authority remains
false and normal anti-chase Opportunity State remains authoritative.

No discovery, market-data request, indicator formula, threshold, ranking score,
qualification, readiness, execution, or order behavior changes.
"""
from __future__ import annotations

_REASON_OWNER_ATTR = "_walter_gs466_extreme_awareness_reason_owner"
_VISIBLE_OWNER_ATTR = "_walter_gs466_extreme_awareness_visible_owner"


def _source_bar_stale_reason(reason: str) -> bool:
    return str(reason or "").strip().lower().startswith("source bar is ")


def extreme_awareness_continuity(record: dict, *, base_reason: str) -> bool:
    """Return True when a current extreme mover is hidden only by source-bar age."""
    if not _source_bar_stale_reason(base_reason):
        return False

    # Reuse GS333/GS465's already-established current-extreme contract rather than
    # creating another percentage or provenance threshold here.
    try:
        from .gs333_extreme_mover_operator_priority import extreme_market_event

        return extreme_market_event(record) is not None
    except Exception:
        # Visibility safety should fail closed. An unexpected presentation error must
        # not make stale ordinary records reappear.
        return False


def install() -> None:
    """Patch GS373's operator-only freshness boundary for current extreme leaders."""
    from . import gs373_operator_visibility_freshness as freshness

    current_reason = freshness.operator_visibility_reason
    if not getattr(current_reason, _REASON_OWNER_ATTR, False):
        original_reason = current_reason

        def operator_visibility_reason(record: dict) -> str:
            reason = original_reason(record)
            if extreme_awareness_continuity(record, base_reason=reason):
                return ""
            return reason

        operator_visibility_reason._gs466_extreme_awareness_continuity = True
        operator_visibility_reason._gs466_original = original_reason
        setattr(operator_visibility_reason, _REASON_OWNER_ATTR, True)
        freshness.operator_visibility_reason = operator_visibility_reason

    current_visible = freshness.operator_visible
    if not getattr(current_visible, _VISIBLE_OWNER_ATTR, False):
        def operator_visible(record: dict) -> bool:
            return not freshness.operator_visibility_reason(record)

        operator_visible._gs466_extreme_awareness_continuity = True
        operator_visible._gs466_original = current_visible
        setattr(operator_visible, _VISIBLE_OWNER_ATTR, True)
        freshness.operator_visible = operator_visible
