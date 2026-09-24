"""Phase 59: GS529/GS532 observational shadows live in Replay / Validation."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs529_entry_ready_shadow_calibration as gs529
from mide import gs532_retest_entry_shadow as gs532
from mide.authorities import replay_validation


ROOT = Path(__file__).resolve().parents[1]


def test_phase59_historical_calibration_seams_are_preserved():
    assert gs529._SHADOW_RUNG_ALLOWLIST == {"1m", "3m"}
    assert gs532.VWAP_MIN_PCT == -0.75
    assert gs532.VWAP_MAX_PCT == 2.0
    assert gs532.MIN_PARTICIPATION == 60.0
    assert gs532.MIN_EXPANSION == 55.0


def test_phase59_gs529_delegates_but_keeps_monkeypatch_seam(monkeypatch):
    monkeypatch.setattr(
        gs529,
        "_fresh_progression",
        lambda _record: {
            "active": True,
            "new_rung": "1m",
            "fresh_rungs": ["30s", "1m"],
        },
    )
    trigger = {
        "passed": False,
        "checks": [
            {
                "condition": "supertrend_flip",
                "passed": False,
            }
        ],
    }
    result = gs529.shadow_entry_calibration(
        {},
        trigger=trigger,
        structure_gate={"passed": True},
    )
    assert result["shadow_entry_ready"] is True
    assert result["recovered_by_progression"] is True
    assert result["trading_authority_changed"] is False


def test_phase59_stale_replay_generation_fails_closed(monkeypatch):
    monkeypatch.setattr(gs529, "_replay", lambda: SimpleNamespace())
    monkeypatch.setattr(gs532, "_replay", lambda: SimpleNamespace())

    trigger = {
        "passed": False,
        "checks": [
            {
                "condition": "supertrend_flip",
                "passed": False,
            }
        ],
    }
    entry_shadow = gs529.shadow_entry_calibration(
        {},
        trigger=trigger,
        structure_gate={"passed": True},
    )
    assert entry_shadow["shadow_entry_ready"] is False
    assert entry_shadow["recovered_by_progression"] is False
    assert entry_shadow["trading_authority_changed"] is False

    retest_shadow = gs532.retest_entry_shadow({})
    assert retest_shadow["shadow_entry_ready"] is False
    assert retest_shadow["trading_authority_changed"] is False


def test_phase59_facades_are_lazy_and_replay_owns_implementation():
    source529 = (
        ROOT / "mide/gs529_entry_ready_shadow_calibration.py"
    ).read_text(encoding="utf-8")
    source532 = (
        ROOT / "mide/gs532_retest_entry_shadow.py"
    ).read_text(encoding="utf-8")
    replay = (
        ROOT / "mide/authorities/replay_validation.py"
    ).read_text(encoding="utf-8")

    assert "def _replay(" in source529
    assert "def _replay(" in source532

    for name in (
        "entry_shadow_fresh_progression",
        "shadow_entry_calibration",
        "retest_entry_shadow",
    ):
        assert f"def {name}(" in replay

    assert "from .gs514_retest_event_memory import discipline_sequence" not in source532
    assert "from . import gs455_early_ignition_3m_confirmation as gs455" not in source529


def test_phase59_scope_remains_observational_only():
    replay = (
        ROOT / "mide/authorities/replay_validation.py"
    ).read_text(encoding="utf-8")
    start = replay.index("# GS529/GS532 observational Entry Ready shadow validation")
    end = replay.index("# GS425 live-scan latency truth recorder", start)
    block = replay[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "candidate_status =",
        "place_order(",
        "submit_order(",
        "play_alert(",
    )
    assert not any(token in block for token in forbidden)
    assert block.count('"trading_authority_changed": False') >= 2
    assert 'ENTRY_SHADOW_AUTHORITY = "OBSERVATIONAL_ONLY"' in block


def test_phase59_scanner_still_persists_shadows_without_consuming_them_for_entry():
    scanner = (
        ROOT / "mide/scanner_v2.py"
    ).read_text(encoding="utf-8")

    assert "entry_ready_shadow = shadow_entry_calibration(" in scanner
    assert "retest_ready_shadow = retest_entry_shadow(record)" in scanner
    entry_start = scanner.index("entry_qualified = qualified_for_entry(")
    entry_end = scanner.index(
        'record["qualified_for_entry"] = entry_qualified',
        entry_start,
    )
    live_entry_slice = scanner[entry_start:entry_end]
    assert "entry_ready_shadow" not in live_entry_slice
    assert "retest_ready_shadow" not in live_entry_slice
