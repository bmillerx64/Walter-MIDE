from itertools import groupby

from mide.decision_engine import evaluate


def test_candidates_move_through_each_stage_exactly_once_and_only_from_prior_output():
    candidates = [
        {
            "symbol": "STAGE2",
            "tradable": False,
            "price": 1.25,
            "float_shares": 1_000_000,
        },
        {
            "symbol": "STAGE3",
            "price": 1.25,
            "float_shares": 1_000_000,
            "participation_score": 0,
            "structure_score": 0,
            "vwap_relation": "below",
            "vwap_distance_pct": -3,
            "supertrend_distance_pct": 5,
            "momentum_quality_score": 0,
        },
        {
            "symbol": "ADVANCES",
            "price": 1.25,
            "float_shares": 1_000_000,
            "participation_score": 90,
            "structure_score": 90,
            "vwap_relation": "above",
            "supertrend_bullish": True,
            "momentum_quality_score": 90,
        },
    ]

    evaluated = evaluate(candidates)
    by_symbol = {record["symbol"]: record for record in evaluated}

    # No candidate may disappear from, enter midway through, or duplicate itself in
    # the funnel. The decision engine may enrich a record, but its input identity
    # must survive unchanged into the corresponding output record.
    assert list(by_symbol) == [candidate["symbol"] for candidate in candidates]
    for candidate in candidates:
        assert candidate.items() <= by_symbol[candidate["symbol"]].items()

    stage_inputs = {
        stage: [
            record["symbol"]
            for record in evaluated
            if any(step["stage"] == stage for step in record["decision_funnel"])
        ]
        for stage in (1, 2, 3)
    }
    stage_outputs = {
        stage: [
            record["symbol"]
            for record in evaluated
            if all(
                step["passed"]
                for step in record["decision_funnel"]
                if step["stage"] == stage
            )
        ]
        for stage in (1, 2, 3)
    }

    assert stage_inputs[1] == [candidate["symbol"] for candidate in candidates]
    assert stage_inputs[2] == stage_outputs[1]
    assert stage_inputs[3] == stage_outputs[2]

    for record in evaluated:
        traversed = [
            stage
            for stage, _steps in groupby(
                step["stage"] for step in record["decision_funnel"]
            )
        ]
        assert traversed == list(range(1, traversed[-1] + 1))
import json

import pytest

from mide.architecture import (
    ArchitecturePolicy,
    ArchitectureViolation,
    Decision,
    STAGES,
    WalterArchitectureV1,
    scanner_implementation,
)
from mide.operational_validation import validate_runtime


class Store:
    def __init__(self, events):
        self.events = events
        self.results = None

    def persist(self, results):
        self.events.append("persist")
        self.results = results


def passing(records):
    return {item["symbol"]: Decision(True, "assessment", "passed") for item in records}


def pipeline(records, *, catalyst=passing, participation=passing, expansion=passing, rank=None):
    events = []
    store = Store(events)
    architecture = WalterArchitectureV1(
        policy=ArchitecturePolicy(0.05, 5.0, 3_500_000),
        discover=lambda: records,
        catalyst=catalyst,
        participation=participation,
        expansion=expansion,
        rank=rank or (lambda candidates: list(reversed(candidates))),
        store=store,
        publish=lambda _: events.append("publish"),
    )
    return architecture, store, events


