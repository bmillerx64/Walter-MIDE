from mide.live_safety import _participation_floor


def test_thin_participation_reason_reports_rvol():
    passed, reason = _participation_floor({"rvol_proxy": 0.17})
    assert passed is False
    assert "RVOL 0.17x" in reason
