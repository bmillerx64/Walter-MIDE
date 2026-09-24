"""Phase 24: GS483 Flight Recorder read containment belongs to Replay / Validation."""

from pathlib import Path

from mide import gs483_resource_containment as gs483
from mide.authorities import replay_validation


ROOT = Path(__file__).resolve().parents[1]


def test_gs483_compatibility_surface_delegates_to_replay_validation():
    assert gs483.AUTHORITY == replay_validation.RESOURCE_CONTAINMENT_AUTHORITY
    assert gs483.TAIL_CHUNK_BYTES == replay_validation.RESOURCE_TAIL_CHUNK_BYTES
    assert gs483.bounded_latest_scan.__name__ == "bounded_latest_scan"
    assert gs483.streaming_scans.__name__ == "streaming_scans"
    assert gs483.streaming_symbol_history.__name__ == "streaming_symbol_history"
    assert gs483.resource_snapshot.__name__ == "recorder_resource_snapshot"


def test_gs483_install_uses_authoritative_replay_validation_installer(monkeypatch):
    called = {"count": 0}

    def install():
        called["count"] += 1

    monkeypatch.setattr(replay_validation, "install_resource_containment", install)
    gs483.install()

    assert called["count"] == 1


def test_gs483_source_is_compatibility_facade_not_duplicate_implementation():
    source = (ROOT / "mide/gs483_resource_containment.py").read_text(
        encoding="utf-8"
    )

    assert "mide.authorities import replay_validation as _replay" in source
    assert "def bounded_latest_scan(" not in source
    assert "def streaming_scans(" not in source
    assert "def streaming_symbol_history(" not in source
    assert "def resource_snapshot(" not in source


def test_phase24_remains_recorder_read_side_only():
    source = (ROOT / "mide/gs483_resource_containment.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "qualified_for_entry",
        "qualified_for_alert",
        "qualified_for_watch",
        "mission_rank",
        "participation_score",
        "opportunity_score",
        "ensure_stream",
        "initialize_quotes",
        "place_order",
        "submit_order",
        "requests.get(",
        "requests.post(",
    )
    assert not any(token in source for token in forbidden)
