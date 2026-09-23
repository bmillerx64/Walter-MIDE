"""Structural contract for Walter Next Phase 1 authority boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

from mide.authorities import COMPONENTS


ROOT = Path(__file__).resolve().parents[1]


def test_exactly_six_authoritative_components_are_declared():
    assert COMPONENTS == (
        "discovery_news",
        "market_evidence",
        "thesis_state",
        "entry_authority",
        "presentation_audio",
        "replay_validation",
    )


def test_app_uses_authority_seams_for_migrated_meaning_imports():
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    imported_from = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }

    for component in COMPONENTS:
        assert f"mide.authorities.{component}" in imported_from

    # These direct top-level imports are now forbidden in app.py.  Dynamic imports
    # retained for Streamlit hot-reload repair are intentionally outside this Phase 1
    # assertion and will be removed only when their runtime behavior is consolidated.
    forbidden = {
        "mide.data_integrity",
        "mide.decision_engine",
        "mide.discovery",
        "mide.escalation",
        "mide.flight_recorder",
        "mide.gs498_mission_ranking_direction",
        "mide.gs516_visible_alert_audio_health",
        "mide.gs528_canonical_entry_ready",
        "mide.live_evidence_observation",
        "mide.mission_outcomes",
        "mide.news",
        "mide.news_provider",
        "mide.scanner_v2",
        "mide.ui",
    }
    assert imported_from.isdisjoint(forbidden)


def test_phase_one_facades_delegate_to_validated_implementations(monkeypatch):
    from mide import decision_engine, discovery, flight_recorder, news, scanner_v2, ui
    from mide.authorities import (
        discovery_news,
        entry_authority,
        market_evidence,
        presentation_audio,
        replay_validation,
        thesis_state,
    )
    from mide.gs498_mission_ranking_direction import mission_ranked_records
    from mide.gs528_canonical_entry_ready import canonical_candidate_status

    assert discovery_news.build_seed_symbols is discovery.build_seed_symbols
    assert discovery_news.index_news is news.index_news
    discovery_sentinel = lambda *args, **kwargs: ("discovery", args, kwargs)
    scanner_sentinel = lambda *args, **kwargs: ("scanner", args, kwargs)
    monkeypatch.setattr(discovery, "analyze_candidates", discovery_sentinel)
    monkeypatch.setattr(scanner_v2, "apply_scanner_v2", scanner_sentinel)
    assert market_evidence.analyze_candidates("x", flag=True) == (
        "discovery", ("x",), {"flag": True}
    )
    assert market_evidence.apply_scanner_v2("y", flag=False) == (
        "scanner", ("y",), {"flag": False}
    )
    assert thesis_state.evaluate is decision_engine.evaluate
    assert thesis_state.mission_ranked_records is mission_ranked_records
    assert entry_authority.canonical_candidate_status is canonical_candidate_status
    presentation_sentinel = lambda *args, **kwargs: ("presentation", args, kwargs)
    monkeypatch.setattr(ui, "actionable_candidate_records", presentation_sentinel)
    assert presentation_audio.actionable_candidate_records("z", flag=True) == (
        "presentation", ("z",), {"flag": True}
    )
    assert replay_validation.FlightRecorder is flight_recorder.FlightRecorder
