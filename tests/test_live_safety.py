from mide.live_safety import (
    _behavioral_decision_with_participation_floor,
    _conservative_yahoo_share_structure,
    _participation_floor,
)


def yahoo_payload(float_shares, shares_outstanding):
    return {
        "quoteSummary": {
            "result": [{
                "defaultKeyStatistics": {
                    "floatShares": {"raw": float_shares},
                    "sharesOutstanding": {"raw": shares_outstanding},
                }
            }]
        }
    }


def test_share_structure_uses_conservative_larger_value():
    assert _conservative_yahoo_share_structure(
        yahoo_payload(1_000_000, 13_390_000)
    ) == 13_390_000


def test_low_rvol_without_multi_window_ignition_fails():
    passed, reason = _participation_floor({
        "rvol_proxy": 0.15,
        "volume_acceleration_1m": 1.3,
        "volume_acceleration_3m": 1.1,
        "dollar_flow_acceleration_1m": 1.2,
        "dollar_flow_acceleration_3m": 1.1,
    })
    assert passed is False
    assert "Participation too thin" in reason


def test_low_rvol_with_real_ignition_can_survive():
    passed, reason = _participation_floor({
        "rvol_proxy": 0.5,
        "volume_acceleration_1m": 2.4,
        "volume_acceleration_3m": 1.7,
        "dollar_flow_acceleration_1m": 1.8,
    })
    assert passed is True
    assert "Early ignition override" in reason


def test_normal_rvol_passes_floor():
    passed, reason = _participation_floor({"rvol_proxy": 1.25})
    assert passed is True
    assert "RVOL 1.25x" in reason
