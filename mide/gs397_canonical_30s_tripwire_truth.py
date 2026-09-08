"""GS397: make genuine Webull 30-second SuperTrend canonical for attention.

Live close validation on 2026-09-08 proved that GS396's stream recorder could see
real bullish 30-second SuperTrend while Walter's older Stage-6 alignment record still
reported the canonical 30s state as false.  The cause was two independent 30-second
paths: GS378 could receive an empty/unsupported ``30Sec`` history result while GS396
was correctly reconstructing completed 30-second bars from the live Webull TICK
stream.

GS397 removes that split-brain state without granting 30-second data entry authority:

* completed Webull stream 30s bars are supplied to GS378's existing alignment path
  before its VWAP/ST rescoring and attention ranking;
* GS396's fresh-tripwire fields are attached to the same analyzed records before
  they leave Stage 6;
* ``timeframes['30s']`` and ``timeframe_alignment['30s']`` are synchronized to that
  same live source and carry explicit source/authority/freshness diagnostics;
* a *fresh* 30s bullish flip becomes current-attention provenance and may enter the
  operator investigation view even when ordinary watch qualification is still false;
* the underlying ``qualified_for_watch``, ``qualified_for_entry``, trigger, readiness,
  execution, and order fields are never promoted by this module.

Thus the contract remains:

    discovery -> 30s investigate -> 1m primary ignition -> 3m confirmation

The 30s stream is read from Walter's existing in-memory Webull subscription cache.
No additional provider/network request is introduced.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from functools import wraps
from typing import Any

from . import gs378_live_vwap_st_crossover as gs378
from . import gs396_live_30s_tripwire as gs396

AUTHORITY = gs396.AUTHORITY
SOURCE = gs396.SOURCE
ATTENTION_PROVENANCE = "FRESH_30S_TRIPWIRE"
INVESTIGATION_AUTHORITY = "ATTENTION_ONLY_NOT_ENTRY_AUTHORITY"
_ALIGNMENT_LABELS = {3: "Strong", 2: "Good", 1: "Weak", 0: "Countertrend"}


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def fresh_30s_tripwire(record: dict) -> bool:
    """Return whether the genuine live 30s flip is inside GS396's freshness TTL."""
    if not record.get("supertrend_30s_available"):
        return False
    tripwire = record.get("thirty_second_tripwire") or {}
    return bool(record.get("supertrend_30s_flip") or tripwire.get("fresh_flip"))


def _primary_above_vwap(record: dict, alignment_30s: dict, tripwire: dict) -> bool | None:
    """Prefer the Stage-6 30s calculation, then derive from the same live close."""
    if "above_vwap" in alignment_30s:
        value = alignment_30s.get("above_vwap")
        if value is not None:
            return bool(value)
    close = _number(tripwire.get("latest_close"))
    vwap = _number(record.get("vwap_value"))
    if close is None or vwap is None:
        return None
    return close >= vwap


def canonicalize_record(record: dict) -> dict:
    """Synchronize all canonical 30s state to GS396's genuine stream evidence.

    This function mutates no qualification or entry-authority field.  It only replaces
    stale/empty 30s evidence and adds explicit investigation diagnostics.
    """
    if not record.get("supertrend_30s_available"):
        return record

    tripwire = dict(record.get("thirty_second_tripwire") or {})
    bullish = bool(record.get("supertrend_30s_bullish", tripwire.get("bullish")))
    fresh = fresh_30s_tripwire(record)

    alignment = deepcopy(record.get("timeframe_alignment") or {})
    thirty = dict(alignment.get("30s") or {})
    above_vwap = _primary_above_vwap(record, thirty, tripwire)

    thirty.update(
        {
            "above_vwap": above_vwap,
            "supertrend_bullish": bullish,
            "authority": AUTHORITY,
            "source": SOURCE,
            "data_available": True,
            "fresh_flip": fresh,
            "last_flip_timestamp": record.get("supertrend_30s_last_flip_timestamp")
            or tripwire.get("last_flip_timestamp"),
            "last_flip_age_seconds": record.get("supertrend_30s_last_flip_age_seconds")
            if record.get("supertrend_30s_last_flip_age_seconds") is not None
            else tripwire.get("last_flip_age_seconds"),
            "latest_closed_timestamp": tripwire.get("latest_closed_timestamp"),
            "latest_close": _number(tripwire.get("latest_close")),
            "supertrend_10_3": _number(tripwire.get("supertrend_value")),
            "volume_acceleration_30s": _number(tripwire.get("volume_acceleration_30s")),
            "dollar_flow_acceleration_30s": _number(
                tripwire.get("dollar_flow_acceleration_30s")
            ),
            "operator_investigation_tripwire": fresh,
            "investigation_authority": INVESTIGATION_AUTHORITY,
        }
    )

    # GS378 has now received the genuine stream frame, so its EMA/structure values are
    # real when present. Recompute only the established alignment boolean; do not
    # invent missing EMA/structure evidence.
    if "above_ema65" in thirty:
        structure = thirty.get("higher_highs_higher_lows")
        thirty["aligned"] = bool(
            above_vwap is True
            and bullish
            and thirty.get("above_ema65") is True
            and structure is not False
        )

    alignment["30s"] = thirty
    record["timeframe_alignment"] = alignment

    timeframes = deepcopy(record.get("timeframes") or {})
    tf30 = dict(timeframes.get("30s") or {})
    tf30.update(
        {
            "above_vwap": above_vwap,
            "supertrend": bullish,
            "supertrend_bullish": bullish,
            "fresh_flip": fresh,
            "authority": AUTHORITY,
            "source": SOURCE,
            "investigation_authority": INVESTIGATION_AUTHORITY,
        }
    )
    timeframes["30s"] = tf30
    record["timeframes"] = timeframes

    if record.get("alignment_score") is not None:
        score = sum(
            bool((alignment.get(label) or {}).get("aligned"))
            for label in ("30s", "1m", "3m")
        )
        record["alignment_score"] = score
        record["alignment_total"] = 3
        record["alignment_label"] = _ALIGNMENT_LABELS[score]

    record["operator_investigation_tripwire"] = fresh
    record["operator_investigation_authority"] = INVESTIGATION_AUTHORITY
    return record


