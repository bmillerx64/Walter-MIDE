from copy import deepcopy

from mide.architecture import ArchitecturePolicy, Decision, WalterArchitectureV1
from mide.architecture_verification import (
    TRACE_STAGES,
    candidate_trace,
    replay_snapshot,
    verify_architecture,
    verify_replay,
)


class Store:
    def persist(self, _records):
        pass


def _pass(records):
    return {row["symbol"]: Decision(True, "assessment", "recorded pass") for row in records}


def _scan(records, *, catalyst=_pass):
    architecture = WalterArchitectureV1(
        policy=ArchitecturePolicy(.05, 5, 3_500_000),
        discover=lambda: deepcopy(records), catalyst=catalyst,
        participation=_pass, expansion=_pass, rank=lambda rows: rows,
        store=Store(), publish=lambda _rows: None,
    )
    return architecture, architecture.run()


def test_accounting_balances_and_membership_is_monotonic():
    architecture, ledger = _scan([
        {"symbol": "GOOD", "price": 1, "free_float": 1},
        {"symbol": "PRICE", "price": 10, "free_float": 1},
    ])
    report = verify_architecture(ledger, architecture.trace)
    assert all(
        row["input_count"] == row["passed_count"] + row["rejected_count"]
        + row["technical_failure_count"]
        for row in report.accounting
    )
    assert report.contracts["Candidate Accounting"]
    assert report.contracts["Monotonic Membership"]


def test_no_silent_losses_and_identity_persistence():
    architecture, ledger = _scan([{"symbol": "ONE", "price": 1, "free_float": 1}])
    report = verify_architecture(ledger, architecture.trace)
    assert report.contracts["No Silent Losses"]
    assert report.contracts["Ledger Integrity"]
    assert ledger[0]["candidate_id"] == ledger[0]["symbol"] == "ONE"


def test_replay_is_deterministic_and_detects_mission_order_drift():
    first, first_ledger = _scan([
        {"symbol": "A", "price": 1, "free_float": 1},
        {"symbol": "B", "price": 1, "free_float": 1},
    ])
    second, second_ledger = _scan([
        {"symbol": "A", "price": 1, "free_float": 1},
        {"symbol": "B", "price": 1, "free_float": 1},
    ])
    baseline = replay_snapshot(first_ledger, first.trace)
    replayed = replay_snapshot(second_ledger, second.trace)
    assert verify_replay(baseline, replayed)["passed"]
    replayed["mission_order"] = list(reversed(replayed["mission_order"]))
    assert verify_replay(baseline, replayed) == {
        "passed": False, "failed_contracts": ["mission_order"]
    }


def test_stage_purity_violation_is_prevented_without_changing_decision():
    def impure(records):
        return {
            row["symbol"]: Decision(True, "Catalyst", "recorded pass", {"mission_rank": 99})
            for row in records
        }

    architecture, ledger = _scan(
        [{"symbol": "PURE", "price": 1, "free_float": 1}], catalyst=impure
    )
    report = verify_architecture(
        ledger, architecture.trace, purity_observations=architecture.purity_observations
    )
    assert report.contracts["Stage Purity"]
    assert report.failures == []
    # Ranking remains authoritative because the illicit Catalyst-owned update is
    # removed before it can mutate the candidate ledger.
    assert ledger[0]["mission_rank"] == 1


def test_candidate_trace_is_exact_and_diagnostics_are_read_only():
    architecture, ledger = _scan([
        {"symbol": "DROP", "price": 10, "free_float": 1},
        {"symbol": "PASS", "price": 1, "free_float": 1},
    ])
    before = deepcopy(ledger)
    trace = candidate_trace(ledger, "drop")
    report = verify_architecture(ledger, architecture.trace)
    assert [row["stage"] for row in trace] == list(TRACE_STAGES)
    assert trace[1] == {
        "stage": "Price", "status": "FAIL",
        "reason": "Price outside configured range",
    }
    assert trace[2]["status"] == "SKIPPED"
    assert report.contracts["Trace Accuracy"]
    assert ledger == before
