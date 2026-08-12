from mide.entry_state import classify_entry_state


def base(**updates):
    record={"price":1.10,"vwap_relation":"above","vwap_distance_pct":1.5,"supertrend_bullish":True,"higher_lows":True,"volume_acceleration_1m":1.4,"volume_acceleration_3m":1.2,"price_change_10m_pct":4.0}
    record.update(updates); return record


def test_active_correction_is_not_actionable():
    prior=base(price=1.20,volume_acceleration_1m=1.8,volume_acceleration_3m=1.5)
    current=base(price=1.10,pullback=True,volume_acceleration_1m=.8,volume_acceleration_3m=1.2)
    result=classify_entry_state(current,prior)
    assert result["entry_state"]=="CORRECTING"
    assert result["entry_actionable"] is False


def test_reentry_requires_buyers_to_turn_back_up():
    prior=base(price=1.05,volume_acceleration_1m=.9,volume_acceleration_3m=1.0)
    current=base(price=1.08,volume_acceleration_1m=1.4,volume_acceleration_3m=1.1)
    result=classify_entry_state(current,prior)
    assert result["entry_state"]=="RE-ENTRY CONFIRMED"
    assert result["entry_actionable"] is True


def test_extended_move_is_not_actionable():
    result=classify_entry_state(base(vwap_distance_pct=6.0),base(price=1.05))
    assert result["entry_state"]=="EXTENDED"
    assert result["entry_actionable"] is False


def test_fresh_ignition_can_be_actionable_without_prior_scan():
    result=classify_entry_state(base(supertrend_flip=True,volume_acceleration_1m=2.0,volume_acceleration_3m=1.5,dollar_flow_acceleration_1m=1.4))
    assert result["entry_state"]=="IGNITING"
    assert result["entry_actionable"] is True
