from mide.replay_contract import replay_contract


def test_replay_contract_declares_safety_guarantees():
    contract = replay_contract()
    assert contract["format"] == "walter-decision-replay-v1"
    assert "frozen_evidence_only" in contract["guarantees"]
    assert "sha256_integrity_verified" in contract["guarantees"]
    assert "no_current_market_data" in contract["guarantees"]
    assert "read_only" in contract["guarantees"]