def test_all_eight_stages_execute_once_in_order_and_counts_never_increase():
    records = [
        {"symbol": "AAA", "price": 1, "free_float": 1_000_000},
        {"symbol": "AAA", "price": 1, "free_float": 1_000_000},
        {"symbol": "PRICE", "price": 7, "free_float": 1_000_000},
        {"symbol": "HALT", "price": 2, "free_float": 2_000_000,
         "halted": True, "halt_type": "LUDP", "halt_status": "active"},
        {"symbol": "FLOAT", "price": 2, "free_float": 9_000_000},
    ]
    architecture, store, events = pipeline(records)
    results = architecture.run()
    assert [event["stage"] for event in architecture.trace] == list(STAGES)
    assert all(event["executions"] == 1 for event in architecture.trace)
    assert [event["output_count"] for event in architecture.trace] == [4, 3, 3, 2, 2, 2, 2, 2]
    assert events == ["persist", "publish"]
    assert store.results is results
    assert {item["terminal_outcome"] for item in results} == {"Rejected", "Qualified and Ranked"}
    halted = next(item for item in results if item["symbol"] == "HALT")
    assert (halted["halted"], halted["halt_type"], halted["halt_status"]) == (True, "LUDP", "active")


def test_assessments_only_receive_preceding_output_and_catalyst_runs_once():
    calls = []

    def stage(name, reject=None):
        def assess(records):
            calls.append((name, [item["symbol"] for item in records]))
            return {
                item["symbol"]: Decision(item["symbol"] != reject, name, "policy")
                for item in records
            }
        return assess

    records = [
        {"symbol": "A", "price": 1, "free_float": 1},
        {"symbol": "B", "price": 1, "free_float": 1},
    ]
    architecture, _, _ = pipeline(
        records,
        catalyst=stage("catalyst", "B"),
        participation=stage("participation"),
        expansion=stage("expansion"),
    )
    architecture.run()
    assert calls == [
        ("catalyst", ["A", "B"]),
        ("participation", ["A"]),
        ("expansion", ["A"]),
    ]


def test_participation_trace_has_rule_histogram_symbols_and_exact_failed_metrics():
    def participation(records):
        decisions = {}
        for item in records:
            symbol = item["symbol"]
            if symbol in {"VOL1", "VOL2"}:
                decisions[symbol] = Decision(
                    False, "Participation", "Average volume below threshold",
                    evidence={"failed_metrics": [{
                        "metric": "volume", "measured": item["volume"],
                        "operator": "<", "threshold": 100_000,
                    }]},
                )
            else:
                decisions[symbol] = Decision(
                    False, "Participation", "RVOL unavailable",
                    evidence={"failed_metrics": [{
                        "metric": "rvol", "measured": None,
                        "operator": "unavailable", "threshold": 1.5,
                    }]},
                )
        return decisions

    records = [
        {"symbol": "VOL1", "price": 1, "free_float": 1, "volume": 10},
        {"symbol": "VOL2", "price": 1, "free_float": 1, "volume": 20},
        {"symbol": "NORVOL", "price": 1, "free_float": 1, "volume": 200_000},
    ]
    architecture, _, _ = pipeline(records, participation=participation)

    architecture.run()

    trace = next(
        row for row in architecture.trace if row["stage"] == "Participation Assessment"
    )
    assert trace["input_count"] == trace["rejection_count"] == 3
    assert trace["distinct_rejection_rules"] == 2
    assert trace["all_rejections_same_rule"] is False
    assert trace["rejection_histogram"] == [
        {
            "reason": "Average volume below threshold", "count": 2,
            "representative_symbols": ["VOL1", "VOL2"],
            "failed_metrics": [
                {"symbol": "VOL1", "metric": "volume", "measured": 10,
                 "operator": "<", "threshold": 100_000},
                {"symbol": "VOL2", "metric": "volume", "measured": 20,
                 "operator": "<", "threshold": 100_000},
            ],
        },
        {
            "reason": "RVOL unavailable", "count": 1,
            "representative_symbols": ["NORVOL"],
            "failed_metrics": [{
                "symbol": "NORVOL", "metric": "rvol", "measured": None,
                "operator": "unavailable", "threshold": 1.5,
            }],
        },
    ]


