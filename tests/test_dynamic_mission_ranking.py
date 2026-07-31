from mide.architecture import (
    ArchitecturePolicy,
    Decision,
    STAGES,
    WalterArchitectureV1,
    WalterCandidateLedger,
)


class Store:
    def persist(self, records):
        self.records = records


def test_live_scans_promote_demote_remove_and_replace_without_changing_identity():
    snapshots = [[
        {"symbol": "AAA", "price": 1, "free_float": 1, "conviction_score": 80,
         "participation_score": 70, "vwap_relation": "below", "qualified": True},
        {"symbol": "BBB", "price": 1, "free_float": 1, "conviction_score": 70,
         "participation_score": 60, "qualified": True},
    ]]
    ledger = WalterCandidateLedger()
    publications = []

    def pass_stage(records):
        return {item["symbol"]: Decision(True, "test", "passed") for item in records}

    def expansion(records):
        return {
            item["symbol"]: Decision(bool(item["qualified"]), "Expansion", "live qualification")
            for item in records
        }

    architecture = WalterArchitectureV1(
        policy=ArchitecturePolicy(.05, 5, 100), discover=lambda: snapshots[0],
        catalyst=pass_stage, participation=pass_stage, expansion=expansion,
        rank=lambda records: sorted(records, key=lambda item: item["conviction_score"], reverse=True),
        store=Store(), publish=lambda records: publications.append([item["symbol"] for item in records]),
        ledger=ledger,
    )

    first = architecture.run()
    identities = {item["symbol"]: id(item) for item in first}
    assert publications[-1] == ["AAA", "BBB"]

    snapshots[0] = [
        {"symbol": "AAA", "price": 1, "free_float": 1, "conviction_score": 65,
         "participation_score": 55, "vwap_relation": "below", "qualified": True},
        {"symbol": "BBB", "price": 1, "free_float": 1, "conviction_score": 90,
         "participation_score": 85, "vwap_relation": "above", "supertrend_bullish": True,
         "volume_expansion": 2, "qualified": True},
        {"symbol": "CCC", "price": 1, "free_float": 1, "conviction_score": 75,
         "participation_score": 75, "qualified": True},
    ]
    second = architecture.run()
    assert publications[-1] == ["BBB", "CCC", "AAA"]
    assert {item["symbol"]: id(item) for item in second if item["symbol"] != "CCC"} == identities
    bbb = ledger.records["BBB"]
    assert bbb["conviction_trend"] == "↑"
    assert {"increased participation", "VWAP reclaim", "SuperTrend flip", "volume expansion"} <= set(bbb["ranking_move_reasons"])

    snapshots[0] = [
        {"symbol": "AAA", "price": 1, "free_float": 1, "conviction_score": 60,
         "participation_score": 45, "qualified": False},
        {"symbol": "CCC", "price": 1, "free_float": 1, "conviction_score": 95,
         "participation_score": 90, "qualified": True},
    ]
    architecture.run()
    assert publications[-1] == ["CCC"]
    assert ledger.records["AAA"]["terminal_outcome"] == "Rejected"
    assert ledger.records["BBB"]["terminal_reason"] == "Not present in current live universe"
    assert [entry["rank"] for entry in ledger.records["AAA"]["ranking_history"]] == [1, 3, None]
    assert len(ledger.records["BBB"]["ranking_history"]) == 3
    assert [stage["stage"] for stage in architecture.trace] == list(STAGES)

