"""Read-only verification and diagnostics for completed Walter scans.

This module deliberately observes the architecture ledger after publication.  It
does not make gate decisions, change membership, sort candidates, or publish data.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from typing import Mapping, Sequence

from mide.architecture import STAGES, TERMINAL_OUTCOMES


TRACE_STAGES = (
    "Universe", "Price", "Validity", "Free Float", "Catalyst",
    "Participation", "Expansion", "Ranking", "Mission", "Outcome",
)

_AUDIT_TO_TRACE = dict(zip(STAGES, TRACE_STAGES[:8]))
_TERMINAL_TO_TRACE = {
    "Qualified and Ranked": "Ranked",
    "Rejected": "Rejected",
    "Technical Failure": "Technical Failure",
}


def _canonical(value: object) -> object:
    """Remove observational timing while retaining every architectural value."""
    if isinstance(value, Mapping):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items())
            if key not in {"timestamp", "execution_time_ms"}
        }
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, set):
        return sorted(_canonical(item) for item in value)
    return value


def replay_snapshot(ledger: Sequence[dict], stages: Sequence[dict]) -> dict:
    """Create a portable, deterministic representation of a completed scan."""
    entries = []
    for record in ledger:
        entries.append({
            "candidate_id": record.get("candidate_id"),
            "symbol": record.get("symbol"),
            "stage_outcomes": _canonical(record.get("architecture_audit", [])),
            "terminal_outcome": record.get("terminal_outcome"),
            "terminal_stage": record.get("terminal_stage"),
            "terminal_category": record.get("terminal_category"),
            "terminal_reason": record.get("terminal_reason"),
            "mission_rank": record.get("mission_rank"),
        })
    entries.sort(key=lambda row: (str(row["candidate_id"]), str(row["symbol"])))
    snapshot = {
        "stage_accounting": _canonical(stages),
        "ledger_entries": entries,
        "mission_order": [
            row["symbol"] for row in sorted(
                (row for row in entries if row["mission_rank"] is not None),
                key=lambda row: int(row["mission_rank"]),
            )
        ],
    }
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)
    snapshot["digest"] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return snapshot


def verify_replay(baseline: Mapping[str, object], replayed: Mapping[str, object]) -> dict:
    """Compare two snapshots without executing or modifying either scan."""
    contracts = ("stage_accounting", "ledger_entries", "mission_order")
    differences = [name for name in contracts if baseline.get(name) != replayed.get(name)]
    return {"passed": not differences, "failed_contracts": differences}


def candidate_trace(ledger: Sequence[dict], symbol: str) -> list[dict]:
    """Return recorded decisions for a symbol; never synthesize a gate reason."""
    normalized = str(symbol).strip().upper()
    matches = [row for row in ledger if str(row.get("symbol", "")).upper() == normalized]
    if len(matches) != 1:
        return []
    record = matches[0]
    audits = {str(row.get("stage")): row for row in record.get("architecture_audit", [])}
    result = []
    terminated = False
    for display, audit_name in zip(TRACE_STAGES[:8], STAGES):
        audit = audits.get(audit_name)
        if audit is None:
            result.append({"stage": display, "status": "SKIPPED", "reason": None})
            continue
        decision = str(audit.get("decision") or "")
        if decision == "Technical Failure":
            status, terminated = "TECHNICAL FAILURE", True
        elif decision in {"Rejected"}:
            status, terminated = "FAIL", True
        elif decision == "Not evaluated":
            status = "SKIPPED"
        else:
            status = "PASS"
        result.append({"stage": display, "status": status, "reason": audit.get("reason")})
    ranked = record.get("terminal_outcome") == "Qualified and Ranked"
    result.append({
        "stage": "Mission", "status": "PASS" if ranked else "SKIPPED",
        "reason": "Recorded mission rank " + str(record["mission_rank"]) if ranked else None,
    })
    outcome = str(record.get("terminal_outcome") or "")
    result.append({
        "stage": "Outcome",
        "status": "TECHNICAL FAILURE" if outcome == "Technical Failure" else "PASS" if outcome else "SKIPPED",
        "reason": record.get("terminal_reason"),
    })
    return result


@dataclass(frozen=True)
class VerificationReport:
    passed: bool
    overall_integrity: int
    contracts: Mapping[str, bool]
    failures: tuple[dict, ...]
    accounting: tuple[dict, ...]
    replay: Mapping[str, object]

    def as_dict(self) -> dict:
        return {
            "passed": self.passed, "overall_integrity": self.overall_integrity,
            "contracts": dict(self.contracts), "failures": list(self.failures),
            "accounting": list(self.accounting), "replay": dict(self.replay),
        }


def verify_architecture(
    ledger: Sequence[dict], stages: Sequence[dict], *,
    purity_observations: Sequence[dict] = (), baseline: Mapping[str, object] | None = None,
) -> VerificationReport:
    """Verify a completed scan and return failures rather than changing runtime."""
    failures: list[dict] = []

    def fail(contract: str, detail: str, symbols: Sequence[str] = ()) -> None:
        failures.append({"contract": contract, "detail": detail, "symbols": list(symbols)})

    accounting = []
    prior_passed = None
    for stage in stages:
        inputs = int(stage.get("input_count", 0))
        passed = int(stage.get("passed_count", stage.get("output_count", 0)))
        rejected = int(stage.get("rejected_count", stage.get("rejection_count", 0)))
        technical = int(stage.get("technical_failure_count", 0))
        row = {"stage": stage.get("stage"), "input_count": inputs, "passed_count": passed,
               "rejected_count": rejected, "technical_failure_count": technical}
        row["balanced"] = inputs == passed + rejected + technical
        accounting.append(row)
        if not row["balanced"]:
            fail("Candidate Accounting", f"Unbalanced stage: {stage.get('stage')}")
        if prior_passed is not None and inputs > prior_passed:
            fail("Monotonic Membership", f"Membership increased at {stage.get('stage')}")
        prior_passed = passed
    if [row["stage"] for row in accounting] != list(STAGES):
        fail("Architecture Integrity", "Stage sequence is incomplete or out of order")

    identities = [(str(row.get("symbol") or ""), str(row.get("candidate_id") or "")) for row in ledger]
    duplicate_ids = sorted(identity for identity in {item[1] for item in identities} if identity and sum(x[1] == identity for x in identities) > 1)
    bad_identity = [symbol for symbol, identity in identities if not identity or symbol != identity]
    if duplicate_ids:
        fail("Ledger Integrity", "Duplicate candidate identities", duplicate_ids)
    if bad_identity:
        fail("Ledger Integrity", "Candidate identity was missing or recreated", bad_identity)
    silent = [str(row.get("symbol")) for row in ledger if row.get("terminal_outcome") not in TERMINAL_OUTCOMES]
    if silent:
        fail("No Silent Losses", "Candidates lack exactly one terminal state", silent)
    inaccurate = [str(row.get("symbol")) for row in ledger if len(candidate_trace(ledger, str(row.get("symbol")))) != len(TRACE_STAGES)]
    if inaccurate:
        fail("Trace Accuracy", "Candidate trace is incomplete or ambiguous", inaccurate)
    for observation in purity_observations:
        if observation.get("violation"):
            fail("Stage Purity", str(observation["violation"]), observation.get("symbols", ()))

    snapshot = replay_snapshot(ledger, stages)
    replay_result = {"passed": True, "failed_contracts": []}
    if baseline is not None:
        replay_result = verify_replay(baseline, snapshot)
        if not replay_result["passed"]:
            fail("Replay Integrity", "Replay differs from completed scan: " + ", ".join(replay_result["failed_contracts"]))
    contract_names = (
        *TRACE_STAGES, "Candidate Accounting", "Ledger Integrity", "Replay Integrity",
        "Monotonic Membership", "No Silent Losses", "Stage Purity", "Trace Accuracy",
    )
    contracts = {name: not any(item["contract"] == name for item in failures) for name in contract_names}
    # A general architecture failure affects the named stage display as a whole.
    if any(item["contract"] == "Architecture Integrity" for item in failures):
        contracts = {name: False for name in contracts}
    score = round(100 * sum(contracts.values()) / len(contracts)) if contracts else 100
    return VerificationReport(not failures, score, contracts, tuple(failures), tuple(accounting), replay_result)