def test_market_data_hook_receives_only_price_gate_survivors():
    retrieved = []
    architecture, _, _ = pipeline([
        {"symbol": "KEEP", "price": 1, "free_float": 1},
        {"symbol": "DROP", "price": 8, "free_float": 1},
    ])
    architecture.after_price_gate = lambda records: retrieved.extend(
        item["symbol"] for item in records
    )

    results = architecture.run()

    assert retrieved == ["KEEP"]
    assert next(item for item in results if item["symbol"] == "DROP")["terminal_stage"] == "Price Gate"
    assert [item["stage"] for item in architecture.trace] == list(STAGES)


def test_rejection_and_technical_failure_have_stage_category_and_reason():
    records = [
        {"symbol": "BAD", "price": None, "free_float": 1},
        {"symbol": "FAIL", "price": 1, "free_float": 1},
    ]

    def failure(records):
        raise RuntimeError("provider unavailable")

    architecture, _, _ = pipeline(records, catalyst=failure)
    results = architecture.run()
    for result in results:
        assert result["terminal_outcome"] in {"Rejected", "Technical Failure"}
        assert result["terminal_stage"]
        assert result["terminal_category"]
        assert result["terminal_reason"]


def test_news_or_ranking_cannot_add_or_silently_remove_symbols():
    records = [{"symbol": "A", "price": 1, "free_float": 1}]

    def news_adds_symbol(items):
        return {"A": Decision(True, "Catalyst", "found"), "NEW": Decision(True, "Catalyst", "found")}

    architecture, _, _ = pipeline(records, catalyst=news_adds_symbol)
    with pytest.raises(ArchitectureViolation, match="every and only"):
        architecture.run()

    architecture, _, _ = pipeline(records, rank=lambda _: [])
    with pytest.raises(ArchitectureViolation, match="preserve"):
        architecture.run()


def test_manifest_matches_runtime_and_ui_selection_is_exact():
    with open("docs/walter-architecture-v1.0.json", encoding="utf-8") as source:
        manifest = json.load(source)
    assert [item["name"] for item in manifest["stages"]] == list(STAGES)
    assert scanner_implementation("Walter Architecture v1.0") is WalterArchitectureV1
    with pytest.raises(KeyError):
        scanner_implementation("unknown")


def test_ledger_has_complete_audit_and_no_candidate_can_disappear():
    records = [
        {"symbol": " pass ", "price": 1, "free_float": 1, "source": "test-feed"},
        {"symbol": "reject", "price": 9, "free_float": 1},
    ]
    architecture, _, _ = pipeline(records)

    results = architecture.run()

    assert {item["symbol"] for item in results} == {"PASS", "REJECT"}
    assert all([entry["stage"] for entry in item["architecture_audit"]] == list(STAGES)
               for item in results)
    assert all(set(entry) == {
        "stage", "input_status", "decision", "evidence", "reason",
        "provenance", "timestamp",
    } for item in results for entry in item["architecture_audit"])
    rejected = next(item for item in results if item["symbol"] == "REJECT")
    assert rejected["terminal_stage"] == "Price Gate"
    assert rejected["terminal_reason"] == "Price outside configured range"
    assert rejected["architecture_audit"][1]["decision"] == "Rejected"


def test_candidate_exception_is_contained_and_identity_survives_ranking():
    records = [
        {"symbol": "GOOD", "price": 1, "free_float": 1},
        {"symbol": "BROKEN", "price": 1, "free_float": 1},
    ]

    def candidate_sensitive_stage(items):
        if any(item["symbol"] == "BROKEN" for item in items):
            raise ValueError("bad candidate payload")
        return passing(items)

    architecture, _, _ = pipeline(records, catalyst=candidate_sensitive_stage)
    results = architecture.run()
    by_symbol = {item["symbol"]: item for item in results}

    assert by_symbol["BROKEN"]["terminal_outcome"] == "Technical Failure"
    assert by_symbol["BROKEN"]["terminal_stage"] == "Catalyst Assessment"
    assert "bad candidate payload" in by_symbol["BROKEN"]["terminal_reason"]
    assert by_symbol["GOOD"]["terminal_outcome"] == "Qualified and Ranked"
    assert by_symbol["GOOD"]["candidate_id"] == "GOOD"


