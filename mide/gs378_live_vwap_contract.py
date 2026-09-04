"""GS378 safety/compatibility bridge for corrected live VWAP and ST/VWAP events.

The core GS378 module fixes Stage-6's VWAP anchor and reconstructs ST/VWAP
crosses from bars already fetched by Walter.  This companion keeps that correction
inside the existing runtime contracts:

* the legacy ``crossed_vwap_and_supertrend`` field keeps its historical meaning
  (current VWAP reclaim + current bullish SuperTrend), now against corrected VWAP;
* GS348 may consume a bar-derived *new* crossover so a 60-second scan cannot miss
  an intrabar transition;
* GS348's existing price/volume/catalyst support gate remains authoritative;
* GS348's scan-to-scan detector remains as a backwards-compatible fallback.

No discovery membership, thresholds, readiness policy, execution, or order logic is
introduced here.
"""
from __future__ import annotations

from functools import wraps
from time import monotonic


_seen_bar_cross_signatures: dict[str, str] = {}


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def _legacy_cross_value(record: dict) -> bool:
    """Preserve the pre-GS378 compatibility contract using corrected VWAP truth."""
    return bool(
        record.get("vwap_reclaimed_last_10m")
        and record.get("supertrend_bullish")
    )


def _new_bar_cross_signature(record: dict) -> str:
    """Return only the currently-new bar event signature, not older recent events."""
    events = record.get("st_vwap_cross_events")
    if isinstance(events, dict):
        parts: list[str] = []
        for label in ("1m", "3m"):
            event = events.get(label)
            if not isinstance(event, dict) or not event.get("new"):
                continue
            timestamp = str(event.get("timestamp") or "").strip()
            if timestamp:
                parts.append(f"{label}@{timestamp}")
        if parts:
            return "|".join(parts)
    if record.get("st_vwap_cross_new"):
        return str(record.get("st_vwap_cross_signature") or "").strip()
    return ""


def _bar_cross_supported(record: dict, gs348) -> bool:
    """Apply the exact GS348 safety gates before activating a reconstructed event."""
    if not record.get("st_vwap_cross_new"):
        return False
    if not bool(record.get("supertrend_bullish") or record.get("supertrend_flip")):
        return False
    return bool(
        gs348._price_above_vwap(record)
        and gs348._supporting_evidence(record)
    )


def reset_state() -> None:
    """Reset only GS378's deduplication state (GS348 reset is wrapped at install)."""
    _seen_bar_cross_signatures.clear()


def install() -> None:
    """Bind compatibility and alert handoff after the core GS378 correction."""
    from . import discovery
    from . import gs348_st_vwap_operator_priority as gs348

    current_analyze = discovery.analyze_candidates
    if not getattr(current_analyze, "_gs378_live_vwap_contract", False):
        @wraps(current_analyze)
        def analyze_with_legacy_contract(client, candidates, news_index, discovery_reasons):
            records = current_analyze(client, candidates, news_index, discovery_reasons)
            for record in records or []:
                if "st_vwap_cross_recent" in record:
                    record["crossed_vwap_and_supertrend"] = _legacy_cross_value(record)
            return records

        _inherit(analyze_with_legacy_contract, current_analyze)
        analyze_with_legacy_contract._gs378_live_vwap_contract = True
        analyze_with_legacy_contract._gs378_contract_original = current_analyze
        discovery.analyze_candidates = analyze_with_legacy_contract

    current_observe = gs348.observe_crosses
    if not getattr(current_observe, "_gs378_bar_cross_handoff", False):
        @wraps(current_observe)
        def observe_with_bar_crosses(records: list[dict], *, now: float | None = None) -> list[str]:
            crossed = list(current_observe(records, now=now))
            stamp = monotonic() if now is None else now
            for record in records or []:
                symbol = str(record.get("symbol") or "").strip().upper()
                signature = _new_bar_cross_signature(record)
                if (
                    not symbol
                    or not signature
                    or _seen_bar_cross_signatures.get(symbol) == signature
                    or not _bar_cross_supported(record, gs348)
                ):
                    continue
                _seen_bar_cross_signatures[symbol] = signature
                gs348._active_crosses[symbol] = stamp
                if symbol not in crossed:
                    crossed.append(symbol)
            return crossed

        _inherit(observe_with_bar_crosses, current_observe)
        observe_with_bar_crosses._gs378_bar_cross_handoff = True
        observe_with_bar_crosses._gs378_bar_cross_original = current_observe
        gs348.observe_crosses = observe_with_bar_crosses

    current_reset = gs348.reset_state
    if not getattr(current_reset, "_gs378_bar_cross_handoff", False):
        @wraps(current_reset)
        def reset_with_bar_crosses() -> None:
            current_reset()
            reset_state()

        _inherit(reset_with_bar_crosses, current_reset)
        reset_with_bar_crosses._gs378_bar_cross_handoff = True
        reset_with_bar_crosses._gs378_bar_cross_original = current_reset
        gs348.reset_state = reset_with_bar_crosses
