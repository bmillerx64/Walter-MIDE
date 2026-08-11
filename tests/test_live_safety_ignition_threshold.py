from mide.live_safety import _participation_floor


def test_ignition_threshold_is_inclusive():
    passed, _ = _participation_floor({
        "rvol_proxy": 0.5,
        "volume_acceleration_1m": 2.0,
        "volume_acceleration_3m": 1.5,
        "dollar_flow_acceleration_1m": 1.5,
    })
    assert passed is True
