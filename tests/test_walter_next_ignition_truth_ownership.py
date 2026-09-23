"""Phase 15 ownership contract for GS393/GS439 cross-authority split."""

from pathlib import Path

from mide import gs393_ignition_truth_extreme_decay as gs393
from mide.authorities import market_evidence, presentation_audio, replay_validation, thesis_state


def _record():
    return {
        "symbol": "TEST",
        "vwap_relation": "above",
        "vwap_distance_pct": 0.8,
        "vwap_reclaimed_last_10m": True,
        "vwap_reclaim_age_bars": 1,
        "supertrend_flip_age_seconds": 240.0,
        "volume_acceleration": 2.0,
        "participation_score": 24.0,
        "expansion_score": 44.0,
        "timeframes": {
            "1m": {"above_vwap": True, "supertrend": True},
            "3m": {"above_vwap": False, "supertrend": False},
        },
    }


def test_gs393_ignition_truth_delegates_to_market_evidence():
    assert gs393.ignition_evidence(_record()) == market_evidence.ignition_evidence(_record())
    assert (
        gs393.IGNITION_MAX_VWAP_DISTANCE_PCT
        == market_evidence.IGNITION_MAX_VWAP_DISTANCE_PCT
        == 2.0
    )
    assert (
        gs393.IGNITION_FLIP_RECENT_SECONDS
        == market_evidence.IGNITION_FLIP_RECENT_SECONDS
        == 150.0
    )
    assert (
        gs393.IGNITION_RECLAIM_RECENT_BARS
        == market_evidence.IGNITION_RECLAIM_RECENT_BARS
        == 2
    )
    assert (
        gs393.EXTREME_DO_NOT_CHASE_TOP_TTL_SECONDS
        == presentation_audio.EXTREME_DO_NOT_CHASE_TOP_TTL_SECONDS
        == 180.0
    )


def test_gs393_state_helper_delegates_to_thesis_state():
    base = {
        "state": thesis_state.DEVELOPING,
        "color": thesis_state.STATE_COLORS[thesis_state.DEVELOPING],
        "reason": "developing",
        "next_step": "wait",
        "attention_provenance": [],
    }
    original = lambda _record: base
    assert gs393._state_with_ignition(original, _record()) == thesis_state.state_with_ignition(
        original,
        _record(),
    )


def test_gs393_install_preserves_cross_authority_order(monkeypatch):
    calls = []

    monkeypatch.setattr(thesis_state, "install_ignition_state", lambda: calls.append("state"))
    monkeypatch.setattr(
        presentation_audio,
        "install_extreme_banner_decay",
        lambda: calls.append("presentation"),
    )
    monkeypatch.setattr(
        replay_validation,
        "install_ignition_validation_sequence",
        lambda: calls.append("replay"),
    )

    gs393.install()
    assert calls == ["state", "presentation", "replay"]


def test_gs393_meaning_has_authoritative_homes():
    market = Path("mide/authorities/market_evidence.py").read_text(encoding="utf-8")
    thesis = Path("mide/authorities/thesis_state.py").read_text(encoding="utf-8")
    presentation = Path("mide/authorities/presentation_audio.py").read_text(encoding="utf-8")
    replay = Path("mide/authorities/replay_validation.py").read_text(encoding="utf-8")
    legacy = Path("mide/gs393_ignition_truth_extreme_decay.py").read_text(encoding="utf-8")

    assert "def ignition_evidence(" in market
    assert "def state_with_ignition(" in thesis
    assert "def install_extreme_banner_decay(" in presentation
    assert "def build_validation_sequence_with_ignition(" in replay
    assert "Compatibility coordinator" in legacy
    assert "def _supporting_flow(" not in legacy
    assert "def build_with_ignition(" not in legacy
