"""GS294: give recently evaluated Webull names one bounded fresh recheck.

Webull discovery is a moving gainers/most-active shortlist.  A symbol can leave
that shortlist between scans even while its intraday setup is still developing.
GS292 made that disappearance visible and GS293 can raise display urgency only
when fresh observations exist.  This layer bridges those two facts by carrying
*symbol identity only* for one additional scan.

The carried symbol receives brand-new Webull price/snapshot/history evidence and
must pass every normal Walter gate again.  No stale quote, score, qualification,
rank, catalyst, readiness, or execution state is reused.
"""
from __future__ import annotations

from collections.abc import Mapping

RECHECK_REASON = "GS294 fresh attention recheck"
RECHECK_LIMIT = 8
_ELIGIBLE_TERMINAL_STAGES = {
    "Participation Assessment",
    "Expansion Assessment",
    "Mission Ranking and Publication",
}


def _number(record: Mapping[str, object], *keys: str) -> float:
    for key in keys:
        try:
            value = record.get(key)
            if value is not None:
                return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _was_carry_only(record: Mapping[str, object]) -> bool:
    reasons = [str(value) for value in (record.get("discovery_reasons") or []) if value]
    return bool(reasons) and all(value == RECHECK_REASON for value in reasons)


def select_recheck_symbols(
    records: Mapping[str, Mapping[str, object]],
    *,
    current_symbols: set[str],
    last_completed_scan: int,
    limit: int = RECHECK_LIMIT,
) -> list[str]:
    """Choose prior-scan attention names for exactly one fresh extra look.

    Eligibility deliberately uses only *where Walter got to* on the prior fresh
    scan and prioritization metadata.  It never declares the symbol qualified.
    A name that was itself present only because of GS294 is not carried again,
    preventing an old symbol from becoming permanent universe membership.
    """
    if last_completed_scan <= 0 or limit <= 0:
        return []

    eligible: list[Mapping[str, object]] = []
    for raw_symbol, record in records.items():
        symbol = str(record.get("symbol") or raw_symbol or "").strip().upper()
        if not symbol or symbol in current_symbols:
            continue
        if int(record.get("discovery_last_seen_scan") or 0) != last_completed_scan:
            continue
        if _was_carry_only(record):
            continue
        if record.get("terminal_outcome") == "Technical Failure":
            continue
        if str(record.get("terminal_stage") or "") not in _ELIGIBLE_TERMINAL_STAGES:
            continue
        eligible.append(record)

    # Ranked names first, then the strongest already-computed observational
    # evidence.  These values decide only which identities receive a fresh read;
    # they never bypass or modify any downstream gate.
    def priority(record: Mapping[str, object]):
        rank = record.get("mission_rank")
        ranked = rank is not None
        rank_value = -int(rank) if ranked else -10_000
        return (
            1 if ranked else 0,
            rank_value,
            _number(record, "conviction_v2_score", "conviction_score", "scanner_v2_score"),
            _number(record, "participation_surge_score", "participation_score"),
            _number(record, "pct_change"),
            str(record.get("symbol") or ""),
        )

    eligible.sort(key=priority, reverse=True)
    return [str(record.get("symbol") or "").strip().upper() for record in eligible[:limit]]


def _is_webull_client(client) -> bool:
    provider = str(getattr(client, "provider_name", "") or "").upper()
    class_name = client.__class__.__name__.upper()
    return "WEBULL" in provider or "WEBULL" in class_name


def install() -> None:
    """Wrap discovery before app.py imports build_seed_symbols."""
    from . import discovery

    original = discovery.build_seed_symbols
    if getattr(original, "_gs294_installed", False):
        return

    def build_seed_symbols(client, settings, news_items, *, universe_verification=None):
        if universe_verification is None:
            seeds, reasons = original(client, settings, news_items)
        else:
            seeds, reasons = original(
                client,
                settings,
                news_items,
                universe_verification=universe_verification,
            )

        # A broad Alpaca-style universe does not need this grace recheck.  The
        # fix is intentionally scoped to Webull's rotating native shortlist.
        if not _is_webull_client(client):
            return seeds, reasons

        try:
            import streamlit as st

            ledger = getattr(st.session_state, "walter_candidate_ledger", None)
            records = getattr(ledger, "records", None)
            last_scan = int(getattr(ledger, "scan_number", 0) or 0)
            if not isinstance(records, Mapping) or last_scan <= 0:
                return seeds, reasons

            current = {str(symbol).strip().upper() for symbol in seeds}
            carried = select_recheck_symbols(
                records,
                current_symbols=current,
                last_completed_scan=last_scan,
            )
            for symbol in carried:
                if symbol in current:
                    continue
                seeds.append(symbol)
                current.add(symbol)
                reasons.setdefault(symbol, []).append(RECHECK_REASON)

            diagnostics = getattr(client, "diagnostics", None)
            if isinstance(diagnostics, dict):
                diagnostics["attention_recheck"] = {
                    "policy": "one additional scan; fresh Webull evidence required",
                    "limit": RECHECK_LIMIT,
                    "symbols": list(carried),
                    "count": len(carried),
                }
                diagnostics["final_seed_count"] = len(seeds)
        except Exception as exc:
            # Recheck is resilience only.  If session state is unavailable, the
            # native discovery result remains authoritative and scanning proceeds.
            diagnostics = getattr(client, "diagnostics", None)
            if isinstance(diagnostics, dict):
                diagnostics["attention_recheck"] = {
                    "policy": "one additional scan; fresh Webull evidence required",
                    "count": 0,
                    "error": f"{type(exc).__name__}: {exc}",
                }

        return seeds, reasons

    build_seed_symbols._gs294_installed = True
    build_seed_symbols._gs294_original = original
    discovery.build_seed_symbols = build_seed_symbols
