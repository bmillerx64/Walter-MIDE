"""Machine-readable contract metadata for Walter decision replay."""

REPLAY_FORMAT = "walter-decision-replay-v1"
REPLAY_GUARANTEES = (
    "frozen_evidence_only",
    "sha256_integrity_verified",
    "no_current_market_data",
    "legacy_absence_explicit",
    "read_only",
)


def replay_contract() -> dict:
    return {"format": REPLAY_FORMAT, "guarantees": list(REPLAY_GUARANTEES)}
