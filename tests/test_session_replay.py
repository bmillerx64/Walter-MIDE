from mide.session_replay import build_session_replay


def trace(timestamp, state, **evidence):
    return {
        "timestamp": timestamp,
        "scan_id": timestamp,
        "stage_reached": "actionable display",
        "evidence": {"workflow_state": state, **evidence},
    }


def test_replay_builds_chronological_milestones_diagnostics_and_summary():
    bundle = {
        "symbol": "dfns",
        "flight_recorder": [
            trace("2026-07-27T14:33:00Z", "Removed"),
            trace("2026-07-27T14:30:00Z", "Watching"),
            trace(
                "2026-07-27T14:31:00Z",
                "Strengthening",
                participation_surge_score=82,
                supertrend_state="bullish",
                opportunity_score=74,
                trigger_diagnostics={
                    "checks": [
                        {
                            "passed": False,
                            "condition": "VWAP reclaim",
                            "failed_reason": "price has not reclaimed VWAP",
                        }
                    ]
                },
            ),
        ],
        "candidate_history": [
            {
                "symbol": "DFNS",
                "scan_timestamp": "2026-07-27T14:31:00Z",
                "candidate_status": "Strengthening",
                "expansion_quality": 72,
                "volume_pace_ratio": 1.8,
                "acceleration_ratio": 1.4,
                "vwap_distance_pct": -0.4,
            }
        ],
    }

    replay = build_session_replay(bundle)

    assert replay["symbol"] == "DFNS"
    assert [scan["state"] for scan in replay["scans"]] == [
        "Watching",
        "Strengthening",
        "Removed",
    ]
    assert replay["milestones"] == {
        "First discovered": "2026-07-27T14:30:00Z",
        "First Candidate": "2026-07-27T14:30:00Z",
        "First Watch List": "2026-07-27T14:30:00Z",
        "First Strengthening": "2026-07-27T14:31:00Z",
        "Closest Entry Ready moment": "2026-07-27T14:31:00Z",
        "Removal from tracking": "2026-07-27T14:33:00Z",
    }
    peak = replay["scans"][1]
    assert peak["expansion_quality"] == 72
    assert peak["vpi"] == 1.8
    assert peak["volume_acceleration"] == 1.4
    assert replay["summary"]["most_limiting_rule"] == "price has not reclaimed VWAP"
    assert "participation surged" in replay["summary"]["why_promoted"]
    assert "did not recommend entry" in replay["summary"]["why_no_entry"]


def test_replay_reports_entry_ready_and_does_not_mutate_exports():
    bundle = {
        "symbol": "READY",
        "candidate_history": [],
        "flight_recorder": [
            trace(
                "2026-07-27T14:30:00Z",
                "Entry Ready",
                qualified_for_entry=True,
                trigger_result=True,
            )
        ],
    }
    original = repr(bundle)

    replay = build_session_replay(bundle)

    assert repr(bundle) == original
    assert replay["summary"]["why_no_entry"] == (
        "Walter recorded an Entry Ready qualification during this session."
    )
    assert replay["summary"]["most_limiting_rule"] == "None recorded"
