from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Iterable


STATUS_HEALTHY = "HEALTHY SCAN"
STATUS_EMPTY = "VALID EMPTY PASS"
STATUS_DEGRADED = "DEGRADED DATA"
STATUS_FAILURE = "PROVIDER / PIPELINE FAILURE"
STATUS_AWAITING = "AWAITING SCAN"

REQUIRED_RECORD_FIELDS = ("symbol", "price", "volume", "timestamp")
DECISION_EVIDENCE_FIELDS = (
    "vwap_relation",
    "participation_score",
    "expansion_quality",
)


def _valid_number(value: object, *, positive: bool) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value) and (value > 0 if positive else value >= 0)


def _utc_now(now: datetime | None) -> datetime:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def record_integrity(
    record: dict,
    *,
    now: datetime | None = None,
    max_age_seconds: int = 300,
) -> dict:
    """Describe one record's data quality without changing the record."""
    current_time = _utc_now(now)
    symbol = record.get("symbol")
    valid_symbol = isinstance(symbol, str) and bool(symbol.strip())
    price_valid = _valid_number(record.get("price"), positive=True)
    volume_valid = _valid_number(record.get("volume"), positive=False)
    timestamp_present = record.get("timestamp") is not None
    parsed_timestamp = _parse_timestamp(record.get("timestamp"))
    timestamp_parseable = parsed_timestamp is not None
    age_seconds = (
        (current_time - parsed_timestamp).total_seconds()
        if parsed_timestamp is not None
        else None
    )
    fresh = (
        age_seconds is not None
        and -30 <= age_seconds <= max_age_seconds
    )
    evidence_count = sum(record.get(field) is not None for field in DECISION_EVIDENCE_FIELDS)
    decision_evidence_present = evidence_count / len(DECISION_EVIDENCE_FIELDS) * 100
    missing_fields = [field for field in REQUIRED_RECORD_FIELDS if record.get(field) is None]
    issues: list[str] = []
    if not valid_symbol:
        issues.append("invalid symbol")
    if not price_valid:
        issues.append("invalid price")
    if not volume_valid:
        issues.append("invalid volume")
    if not timestamp_present:
        issues.append("missing timestamp")
    elif not timestamp_parseable:
        issues.append("unparseable timestamp")
    elif not fresh:
        issues.append("stale timestamp")

    return {
        "symbol": symbol,
        "valid_symbol": valid_symbol,
        "price_valid": price_valid,
        "volume_valid": volume_valid,
        "timestamp_present": timestamp_present,
        "timestamp_parseable": timestamp_parseable,
        "age_seconds": age_seconds,
        "fresh": fresh,
        "decision_evidence_present": decision_evidence_present,
        "missing_fields": missing_fields,
        "issues": issues,
        "record_ok": valid_symbol and price_valid and volume_valid and timestamp_parseable and fresh,
    }


def records_integrity(
    records: Iterable[dict],
    *,
    now: datetime | None = None,
    max_age_seconds: int = 300,
) -> dict:
    """Aggregate immutable record-level diagnostics."""
    current_time = _utc_now(now)
    results = [
        record_integrity(record, now=current_time, max_age_seconds=max_age_seconds)
        for record in records
    ]
    symbols = [result["symbol"] for result in results if result["valid_symbol"]]
    symbol_counts = {symbol: symbols.count(symbol) for symbol in set(symbols)}
    duplicates = sorted(symbol for symbol, count in symbol_counts.items() if count > 1)
    parseable_count = sum(result["timestamp_parseable"] for result in results)
    fresh_count = sum(result["fresh"] for result in results)
    valid_count = sum(result["record_ok"] for result in results)
    count = len(results)
    issues_by_symbol: dict[str, list[str]] = {}
    for index, result in enumerate(results):
        if result["issues"]:
            key = str(result["symbol"]) if result["valid_symbol"] else f"<record {index + 1}>"
            issues_by_symbol.setdefault(key, []).extend(result["issues"])
    for symbol in duplicates:
        issues_by_symbol.setdefault(str(symbol), []).append("duplicate symbol")

    return {
        "record_count": count,
        "unique_symbols": len(symbol_counts),
        "duplicate_symbols": duplicates,
        "valid_record_count": valid_count,
        "invalid_record_count": count - valid_count,
        "fresh_record_count": fresh_count,
        "stale_record_count": parseable_count - fresh_count,
        "missing_timestamp_count": sum(not result["timestamp_present"] for result in results),
        "average_decision_evidence_pct": (
            sum(result["decision_evidence_present"] for result in results) / count
            if count else 100.0
        ),
        "record_integrity_pct": valid_count / count * 100 if count else 100.0,
        "freshness_pct": fresh_count / parseable_count * 100 if parseable_count else None,
        "issues_by_symbol": issues_by_symbol,
    }


def _explicit_provider_failure(provider_diagnostics: dict | None) -> bool:
    if not provider_diagnostics:
        return False
    return (
        provider_diagnostics.get("ok") is False
        or provider_diagnostics.get("success") is False
        or bool(provider_diagnostics.get("error"))
    )


