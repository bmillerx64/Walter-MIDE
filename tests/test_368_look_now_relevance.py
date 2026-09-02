from mide import gs310_unified_opportunity_state as unified
from mide import gs311_unified_voice as voice
from mide import gs314_state_consistency as consistency
from mide import gs363_operator_attention_hierarchy as hierarchy


def _top_mover(
    symbol,
    *,
    participation,
    expansion,
    volume_acceleration,
    dollar_flow_acceleration,
    vwap_distance=1.0,
    trend=True,
):
    return {
        "symbol": symbol,
        "qualified_for_ranking": True,
        "vwap_relation": "above",
        "vwap_distance_pct": vwap_distance,
        "supertrend_bullish": trend,
        "participation_surge_score": participation,
        "expansion_quality": expansion,
        "volume_acceleration": volume_acceleration,
        "dollar_flow_acceleration": dollar_flow_acceleration,
        "discovery_reasons": ["Webull native: day_gainers"],
    }


def test_gels_like_top_mover_is_developing_without_fresh_flow_confirmation():
    gels = _top_mover(
        "GELS",
        participation=42,
        expansion=43,
        volume_acceleration=0.50,
        dollar_flow_acceleration=0.50,
    )

    view = unified.opportunity_state(gels)
    assert view["state"] == unified.DEVELOPING
    assert "fresh volume or dollar-flow confirmation" in view["reason"]


def test_viot_like_top_mover_stays_look_now_with_participation_and_fresh_dollar_flow():
    viot = _top_mover(
        "VIOT",
        participation=31.6,
        expansion=40,
        volume_acceleration=0.50,
        dollar_flow_acceleration=1.74,
        vwap_distance=1.41,
    )

    view = unified.opportunity_state(viot)
    assert view["state"] == unified.LOOK_NOW
    assert viot["participation_surge_score"] < 72
    assert viot["expansion_quality"] < 58


def test_top_mover_with_fresh_volume_but_no_participation_stays_developing():
    thin = _top_mover(
        "THIN",
        participation=18,
        expansion=44,
        volume_acceleration=1.80,
        dollar_flow_acceleration=0.70,
    )

    assert unified.opportunity_state(thin)["state"] == unified.DEVELOPING


def test_fresh_news_keeps_early_look_now_without_top_mover_flow_contract():
    news = {
        "symbol": "NEWS",
        "qualified_for_ranking": True,
        "vwap_relation": "above",
        "vwap_distance_pct": 1.0,
        "supertrend_bullish": False,
        "participation_surge_score": 10,
        "expansion_quality": 20,
        "volume_acceleration": 0.20,
        "dollar_flow_acceleration": 0.20,
        "discovery_reasons": ["FMP material news seed"],
    }

    assert unified.opportunity_state(news)["state"] == unified.LOOK_NOW


def test_every_trader_facing_binding_uses_gs368_relevance_calibration():
    assert getattr(unified.opportunity_state, "_gs368_look_now_relevance", False)
    assert voice.opportunity_state is unified.opportunity_state
    assert consistency.opportunity_state is unified.opportunity_state
    assert hierarchy.opportunity_state is unified.opportunity_state
