"""Runtime invariants and health reporting for the Walter architecture."""

from __future__ import annotations

from collections import Counter
from typing import Mapping, Sequence

from mide.architecture import ArchitectureViolation, STAGES, TERMINAL_OUTCOMES


def _identity(record: Mapping[str, object]) -> tuple[str, str]:
    return (str(record.get("symbol") or ""), str(record.get("candidate_id") or ""))


def validate_runtime(
    *, ledger: Sequence[dict], published: Sequence[dict], stages: Sequence[dict],
    persistence_completed: bool,
) -> dict:
    """Validate a completed scan and return a dashboard-ready health summary.

    Raises ``ArchitectureViolation`` rather than allowing corrupt or unpersisted
    mission data to be presented as a successful scan.
    """
    if [stage.get("stage") for stage in stages] != list(STAGES):
        raise ArchitectureViolation("Operational trace must contain all eight stages in order")
    counts = [int(stage.get("output_count", 0)) for stage in stages]
    if any(later > earlier for earlier, later in zip(counts, counts[1:])):
        raise ArchitectureViolation("Stage membership increased after Universe Construction")
    if not persistence_completed:
        raise ArchitectureViolation("Persistence must complete before publication")
    if any(record.get("terminal_outcome") not in TERMINAL_OUTCOMES for record in ledger):
        raise ArchitectureViolation("Candidate disappeared without a terminal ledger outcome")

    qualified = sorted(
        (record for record in ledger if record.get("terminal_outcome") == "Qualified and Ranked"),
        key=lambda record: int(record.get("mission_rank", 0)),
    )
    if [_identity(record) for record in published] != [_identity(record) for record in qualified]:
        raise ArchitectureViolation("Published mission does not match the Stage 8 ledger")
    # Publication must receive the persisted authoritative objects, not merely
    # records that happen to share their symbol text.
    if [id(record) for record in published] != [id(record) for record in qualified]:
        raise ArchitectureViolation("Publication did not preserve ledger identity")

    outcomes = Counter(str(record.get("terminal_outcome")) for record in ledger)
    rejected_by_stage = Counter(
        str(record.get("terminal_stage"))
        for record in ledger if record.get("terminal_outcome") == "Rejected"
    )
    return {
        "healthy": True,
        "pipeline_complete": True,
        "execution_completed_without_uncaught_exceptions": True,
        "persistence_completed_before_publication": True,
        "publication_integrity_verified": True,
        "symbols_discovered": len(ledger),
        "symbols_rejected": outcomes["Rejected"],
        "symbols_rejected_by_stage": dict(rejected_by_stage),
        "symbols_ranked": outcomes["Qualified and Ranked"],
        "symbols_published": len(published),
        "technical_failures": outcomes["Technical Failure"],
        "stage_metrics": [dict(stage) for stage in stages],
    }
