from mide.gs348_st_vwap_operator_priority import (
    MIN_ABSOLUTE_VOLUME,
    STVWAPSnapshot,
    operator_relevant_developing,
    reset_state,
    st_vwap_cross,
)


def record(**overrides):
    data = dict(
        symbol="OLOX",
        price=1.08,
        vwap_value=1.05,
        supertrend_value=1.06,
        supertrend_bullish=True,
        volume=900_000,
        volume_acceleration=1.8,
        participation_score=28,
        expansion_score=48,
        vwap_distance_pct=2.0,
        candidate_status="Developing",
    )
    data.update(overrides)
    return data


def test_olox_style_st_cross_is_high_priority_watch_event():
    prior = STVWAPSnapshot(supertrend_value=1.02, vwap_value=1.05, seen_at=1.0)
    ok, reason = st_vwap_cross(record(), prior)
    assert ok is True
    assert "crossed above VWAP" in reason


def test_cross_requires_actual_line_to_line_transition():
    prior = STVWAPSnapshot(supertrend_value=1.06, vwap_value=1.05, seen_at=1.0)
    ok, reason = st_vwap_cross(record(), prior)
    assert ok is False
    assert reason == "no fresh ST/VWAP cross"


def test_low_absolute_volume_without_fresh_catalyst_is_not_operator_relevant_developing():
    reset_state()
    sqft = record(symbol="SQFT", volume=160_320, volume_acceleration=1.8, participation_score=26, expansion_score=47)
    assert sqft["volume"] < MIN_ABSOLUTE_VOLUME
    assert operator_relevant_developing(sqft) is False


def test_fresh_catalyst_can_keep_lower_volume_developing_name_visible():
    reset_state()
    candidate = record(symbol="NEWS", volume=180_000, headline="Fresh material company update")
    assert operator_relevant_developing(candidate) is True


def test_cross_itself_fails_when_absolute_volume_is_thin_without_catalyst():
    prior = STVWAPSnapshot(supertrend_value=1.02, vwap_value=1.05, seen_at=1.0)
    ok, reason = st_vwap_cross(record(symbol="SQFT", volume=160_320), prior)
    assert ok is False
    assert reason == "insufficient supporting volume/evidence"
