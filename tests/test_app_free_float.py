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


def test_fail_closed_refresh_sentinel_remains_rejected_and_unverified():
    decision = free_float_decision(
        {
            "symbol": "JZ",
            "float_shares": float("inf"),
            "free_float_verified": False,
            "free_float_verification_status": "refresh-unavailable-reject",
            "free_float_source": "low-float live refresh unresolved; fail closed",
        },
        Settings().max_free_float,
    )

    assert decision.passed is False
    assert decision.reason == "Free float live refresh unresolved; fail closed"
    assert decision.updates["free_float_verified"] is False
    assert (
        decision.updates["free_float_verification_status"]
        == "refresh-unavailable-reject"
    )
    assert (
        decision.updates["free_float_source"]
        == "low-float live refresh unresolved; fail closed"
    )


def test_nonfinite_float_without_provider_metadata_fails_closed_as_unverified():
    decision = free_float_decision(
        {"symbol": "SENTINEL", "float_shares": float("inf")},
        Settings().max_free_float,
    )

    assert decision.passed is False
    assert decision.reason == "Free float unresolved; fail closed"
    assert decision.updates["free_float_verified"] is False
    assert decision.updates["free_float_verification_status"] == "unavailable-reject"
