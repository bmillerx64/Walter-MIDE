"""Phase 62: GS455 ordered maturation progression belongs to Market Evidence."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs455_early_ignition_3m_confirmation as gs455
from mide.authorities import market_evidence


ROOT = Path(__file__).resolve().parents[1]


def test_phase62_historical_calibration_seams_remain_in_gs455():
    assert gs455.CROSSOVER_LADDER == (
        "30s",
        "1m",
        "3m",
        "5m",
        "10m",
        "15m",
    )
    assert gs455.LOOK_NOW_MAX_VWAP_DISTANCE_PCT == 5.0
    assert gs455._NEW_WINDOWS_SECONDS["30s"] == 90.0
    assert gs455._NEW_WINDOWS_SECONDS["3m"] == 240.0


def test_phase62_market_evidence_uses_historical_rung_seams(monkeypatch):
    events = {
        "30s": {
            "crossed": True,
            "current_confirmed": True,
            "new": False,
            "timestamp": "2026-09-15T10:00:00-04:00",
        },
        "1m": {
            "crossed": True,
            "current_confirmed": True,
            "new": True,
            "timestamp": "2026-09-15T10:01:00-04:00",
        },
    }
    monkeypatch.setattr(
        gs455,
        "_rung_event",
        lambda _record, label: dict(events.get(label) or {}),
    )
    monkeypatch.setattr(
        gs455,
        "_supporting_flow",
        lambda _record: True,
    )
    monkeypatch.setattr(
        gs455,
        "_halted",
        lambda _record: False,
    )

    progression = gs455.crossover_progression(
        {"vwap_relation": "above"}
    )
    signal = gs455.progression_signal(
        {"vwap_relation": "above"}
    )

    assert progression["active_rungs"] == ["30s", "1m"]
    assert progression["ordered"] is True
    assert progression["stage"] == "IGNITION"
    assert signal["active"] is True
    assert signal["new_rung"] == "1m"


def test_phase62_stale_market_evidence_generation_fails_closed(monkeypatch):
    monkeypatch.setattr(
        gs455,
        "_market_evidence",
        lambda: SimpleNamespace(),
    )

    progression = gs455.crossover_progression(
        {"vwap_relation": "above"}
    )
    signal = gs455.progression_signal(
        {
            "vwap_relation": "above",
            "vwap_distance_pct": 1.0,
        }
    )

    assert progression["active_rungs"] == []
    assert progression["stage"] == "NONE"
    assert signal["active"] is False
    assert signal["new_rung"] is None
    assert signal["vwap_distance_pct"] == 1.0


def test_phase62_progression_meaning_lives_in_market_evidence():
    legacy = (
        ROOT / "mide/gs455_early_ignition_3m_confirmation.py"
    ).read_text(encoding="utf-8")
    authority = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")

    assert "def _market_evidence(" in legacy
    assert "def crossover_progression(record: dict)" in authority
    assert "def progression_signal(record: dict)" in authority

    start = legacy.index("def crossover_progression(record: dict)")
    end = legacy.index("def _state_with_progression(", start)
    facade_block = legacy[start:end]

    assert "Compatibility facade" in facade_block
    assert "active_rungs.append(" not in facade_block
    assert "new_rung and not _halted" not in facade_block


def test_phase62_scope_remains_market_evidence_only():
    authority = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")
    start = authority.index("# GS455 ordered ST/VWAP maturation progression evidence")
    end = authority.index("# GS460/GS461 ST compression", start)
    block = authority[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "candidate_status =",
        "place_order(",
        "submit_order(",
        "play_alert(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in block for token in forbidden)


def test_phase62_existing_gs455_install_boundaries_stay_put():
    source = (
        ROOT / "mide/gs455_early_ignition_3m_confirmation.py"
    ).read_text(encoding="utf-8")

    assert "def _install_existing_maturation_source(" in source
    assert "def _install_prefilter(" in source
    assert "def _install_state(" in source
    assert "def _install_alert_priority(" in source
    assert "_install_existing_maturation_source()" in source
    assert "_install_prefilter()" in source
    assert "_install_state()" in source
    assert "_install_alert_priority()" in source
