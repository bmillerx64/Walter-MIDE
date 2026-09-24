"""Phase 67: GS455 rung extraction belongs to Market Evidence."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs455_early_ignition_3m_confirmation as gs455
from mide.authorities import market_evidence


ROOT = Path(__file__).resolve().parents[1]


def test_phase67_30s_tripwire_rung_semantics_are_preserved():
    rung = market_evidence.thirty_second_progression_rung(
        {
            "supertrend_30s_bullish": True,
            "supertrend_30s_last_flip_timestamp": "2026-09-15T10:17:00-04:00",
            "supertrend_30s_last_flip_age_seconds": 20.0,
        }
    )
    assert rung["timeframe"] == "30s"
    assert rung["crossed"] is True
    assert rung["recent"] is True
    assert rung["new"] is True
    assert rung["current_confirmed"] is True
    assert rung["kind"] == "canonical_30s_tripwire_flip"


def test_phase67_1m_canonical_event_keeps_enriched_current_confirmation():
    event = market_evidence.progression_rung_event(
        {
            "st_vwap_cross_events": {
                "1m": {
                    "timeframe": "1m",
                    "crossed": True,
                    "timestamp": "2026-09-15T10:20:00-04:00",
                }
            },
            "timeframes": {
                "1m": {
                    "above_vwap": True,
                    "supertrend": True,
                    "st_vwap_line_cross": {
                        "current_confirmed": True,
                    },
                }
            },
        },
        "1m",
    )
    assert event["crossed"] is True
    assert event["current_confirmed"] is True
    assert event["timestamp"] == "2026-09-15T10:20:00-04:00"


def test_phase67_30s_authority_preserves_gs456_mutable_wrapper_seam(monkeypatch):
    sentinel = {
        "timeframe": "30s",
        "crossed": True,
        "recent": True,
        "new": True,
        "timestamp": "sentinel",
        "age_seconds": 0.0,
        "current_confirmed": True,
        "kind": "sentinel",
    }
    monkeypatch.setattr(
        gs455,
        "_thirty_second_rung",
        lambda _record: dict(sentinel),
    )
    assert market_evidence.progression_rung_event({}, "30s") == sentinel


def test_phase67_stale_market_evidence_generation_fails_closed(monkeypatch):
    legacy_30s = getattr(
        gs455._thirty_second_rung,
        "_gs456_original",
        gs455._thirty_second_rung,
    )
    monkeypatch.setattr(
        gs455,
        "_market_evidence",
        lambda: SimpleNamespace(),
    )
    rung = legacy_30s({"symbol": "TEST"})
    assert rung["crossed"] is False
    assert rung["current_confirmed"] is False
    assert gs455._rung_event({"symbol": "TEST"}, "3m") == {}


def test_phase67_rung_logic_lives_in_market_evidence_with_lazy_legacy_facades():
    legacy = (
        ROOT / "mide/gs455_early_ignition_3m_confirmation.py"
    ).read_text(encoding="utf-8")
    authority = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")

    assert "def thirty_second_progression_rung(" in authority
    assert "def progression_rung_event(" in authority

    start = legacy.index("def _thirty_second_rung(")
    end = legacy.index("def _thesis_state(", start)
    facade = legacy[start:end]
    assert "_market_evidence()" in facade
    assert "thirty_second_tripwire" not in facade
    assert "st_vwap_cross_events" not in facade
    assert "multitimeframe_maturation" not in facade


def test_phase67_scope_is_market_evidence_only():
    source = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")
    start = source.index("# GS455 ordered ST/VWAP maturation progression evidence")
    end = source.index("# GS455 literal ST/VWAP line-cross enrichment", start)
    block = source[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "candidate_status =",
        "place_order(",
        "submit_order(",
        "escalation_alert_phrase",
        "LOOK NOW",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in block for token in forbidden)
