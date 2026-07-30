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
