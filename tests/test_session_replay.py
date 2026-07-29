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
                quality_score=88,
                quality_grade="B+",
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
    assert peak["quality_score"] == 88
    assert peak["quality_grade"] == "B+"
    assert replay["summary"]["most_limiting_rule"] == (
        "VWAP — price has not reclaimed VWAP"
    )
    assert replay["summary"]["most_limiting_rule_count"] == 1
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


def test_replay_shows_exact_categorized_blockers_and_compresses_identical_events():
    failed_gates = {
        "participation_gate": {
            "passed": False,
            "failed_criteria": [
                {
                    "condition": "Dollar volume increasing",
                    "failed_reason": "Dollar flow not increasing",
                    "measured": 1.02,
                    "threshold": 1.15,
                }
            ],
        },
        "structure_gate": {
            "passed": False,
            "checks": [
                {
                    "condition": "VWAP reclaim or constructive test",
                    "passed": False,
                    "failed_reason": "VWAP not reclaimed",
                    "measured": "below",
                    "threshold": "above or testing",
                },
                {
                    "condition": "SuperTrend confirmation",
                    "passed": False,
                    "failed_reason": "SuperTrend not confirmed",
                },
            ],
        },
    }
    bundle = {
        "symbol": "same",
        "flight_recorder": [
            trace("2026-07-27T14:30:00Z", "Watching", **failed_gates),
            trace("2026-07-27T14:31:00Z", "Watching", **failed_gates),
            trace("2026-07-27T14:32:00Z", "Strengthening", **failed_gates),
        ],
    }

    replay = build_session_replay(bundle)

    assert len(replay["scans"]) == 2
    event = replay["scans"][0]
    assert event["scan_count"] == 2
    assert event["end_timestamp"] == "2026-07-27T14:31:00Z"
    assert event["promotion_blockers"] == [
        {
            "category": "Participation",
            "reason": "Dollar flow not increasing",
            "condition": "Dollar volume increasing",
            "measured": 1.02,
            "threshold": 1.15,
        },
        {
            "category": "VWAP",
            "reason": "VWAP not reclaimed",
            "condition": "VWAP reclaim or constructive test",
            "measured": "below",
            "threshold": "above or testing",
        },
        {
            "category": "SuperTrend",
            "reason": "SuperTrend not confirmed",
            "condition": "SuperTrend confirmation",
        },
    ]
    assert replay["summary"]["total_scans"] == 3
    assert replay["summary"]["summarized_events"] == 2
    assert replay["summary"]["most_limiting_rule_count"] == 3