def test_persisted_ledger_precedes_and_exclusively_controls_publication():
    events = []
    persisted = []
    published = []

    class CapturingStore:
        def persist(self, results):
            events.append("persist")
            persisted.extend(results)

    architecture = WalterArchitectureV1(
        policy=ArchitecturePolicy(0.05, 5.0, 3_500_000),
        discover=lambda: [
            {"symbol": "QUALIFIED", "price": 1, "free_float": 1},
            {"symbol": "REJECTED", "price": 10, "free_float": 1},
        ],
        catalyst=passing, participation=passing, expansion=passing,
        rank=lambda records: records, store=CapturingStore(),
        publish=lambda records: (events.append("publish"), published.extend(records)),
    )
    results = architecture.run()

    assert events == ["persist", "publish"]
    assert persisted == results
    expected = {
        id(item) for item in persisted
        if item["terminal_outcome"] == "Qualified and Ranked"
    }
    assert {id(item) for item in published} == expected
    assert {item["symbol"] for item in published} == {"QUALIFIED"}
    assert architecture.operational_summary["publication_integrity_verified"] is True
    assert architecture.operational_summary["symbols_published"] == 1


def test_operational_metrics_cover_timing_counts_rejections_and_failures():
    ticks = iter(range(100))
    records = [
        {"symbol": "GOOD", "price": 1, "free_float": 1},
        {"symbol": "REJECT", "price": 10, "free_float": 1},
    ]
    architecture, _, _ = pipeline(records)
    architecture.timer = lambda: next(ticks)

    architecture.run()

    assert len(architecture.trace) == 8
    assert all(stage["execution_time_ms"] == 1000 for stage in architecture.trace)
    assert all(
        {"input_count", "output_count", "rejection_count", "technical_failure_count"}
        <= set(stage) for stage in architecture.trace
    )
    assert architecture.operational_summary["symbols_rejected_by_stage"] == {
        "Price Gate": 1
    }


def test_missing_snapshot_identity_reaches_price_gate_before_rejection():
    observed = {}
    architecture, _, _ = pipeline([{
        "symbol": "NO_DATA", "price": None, "snapshot_status": "unavailable",
        "data_usable": False,
    }])
    architecture.stage_observer = lambda number, stage, records: observed.setdefault(
        stage, [record["symbol"] for record in records]
    )

    architecture.run()

    assert observed["Price Gate"] == ["NO_DATA"]
    record = architecture.candidate_ledger.records["NO_DATA"]
    assert record["terminal_stage"] == "Price Gate"
    assert record["terminal_reason"] == "Usable price unavailable"


def test_validation_framework_rejects_growth_disappearance_and_publication_drift():
    ledger = [{
        "symbol": "A", "candidate_id": "A", "terminal_outcome": "Qualified and Ranked",
        "mission_rank": 1,
    }]
    stages = [
        {"stage": name, "output_count": 1, "input_count": 1}
        for name in STAGES
    ]
    assert validate_runtime(
        ledger=ledger, published=ledger, stages=stages, persistence_completed=True,
    )["healthy"] is True

    growing = [dict(stage) for stage in stages]
    growing[3]["output_count"] = 2
    with pytest.raises(ArchitectureViolation, match="membership increased"):
        validate_runtime(
            ledger=ledger, published=ledger, stages=growing,
            persistence_completed=True,
        )
    with pytest.raises(ArchitectureViolation, match="does not match"):
        validate_runtime(
            ledger=ledger, published=[], stages=stages, persistence_completed=True,
        )
    with pytest.raises(ArchitectureViolation, match="Persistence"):
        validate_runtime(
            ledger=ledger, published=ledger, stages=stages,
            persistence_completed=False,
        )
