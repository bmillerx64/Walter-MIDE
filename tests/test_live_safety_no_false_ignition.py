from mide.live_safety import _participation_floor


def test_one_minute_spike_alone_does_not_override_low_rvol():
    passed, _ = _participation_floor({
        "rvol_proxy": 0.4,
        "volume_acceleration_1m": 3.0,
        "volume_acceleration_3m": 1.1,
        "dollar_flow_acceleration_1m": 2.0,
    })
    assert passed is False
