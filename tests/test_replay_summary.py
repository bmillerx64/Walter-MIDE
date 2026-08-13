from mide.replay_summary import summarize_replay


def test_summary_reports_state_and_blockers_without_recalculation():
    replay = {
        "symbol": "ABC",
        "replay_state": "STRUCTURE_BLOCKED",
        "blockers": ["VWAP not reclaimed", "alignment below threshold"],
    }
    assert summarize_replay(replay) == (
        "ABC: STRUCTURE_BLOCKED — VWAP not reclaimed; alignment below threshold"
    )
