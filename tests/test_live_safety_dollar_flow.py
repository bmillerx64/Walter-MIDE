from mide.live_safety import _participation_floor


def test_volume_spike_without_dollar_flow_does_not_override_low_rvol():
    passed, _ = _participation_floor({
        "rvol_proxy": 0.4,
        "volume_acceleration_1m": 2.5,
        "volume_acceleration_3m": 1.8,
        "dollar_flow_acceleration_1m": 1.1,
        "dollar_flow_acceleration_3m": 1.0,
    })
    assert passed is False
