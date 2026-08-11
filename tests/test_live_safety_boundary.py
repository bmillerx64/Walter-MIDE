from mide.live_safety import _participation_floor


def test_rvol_one_is_normal_participation():
    passed, _ = _participation_floor({"rvol_proxy": 1.0})
    assert passed is True
