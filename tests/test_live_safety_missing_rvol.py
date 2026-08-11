from mide.live_safety import _participation_floor


def test_missing_rvol_requires_real_ignition_instead_of_default_pass():
    passed, _ = _participation_floor({
        "volume_acceleration_1m": 1.0,
        "volume_acceleration_3m": 1.0,
    })
    assert passed is False