def _empty_pass_reason(funnel: dict) -> str:
    stage_labels = (
        ("price", "Price Gate"),
        ("tradability", "Validity Gate"),
        ("free_float", "Free-Float Gate"),
        ("stage_3_analysis", "Catalyst Assessment"),
        ("monitored", "Participation Assessment"),
        ("entry_ready", "Expansion Assessment"),
        ("candidates", "Mission Ranking"),
        ("candidate_count", "Mission Ranking"),
    )
    for key, label in stage_labels:
        if key not in funnel:
            continue
        count = funnel.get(key)
        if count == 0:
            return f"No symbols survived {label}."
    return "Upstream data arrived, but no symbols passed downstream filters."


def scan_integrity_report(
    records: Iterable[dict],
    *,
    live: bool,
    funnel_counts: dict | None = None,
    provider_diagnostics: dict | None = None,
    now: datetime | None = None,
    scan_completed: bool | None = None,
) -> dict:
    """Classify scan trust without affecting any scanner decision."""
    record_list = list(records)
    aggregate = records_integrity(record_list, now=now)
    source_funnel = funnel_counts or {}
    measured = scan_completed if scan_completed is not None else bool(
        record_list or funnel_counts is not None or provider_diagnostics is not None
    )
    if not measured:
        return {
            "status": STATUS_AWAITING,
            "status_reason": "No completed scan has been measured yet.",
            "trust_score": None,
            "live": live,
            "funnel": {},
            **aggregate,
            "record_integrity_pct": None,
            "freshness_pct": None,
            "warnings": [],
            "failures": [],
            "empty_pass": False,
            "provider_failure": False,
            "measured": False,
        }
    funnel_keys = (
        "universe", "tradability", "price", "free_float", "stage_3_analysis",
        "monitored", "entry_ready", "free_float_lookup_failures",
        "free_float_actual_failures", "snapshots_requested", "snapshots_received",
        "snapshot_symbols_requested", "snapshot_symbols_received",
        "prefilter", "prefiltered", "prefilter_count", "candidates",
        "candidate_count",
    )
    funnel = {key: source_funnel[key] for key in funnel_keys if key in source_funnel}
    requested = funnel.get("snapshots_requested", funnel.get("snapshot_symbols_requested"))
    received = funnel.get("snapshots_received", funnel.get("snapshot_symbols_received"))
    provider_failure = (
        (live and funnel.get("universe") == 0)
        or (requested is not None and requested > 0 and received == 0)
        or _explicit_provider_failure(provider_diagnostics)
    )
    lookup_failures = funnel.get("free_float_lookup_failures", 0) or 0
    degraded = (
        aggregate["record_count"] > 0
        and (
            aggregate["record_integrity_pct"] < 99
            or (
                aggregate["freshness_pct"] is not None
                and aggregate["freshness_pct"] < 99
            )
            or lookup_failures > 0
        )
    )
    downstream_keys = (
        "tradability", "price", "free_float", "prefilter", "prefiltered",
        "prefilter_count", "stage_3_analysis", "monitored", "entry_ready",
        "candidates", "candidate_count",
    )
    downstream_zero = any(funnel.get(key) == 0 for key in downstream_keys if key in funnel)
    empty_pass = (
        not provider_failure
        and funnel.get("universe") is not None
        and funnel["universe"] > 0
        and (aggregate["record_count"] == 0 or downstream_zero)
    )

    warnings: list[str] = []
    failures: list[str] = []
    if live and funnel.get("universe") == 0:
        failures.append("Live provider returned an empty universe.")
    if requested is not None and requested > 0 and received == 0:
        failures.append("Snapshot pipeline requested data but received none.")
    if _explicit_provider_failure(provider_diagnostics):
        failures.append("Provider diagnostics reported an explicit error.")
    if aggregate["record_integrity_pct"] < 99:
        warnings.append("One or more records failed integrity checks.")
    if aggregate["freshness_pct"] is not None and aggregate["freshness_pct"] < 99:
        warnings.append("One or more timestamped records are stale.")
    if lookup_failures > 0:
        warnings.append("Free-float lookups were incomplete.")
    if aggregate["duplicate_symbols"]:
        warnings.append("Duplicate symbols were observed.")

    if provider_failure:
        status = STATUS_FAILURE
        reason = failures[0]
    elif degraded:
        status = STATUS_DEGRADED
        reason = warnings[0]
    elif empty_pass:
        status = STATUS_EMPTY
        reason = _empty_pass_reason(funnel)
    else:
        status = STATUS_HEALTHY
        reason = "Upstream data and record quality checks passed."

    trust_score = 100.0
    if provider_failure:
        trust_score -= 40
    trust_score -= min(25, (100 - aggregate["record_integrity_pct"]) * 0.25)
    if aggregate["freshness_pct"] is not None:
        trust_score -= min(20, (100 - aggregate["freshness_pct"]) * 0.2)
    if lookup_failures > 0:
        trust_score -= 10
    if aggregate["duplicate_symbols"]:
        trust_score -= 5

    return {
        "status": status,
        "status_reason": reason,
        "trust_score": round(max(0.0, min(100.0, trust_score)), 1),
        "live": live,
        "funnel": funnel,
        **aggregate,
        "warnings": warnings,
        "failures": failures,
        "empty_pass": empty_pass,
        "provider_failure": provider_failure,
        "measured": True,
    }
