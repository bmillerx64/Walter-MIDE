from mide.live_safety import _participation_floor


def test_low_session_rvol_can_still_surface_when_tape_is_igniting_now():
    passed, reason = _participation_floor({
        "rvol_proxy": 0.65,
        "volume_acceleration_1m": 2.2,
        "volume_acceleration_3m": 1.6,
        "dollar_flow_acceleration_1m": 1.7,
    })
    assert passed is True
    assert "Early ignition override" in reason
