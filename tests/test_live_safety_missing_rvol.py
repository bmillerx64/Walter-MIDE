from mide.live_safety import _participation_floor


def test_missing_rvol_defaults_to_neutral_and_does_not_block_entry():
    # FIX-6: rvol_proxy absent → default 1.0 (neutral) so the participation floor
    # passes.  The old default of 0.0 silently blocked every symbol that had not
    # yet received an RVOL reading from the feed.
    passed, reason = _participation_floor({
        "volume_acceleration_1m": 1.0,
        "volume_acceleration_3m": 1.0,
    })
    assert passed is True
    assert "rvol" in reason.lower() or "floor" in reason.lower() or reason != ""
