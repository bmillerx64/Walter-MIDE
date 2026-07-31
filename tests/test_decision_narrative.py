from mide.architecture import ArchitecturePolicy, Decision, WalterArchitectureV1, WalterCandidateLedger


class Store:
    def persist(self, records):
        self.records = records


def _architecture(snapshots, ledger):
    def decide(stage):
        return lambda records: {
            r["symbol"]: Decision(
                bool(r.get(f"{stage}_passed", True)), stage.title(),
                str(r.get(f"{stage}_reason", f"recorded {stage} evidence")),
                evidence={"source": f"{stage}-fixture"},
            ) for r in records
        }

    return WalterArchitectureV1(
        policy=ArchitecturePolicy(.05, 10, 100), discover=lambda: snapshots[0],
        catalyst=decide("catalyst"), participation=decide("participation"),
        expansion=decide("expansion"),
        rank=lambda records: sorted(records, key=lambda r: r["conviction_score"], reverse=True),
        store=Store(), publish=lambda records: None, ledger=ledger,
    )


def _record(symbol, conviction, participation, expansion, **extra):
    return {
        "symbol": symbol, "price": 1, "free_float": 1,
        "conviction_score": conviction, "participation_score": participation,
        "expansion_score": expansion, **extra,
    }


def test_explanations_match_only_recorded_ledger_evidence_and_cover_required_summaries():
    snapshots = [[
        _record("AAA", 90, 95, 80, catalyst_reason="SEC filing recorded", vwap_relation="above", supertrend_bullish=True),
        _record("BBB", 70, 60, 55, catalyst_reason="Newswire item recorded"),
    ]]
    ledger = WalterCandidateLedger()
    _architecture(snapshots, ledger).run()

    first = ledger.records["AAA"]["decision_explanation"]
    second = ledger.records["BBB"]["decision_explanation"]
    assert "SEC filing recorded" in first["catalyst_summary"]
    assert "recorded participation evidence" in first["participation_summary"]
    assert "recorded expansion evidence" in first["expansion_summary"]
    assert first["strongest_positive_factors"]
    assert first["strongest_negative_factors"] == []
    assert "stronger recorded conviction, participation, expansion" in first["decision_narrative"]
    assert "Why Not #1? AAA has stronger recorded conviction, participation, expansion." == second["why_not_number_one"]
    serialized = repr(first) + repr(second)
    assert "earnings" not in serialized and "FDA" not in serialized
    assert first["evidence_source"] == "architecture_audit and ranking_history"


def test_ranking_explanation_updates_after_live_reranking_and_records_promotion():
    snapshots = [[_record("AAA", 90, 90, 80), _record("BBB", 70, 60, 55)]]
    ledger = WalterCandidateLedger()
    architecture = _architecture(snapshots, ledger)
    architecture.run()
    snapshots[0] = [_record("AAA", 65, 55, 50), _record("BBB", 95, 96, 90, vwap_relation="above")]
    architecture.run()

    promoted = ledger.records["BBB"]["decision_explanation"]
    demoted = ledger.records["AAA"]["decision_explanation"]
    assert promoted["ranking_change_explanation"].startswith("Rank changed from 2 to 1")
    assert "increased participation" in promoted["ranking_change_explanation"]
    assert promoted["conviction_trend"].startswith("↑")
    assert demoted["ranking_change_explanation"].startswith("Rank changed from 1 to 2")
    assert demoted["why_not_number_one"].startswith("Why Not #1? BBB")


def test_removed_mission_candidate_receives_recorded_removal_explanation():
    snapshots = [[_record("AAA", 90, 90, 80)]]
    ledger = WalterCandidateLedger()
    architecture = _architecture(snapshots, ledger)
    architecture.run()
    snapshots[0] = []
    architecture.run()

    removed = ledger.records["AAA"]["decision_explanation"]
    assert removed["why_removed"] == "Why Removed? Not present in current live universe"
    assert removed["ranking_change_explanation"].startswith("Rank changed from 1 to None")
    assert removed["removal_event"].startswith("A recorded architecture stage")
