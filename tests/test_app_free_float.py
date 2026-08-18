from app import free_float_decision
from mide.config import Settings


def test_known_free_float_at_ceiling_passes_as_verified():
    ceiling = Settings().max_free_float
    decision = free_float_decision(
        {"symbol": "ATMAX", "float_shares": ceiling},
        ceiling,
    )

    assert decision.passed is True
    assert decision.reason == "Free float within configured limit"
    assert decision.updates["free_float_verified"] is True
    assert decision.updates["free_float_verification_status"] == "verified"


def test_known_free_float_above_ceiling_is_rejected():
    ceiling = Settings().max_free_float
    decision = free_float_decision(
        {"symbol": "OVER", "free_float": ceiling + 1},
        ceiling,
    )

    assert decision.passed is False
    assert decision.reason == "Free float exceeds configured limit"
    assert decision.updates["free_float_verified"] is True
    assert decision.updates["free_float_verification_status"] == "verified"


def test_unparseable_free_float_passes_but_is_marked_unavailable():
    decision = free_float_decision(
        {"symbol": "UNKNOWN", "shares_float": "unavailable"},
        Settings().max_free_float,
    )

    assert decision.passed is True
    assert decision.reason == "Free float unavailable; configured limit unverified"
    assert decision.updates["free_float_verified"] is False
    assert decision.updates["free_float_verification_status"] == "unavailable"
