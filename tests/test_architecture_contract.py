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
