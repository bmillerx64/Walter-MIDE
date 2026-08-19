from datetime import datetime, timedelta, timezone

from mide.architecture import ArchitecturePolicy, Decision, WalterArchitectureV1

UTC = timezone.utc


class Store:
    def persist(self, results):
        self.results = results


def _pass(records):
    return {row["symbol"]: Decision(True, "test", "passed") for row in records}


def _architecture(scans):
    base = datetime(2026, 8, 19, 19, 0, tzinfo=UTC)
    arch = WalterArchitectureV1(
        policy=ArchitecturePolicy(.05, 5, 3_500_000),
        discover=lambda: scans.pop(0),
        catalyst=_pass, participation=_pass, expansion=_pass,
        rank=lambda rows: rows, store=Store(), publish=lambda rows: None,
        clock=lambda: base + timedelta(seconds=arch.candidate_ledger.scan_number),
    )
    return arch


def test_candidate_present_on_consecutive_refreshes_is_re_evaluated_each_scan():
    row1 = {"symbol": "RUN", "price": 1.00, "free_float": 1_000_000, "conviction": 30}
    row2 = {"symbol": "RUN", "price": 1.20, "free_float": 1_000_000, "conviction": 40}
    arch = _architecture([[row1], [row2]])
    arch.run()
    record = arch.run()[0]
    assert record["reevaluation_status"] == "REEVALUATED"
    assert record["last_reevaluated_scan"] == 2
    assert record["reevaluation_gap_scans"] == 0
    assert record["consecutive_reevaluations"] == 2
    assert [e["status"] for e in record["reevaluation_history"]] == ["REEVALUATED", "REEVALUATED"]


def test_candidate_missing_from_refresh_is_explicitly_not_re_evaluated():
    row = {"symbol": "DROP", "price": 1.00, "free_float": 1_000_000}
    arch = _architecture([[row], []])
    arch.run()
    record = arch.run()[0]
    assert record["reevaluation_status"] == "NOT_IN_CURRENT_REFRESH"
    assert record["reevaluation_gap_scans"] == 1
    assert record["consecutive_reevaluations"] == 0
    assert record["reevaluation_history"][-1]["status"] == "NOT_IN_CURRENT_REFRESH"


def test_rediscovery_reports_gap_then_resumes_evaluation_without_changing_first_seen():
    row = {"symbol": "BACK", "price": 1.00, "free_float": 1_000_000}
    arch = _architecture([[row], [], [row]])
    first = arch.run()[0]["discovery_first_seen_at"]
    arch.run()
    record = arch.run()[0]
    assert record["discovery_first_seen_at"] == first
    assert record["reevaluation_status"] == "REEVALUATED"
    assert record["reevaluation_gap_scans"] == 1
    assert record["consecutive_reevaluations"] == 1


def test_continuity_observability_does_not_change_qualification_or_rank():
    rows = [
        {"symbol": "ONE", "price": 1.0, "free_float": 1_000_000},
        {"symbol": "TWO", "price": 6.0, "free_float": 1_000_000},
    ]
    arch = _architecture([rows])
    results = arch.run()
    assert [(r["symbol"], r["terminal_stage"], r.get("mission_rank")) for r in results] == [
        ("ONE", "Mission Ranking and Publication", 1),
        ("TWO", "Price Gate", None),
    ]


def test_runtime_dispatch_architecture_remains_transparent_without_ledger_fields():
    expected = {"scan_completed": True, "candidates": ["RUN"]}
    arch = WalterArchitectureV1.for_runtime(lambda: expected)

    # Runtime-dispatch instances intentionally do not construct candidate_ledger,
    # _ledger, or clock. GS292 must preserve that established production contract.
    assert not hasattr(arch, "candidate_ledger")
    assert not hasattr(arch, "_ledger")
    assert arch.run() is expected