class _Captured30sProvider:
    """Present one immutable local stream snapshot to GS396 without a second read."""

    def __init__(self, rows_by_symbol: dict[str, list[dict]]):
        self.rows_by_symbol = rows_by_symbol

    def stream_30s_bars(self, symbol: str):
        return list(self.rows_by_symbol.get(str(symbol or "").strip().upper(), []) or [])


def _stream_provider(client):
    if client is not None and hasattr(client, "stream_30s_bars"):
        return client
    try:
        return gs396._active_provider()
    except Exception:
        return None


def _capture_stream_rows(records, provider) -> dict[str, list[dict]]:
    if provider is None or not hasattr(provider, "stream_30s_bars"):
        return {}
    captured: dict[str, list[dict]] = {}
    for source in records or []:
        symbol = str((source or {}).get("symbol") or "").strip().upper()
        if not symbol:
            continue
        try:
            rows = list(provider.stream_30s_bars(symbol) or [])
        except Exception:
            rows = []
        if rows:
            captured[symbol] = rows
    return captured


def _install_canonical_stage6_path() -> None:
    """Feed the live 30s cache into GS378 before Stage-6 evidence leaves discovery."""
    current = gs378.apply_live_vwap_truth
    if getattr(current, "_gs397_canonical_30s", False):
        return

    @wraps(current)
    def apply_canonical_30s(
        records,
        current_session_raw,
        current_session_30s_raw,
        client,
    ):
        provider = _stream_provider(client)
        captured = _capture_stream_rows(records, provider)
        merged_30s = dict(current_session_30s_raw or {})
        # Genuine completed TICK-reconstructed bars are authoritative when available.
        merged_30s.update(captured)

        updated = current(records, current_session_raw, merged_30s, client)
        if not captured:
            return updated

        scan_time = datetime.now(timezone.utc)
        cached_provider = _Captured30sProvider(captured)
        enriched = gs396.enrich_records_with_live_30s(
            updated,
            scan_time=scan_time,
            provider=cached_provider,
        )
        canonical = [canonicalize_record(record) for record in enriched]

        diagnostics = getattr(client, "diagnostics", None)
        if isinstance(diagnostics, dict):
            diagnostics["gs397_canonical_30s_tripwire"] = {
                "authority": AUTHORITY,
                "source": SOURCE,
                "captured_symbols": len(captured),
                "canonicalized_records": sum(
                    bool(record.get("supertrend_30s_available")) for record in canonical
                ),
                "fresh_tripwires": sum(
                    fresh_30s_tripwire(record) for record in canonical
                ),
                "attention_role": "investigation only",
                "one_minute_role": "primary ignition unchanged",
                "three_minute_role": "confirmation unchanged",
                "entry_authority_changed": False,
                "qualification_thresholds_changed": False,
                "additional_provider_requests": 0,
            }
        return canonical

    apply_canonical_30s._gs397_canonical_30s = True
    apply_canonical_30s._gs397_original = current
    gs378.apply_live_vwap_truth = apply_canonical_30s


def _install_attention_provenance() -> None:
    """Make a fresh live 30s flip a current reason to investigate, not to enter."""
    from . import gs309_current_attention_mission as attention

    current = attention.current_attention_provenance
    if getattr(current, "_gs397_30s_attention", False):
        return

    @wraps(current)
    def current_attention_provenance(record: dict) -> tuple[str, ...]:
        evidence = list(current(record))
        if fresh_30s_tripwire(record):
            evidence.append(ATTENTION_PROVENANCE)
        return tuple(dict.fromkeys(evidence))

    current_attention_provenance._gs397_30s_attention = True
    current_attention_provenance._gs397_original = current
    attention.current_attention_provenance = current_attention_provenance


def _install_investigation_visibility() -> None:
    """Permit fresh tripwires into the operator view without mutating qualification."""
    from . import ui

    current = ui.is_actionable_candidate
    if getattr(current, "_gs397_30s_investigation", False):
        return

    @wraps(current)
    def is_actionable_candidate(record: dict) -> bool:
        if fresh_30s_tripwire(record):
            return True
        return current(record)

    is_actionable_candidate._gs397_30s_investigation = True
    is_actionable_candidate._gs397_original = current
    ui.is_actionable_candidate = is_actionable_candidate


def install() -> None:
    """Install the GS397 canonical 30s evidence and attention boundary."""
    _install_canonical_stage6_path()
    _install_attention_provenance()
    _install_investigation_visibility()
