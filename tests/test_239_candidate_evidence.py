from copy import deepcopy

from mide.candidate_evidence import candidate_evidence_report, candidate_evidence_summary
from mide.decision_narrative import build_decision_narrative


def _stage(name):
    return {"stage": name, "decision": "Qualified", "reason": f"recorded {name}"}


def _complete_record():
    return {
        "symbol": "AAA",
        "architecture_audit": [
            _stage("Catalyst Assessment"),
            _stage("Participation Assessment"),
            _stage("Expansion Assessment"),
            _stage("Mission Ranking and Publication"),
        ],
        "ranking_history": [
            {
                "rank": 1,
                "previous_rank": 1,
                "qualified": True,
                "conviction_trend": "→",
                "conviction_change": 0,
                "reasons": [],
                "evidence": {
                    "conviction": 82,
                    "participation": 64,
                    "expansion": 71,
                    "volume_expansion": 77,
                    "entry_readiness": False,
                    "vwap_reclaimed": True,
                    "supertrend_bullish": True,
                },
            }
        ],
    }


def test_complete_candidate_evidence_scores_100_without_mutation():
    record = _complete_record()
    original = deepcopy(record)
    report = candidate_evidence_report(record)
    assert report["status"] == "COMPLETE"
    assert report["completeness_pct"] == 100.0
    assert report["evidence_complete"] is True
    assert report["issues"] == []
    assert candidate_evidence_summary(record) == "Evidence COMPLETE · 100%"
    assert record == original


def test_missing_architecture_stage_is_reported_not_invented():
    record = _complete_record()
    record["architecture_audit"] = [
        item for item in record["architecture_audit"]
        if item["stage"] != "Catalyst Assessment"
    ]
    report = candidate_evidence_report(record)
    assert report["status"] == "PARTIAL"
    assert "Catalyst Assessment" in report["missing_stages"]
    assert any("missing architecture stage evidence" in issue for issue in report["issues"])


def test_missing_ranking_evidence_is_visible_and_lowers_completeness():
    record = _complete_record()
    del record["ranking_history"][-1]["evidence"]["participation"]
    report = candidate_evidence_report(record)
    assert "participation" in report["missing_ranking_fields"]
    assert report["completeness_pct"] < 100
    assert report["evidence_complete"] is False


def test_missing_ranking_history_is_insufficient_not_zero_filled():
    record = _complete_record()
    record["ranking_history"] = []
    report = candidate_evidence_report(record)
    assert report["status"] == "INSUFFICIENT"
    assert report["ranking_present"] is False
    assert "missing ranking history" in report["issues"]


def test_decision_narrative_exposes_candidate_evidence_trust():
    narrative = build_decision_narrative(_complete_record())
    assert narrative["evidence_trust"]["status"] == "COMPLETE"
    assert narrative["evidence_trust"]["completeness_pct"] == 100.0
    assert narrative["evidence_trust_summary"] == "Evidence COMPLETE · 100%"
    assert narrative["evidence_source"] == "architecture_audit and ranking_history"


def test_candidate_evidence_diagnostic_does_not_change_decision_fields():
    record = _complete_record()
    record["qualified_for_entry"] = False
    record["conviction_score"] = 91
    original = deepcopy(record)
    candidate_evidence_report(record)
    build_decision_narrative(record)
    assert record == original
    assert record["qualified_for_entry"] is False
    assert record["conviction_score"] == 91
