"""Manifest for Walter deterministic replay subsystem components."""

REPLAY_COMPONENTS = (
    "decision_time_evidence",
    "decision_replay",
    "flight_recorder_evidence",
    "flight_recorder_gold",
    "flight_replay",
    "flight_recorder_replay_api",
    "replay_audit",
    "replay_health",
    "replay_export",
)


def replay_manifest() -> list[str]:
    return list(REPLAY_COMPONENTS)
