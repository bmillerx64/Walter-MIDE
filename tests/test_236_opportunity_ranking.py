from mide.opportunity import dollar_flow_score, enrich_opportunity
from mide.ui import walter_mission_control


def _record(symbol: str, dollar_volume: float) -> dict:
    return {
        "symbol": symbol,
        "candidate_status": "Watching",
        "qualified_for_watch": True,
        "participation_score": 60,
        "participation_surge_score": 60,
        "expansion_quality": 60,
        "vwap_relation": "testing",
        "vwap_distance_pct": 0.5,
        "supertrend_bullish": False,
        "market_dominance_score": 0,
        "attention_score": 0,
        "dollar_volume": dollar_volume,
    }


def test_dollar_flow_score_separates_thin_from_material_tape():
    thin = _record("THIN", 250_000)
    active = _record("ACTIVE", 100_000_000)

    assert dollar_flow_score(active) > dollar_flow_score(thin) + 60
    assert 0 <= dollar_flow_score(thin) <= 100
    assert 0 <= dollar_flow_score(active) <= 100


def test_enrichment_preserves_upstream_dollar_flow_score():
    record = _record("UPSTREAM", 100_000_000)
    record["dollar_flow_score"] = 42

    enrich_opportunity(record)

    assert record["dollar_flow_score"] == 42


def test_mission_control_prefers_material_dollar_flow_when_other_evidence_ties():
    thin = _record("THIN", 250_000)
    active = _record("ACTIVE", 100_000_000)
    enrich_opportunity(thin)
    enrich_opportunity(active)

    mission = walter_mission_control([thin, active])

    assert mission["primary"]["symbol"] == "ACTIVE"
    assert mission["primary"]["confidence"] > mission["secondary"]["confidence"]
    assert mission["primary"]["band"] == mission["secondary"]["band"] == "background"
