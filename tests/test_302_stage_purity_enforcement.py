from mide.architecture import Decision
from mide.gs302_stage_purity_enforcement import _sanitize_decision


def test_participation_drops_upstream_owned_price_but_keeps_analysis_fields():
    decision = Decision(
        True,
        "Participation",
        "Participation evidence measured",
        {
            "symbol": "ARCT",
            "price": 10.35,
            "free_float": 28_423_069,
            "participation_score": 40.9,
            "volume_acceleration": 1.2,
            "vwap_relation": "above",
        },
    )
    cleaned = _sanitize_decision("Participation Assessment", decision)
    assert "price" not in cleaned.updates
    assert "free_float" not in cleaned.updates
    assert cleaned.updates["participation_score"] == 40.9
    assert cleaned.updates["volume_acceleration"] == 1.2
    assert cleaned.updates["vwap_relation"] == "above"


def test_expansion_cannot_rewrite_upstream_price_or_float():
    decision = Decision(
        True,
        "Expansion",
        "Confluence 65",
        {"price": 1.55, "free_float": 7_542_638, "confluence_score": 65},
    )
    cleaned = _sanitize_decision("Expansion Assessment", decision)
    assert cleaned.updates == {"confluence_score": 65}


def test_catalyst_cannot_rewrite_price_but_keeps_catalyst_evidence():
    decision = Decision(
        True,
        "Catalyst",
        "Catalyst evidence assessed",
        {"price": 0.47, "headline": "Material contract awarded", "catalyst_score": 9},
    )
    cleaned = _sanitize_decision("Catalyst Assessment", decision)
    assert "price" not in cleaned.updates
    assert cleaned.updates["headline"] == "Material contract awarded"
    assert cleaned.updates["catalyst_score"] == 9


def test_non_restricted_stage_is_unchanged_identity():
    decision = Decision(True, "Other", "ok", {"price": 1.0, "score": 10})
    assert _sanitize_decision("Mission Ranking and Publication", decision) is decision


def test_decision_semantics_evidence_and_provenance_are_preserved():
    evidence = {"failed_metrics": []}
    provenance = {"provider": "Webull"}
    decision = Decision(
        False,
        "Participation",
        "reason",
        {"price": 1.0, "participation_score": 33.4},
        evidence,
        provenance,
    )
    cleaned = _sanitize_decision("Participation Assessment", decision)
    assert cleaned.passed is False
    assert cleaned.category == decision.category
    assert cleaned.reason == decision.reason
    assert cleaned.evidence is evidence
    assert cleaned.provenance is provenance
