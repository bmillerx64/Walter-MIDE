from mide.architecture import ArchitecturePolicy, Decision, STAGES, WalterArchitectureV1


class Store:
    def __init__(self):
        self.results = None

    def persist(self, results):
        self.results = results


def _pipeline(records, *, catalyst_scores):
    store = Store()

    def catalyst(items):
        decisions = {}
        for item in items:
            symbol = item["symbol"]
            score = catalyst_scores.get(symbol, 0)
            updates = {}
            if score:
                updates = {
                    "headline": f"{symbol} announces material company news",
                    "catalyst_score": score,
                }
            decisions[symbol] = Decision(True, "Catalyst", "assessed", updates)
        return decisions

    def free_float(items):
        result = {}
        for item in items:
            value = float(item["float_shares"])
            passed = value <= 3_500_000
            result[item["symbol"]] = Decision(
                passed,
                "Free Float",
                "Free float within configured limit" if passed else "Free float exceeds configured limit",
                {"free_float_verified": True},
            )
        return result

    passing = lambda items: {
        item["symbol"]: Decision(True, "assessment", "passed") for item in items
    }

    architecture = WalterArchitectureV1(
        policy=ArchitecturePolicy(0.05, 5.0, 3_500_000),
        discover=lambda: records,
        catalyst=catalyst,
        free_float=free_float,
        participation=passing,
        expansion=passing,
        rank=lambda items: list(items),
        store=store,
        publish=lambda items: None,
    )
    result = architecture.run()
    return architecture, result


def test_route_places_catalyst_before_free_float_in_production_contract():
    assert STAGES[3:5] == ("Catalyst Assessment", "Free-Float Gate")


def test_low_float_candidate_remains_normal_squeeze_lane():
    architecture, result = _pipeline(
        [{"symbol": "TINY", "price": 1.0, "float_shares": 2_000_000}],
        catalyst_scores={"TINY": 0},
    )
    record = next(item for item in result if item["symbol"] == "TINY")
    assert record.get("float_gate_bypass") is not True
    assert record.get("strategy_lane") != "CATALYST_MOMENTUM"
    assert record["terminal_outcome"] == "Qualified and Ranked"


def test_plag_style_larger_float_with_material_catalyst_reaches_participation():
    architecture, result = _pipeline(
        [{"symbol": "PLAG", "price": 1.0, "float_shares": 11_500_000}],
        catalyst_scores={"PLAG": 9},
    )
    record = next(item for item in result if item["symbol"] == "PLAG")
    assert record["strategy_lane"] == "CATALYST_MOMENTUM"
    assert record["float_gate_bypass"] is True
    assert record["squeeze_eligible"] is False
    assert record["terminal_outcome"] == "Qualified and Ranked"
    stages = [step["stage"] for step in record["architecture_audit"]]
    assert stages.index("Catalyst Assessment") < stages.index("Free-Float Gate")
    assert "Participation Assessment" in stages
    assert "Expansion Assessment" in stages


def test_larger_float_without_material_catalyst_is_still_rejected():
    architecture, result = _pipeline(
        [{"symbol": "BIG", "price": 1.0, "float_shares": 11_500_000}],
        catalyst_scores={"BIG": 0},
    )
    record = next(item for item in result if item["symbol"] == "BIG")
    assert record.get("float_gate_bypass") is not True
    assert record["terminal_outcome"] == "Rejected"
    assert record["terminal_stage"] == "Free-Float Gate"


def test_weak_headline_score_does_not_bypass_float_gate():
    architecture, result = _pipeline(
        [{"symbol": "WEAK", "price": 1.0, "float_shares": 11_500_000}],
        catalyst_scores={"WEAK": 6.9},
    )
    record = next(item for item in result if item["symbol"] == "WEAK")
    assert record.get("float_gate_bypass") is not True
    assert record["terminal_outcome"] == "Rejected"
    assert record["terminal_stage"] == "Free-Float Gate"
