from mide.live_safety import _participation_floor


def test_tnmg_style_half_rvol_does_not_get_ready_without_ignition():
    passed, _ = _participation_floor({
        "rvol_proxy": 0.50,
        "volume_acceleration_1m": 1.4,
        "volume_acceleration_3m": 1.2,
        "dollar_flow_acceleration_1m": 1.3,
        "dollar_flow_acceleration_3m": 1.2,
    })
    assert passed is False
