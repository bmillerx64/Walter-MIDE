"""GS304: keep display-only trade readiness consistent with evidence trust.

Walter's scanner/ranking/qualification remain authoritative.  This module only
prevents the mission-card readiness presentation from advertising READY or
ENTRY WINDOW when the same record fails the existing read-only market-evidence
audit.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any

from .market_evidence_audit import market_evidence_report


def evidence_guarded_readiness(
    item: Mapping[str, Any],
    base_readiness: Mapping[str, Any],
    *,
    max_age_seconds: float = 120.0,
) -> dict[str, Any]:
    """Return a detached presentation result capped when evidence is untrusted."""
    result = deepcopy(dict(base_readiness))
    record = item.get("record") or {}
    if not isinstance(record, Mapping):
        return result

    evidence = market_evidence_report(record, max_age_seconds=max_age_seconds)
    result["evidence_status"] = evidence["status"]
    result["evidence_fresh"] = evidence["fresh"]
    result["evidence_guarded"] = False

    # BUILDING/WATCH remain useful observational states.  The safety invariant is
    # only that READY/ENTRY WINDOW may not be presented from non-TRUSTED evidence.
    if int(result.get("index", 0) or 0) < 3 or evidence["trusted"]:
        return result

    result["index"] = 1
    result["state"] = "WATCH"
    result["evidence_guarded"] = True
    if not evidence["fresh"]:
        result["sentence"] = "Market evidence is stale. Refresh before entry."
    elif evidence["coherence_failures"]:
        result["sentence"] = "Market evidence is inconsistent. Refresh before entry."
    else:
        result["sentence"] = "Market evidence is incomplete. Refresh before entry."
    return result


def install() -> None:
    """Install the guard at the existing display-only readiness seam."""
    from . import ui

    if getattr(ui, "_gs304_installed", False):
        return

    original: Callable[[dict], dict] = ui.trade_readiness

    def trade_readiness(item: dict) -> dict:
        base = original(item)
        return evidence_guarded_readiness(item, base)

    ui.trade_readiness = trade_readiness
    ui._gs304_trade_readiness_original = original
    ui._gs304_installed = True
