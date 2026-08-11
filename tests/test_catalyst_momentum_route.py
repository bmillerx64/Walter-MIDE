from mide.architecture import ArchitecturePolicy, Decision, STAGES, WalterArchitectureV1


class Store:
    def __init__(self):
        self.results = None

    def persist(self, results):
        self.results = results


def _pipeline(records, *, catalyst_scores):
    store = Store()
    calls = {"catalyst": 0}

    def catalyst(items):
        calls["catalyst"] += 1
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
    return architecture, result, calls


def test_published_architecture_order_remains_unchanged():
    assert STAGES[3:5] == ("Free-Float Gate", "Catalyst Assessment")


def test_low_float_candidate_remains_normal_squeeze_lane():
    architecture, result, calls = _pipeline(
        [{"symbol": "TINY", "price": 1.0, "float_shares": 2_000_000}],
        catalyst_scores={"TINY": 0},
    )
    record = next(item for item in result if item["symbol"] == "TINY")
    assert record.get("float_gate_bypass") is not True
    assert record.get("strategy_lane") != "CATALYST_MOMENTUM"
    assert record["terminal_outcome"] == "Qualified and Ranked"
    assert calls["catalyst"] == 1


def test_plag_style_larger_float_with_material_catalyst_reaches_participation():
    architecture, result, calls = _pipeline(
        [{"symbol": "PLAG", "price": 1.0, "float_shares": 11_500_000}],
        catalyst_scores={"PLAG": 9},
    )
    record = next(item for item in result if item["symbol"] == "PLAG")
    assert record["strategy_lane"] == "CATALYST_MOMENTUM"
    assert record["float_gate_bypass"] is True
    assert record["squeeze_eligible"] is False
    assert record["terminal_outcome"] == "Qualified and Ranked"
    assert record["headline"].startswith("PLAG announces")
    stages = [step["stage"] for step in record["architecture_audit"]]
    assert stages.index("Free-Float Gate") < stages.index("Catalyst Assessment")
    assert "Participation Assessment" in stages
    assert "Expansion Assessment" in stages
    # The Stage-5 catalyst assessment consumes the Stage-4 preflight cache.
    assert calls["catalyst"] == 1


def test_larger_float_without_material_catalyst_is_still_rejected():
    architecture, result, calls = _pipeline(
        [{"symbol": "BIG", "price": 1.0, "float_shares": 11_500_000}],
        catalyst_scores={"BIG": 0},
    )
    record = next(item for item in result if item["symbol"] == "BIG")
    assert record.get("float_gate_bypass") is not True
    assert record["terminal_outcome"] == "Rejected"
    assert record["terminal_stage"] == "Free-Float Gate"
    assert calls["catalyst"] == 1


def test_weak_headline_score_does_not_bypass_float_gate():
    architecture, result, calls = _pipeline(
        [{"symbol": "WEAK", "price": 1.0, "float_shares": 11_500_000}],
        catalyst_scores={"WEAK": 6.9},
    )
    record = next(item for item in result if item["symbol"] == "WEAK")
    assert record.get("float_gate_bypass") is not True
    assert record["terminal_outcome"] == "Rejected"
    assert record["terminal_stage"] == "Free-Float Gate"
    assert calls["catalyst"] == 1


def test_unavailable_float_is_never_excused_by_catalyst_lane():
    calls = {"catalyst": 0}

    def catalyst(items):
        calls["catalyst"] += 1
        return {
            item["symbol"]: Decision(
                True,
                "Catalyst",
                "assessed",
                {"headline": "Material news", "catalyst_score": 10},
            )
            for item in items
        }

    def unavailable_float(items):
        return {
            item["symbol"]: Decision(
                False, "Free Float", "Usable free-float value unavailable"
            )
            for item in items
        }

    passing = lambda items: {
        item["symbol"]: Decision(True, "assessment", "passed") for item in items
    }
    architecture = WalterArchitectureV1(
        policy=ArchitecturePolicy(0.05, 5.0, 3_500_000),
        discover=lambda: [{"symbol": "UNKNOWN", "price": 1.0}],
        catalyst=catalyst,
        free_float=unavailable_float,
        participation=passing,
        expansion=passing,
        rank=lambda items: list(items),
        store=Store(),
        publish=lambda items: None,
    )
    result = architecture.run()
    record = next(item for item in result if item["symbol"] == "UNKNOWN")
    assert record.get("float_gate_bypass") is not True
    assert record["terminal_outcome"] == "Rejected"
    assert record["terminal_stage"] == "Free-Float Gate"
    assert calls["catalyst"] == 1
