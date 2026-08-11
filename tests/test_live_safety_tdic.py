from mide.live_safety import _participation_floor


def test_tdic_style_rvol_does_not_get_ready_without_ignition():
    passed, _ = _participation_floor({
        "rvol_proxy": 0.17,
        "volume_acceleration_1m": 1.3,
        "volume_acceleration_3m": 1.1,
        "dollar_flow_acceleration_1m": 1.2,
        "dollar_flow_acceleration_3m": 1.1,
    })
    assert passed is False
