"""Phase 78: GS404 reset/retest evidence belongs to Market Evidence."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs404_reset_retest_look_now as gs404
from mide.authorities import market_evidence


ROOT = Path(__file__).resolve().parents[1]


def _record(**updates):
    record = {
        "symbol": "ZTG",
        "vwap_distance_pct": -0.86,
        "source_bar_age_seconds": 45.0,
        "discovery_reasons": [
            "Webull native: day_gainers",
            "Webull native: five_minute_movers",
        ],
        "timeframes": {
            "1m": {
                "above_vwap": False,
                "supertrend": True,
            },
        },
        "participation_score": 31.1,
        "volume_acceleration": 3.32,
        "dollar_flow_acceleration": 28.57,
        "opportunity_pulse_previous": {
            "vwap_distance_pct": 7.985,
        },
    }
    record.update(updates)
    return record


def test_phase78_authority_preserves_reset_retest_evidence():
    evidence = market_evidence.reset_retest_attention_evidence(
        _record()
    )
    assert evidence["recent"] is True
    assert evidence["trigger"] == "RESET_RETEST_NEAR_VWAP"
    assert evidence["previous_extended"] is True
    assert evidence["near_vwap_now"] is True
    assert evidence["one_minute_supertrend_bullish"] is True
    assert evidence["participation_present"] is True
    assert evidence["flow_present"] is True
    assert evidence["current_webull_radar_attention"] is True
    assert evidence["fresh_source"] is True
    assert evidence["entry_authority_unchanged"] is True


def test_phase78_authority_preserves_existing_thresholds():
    assert market_evidence.reset_retest_eligible(
        _record(
            opportunity_pulse_previous={
                "vwap_distance_pct": 4.99,
            }
        )
    ) is False
    assert market_evidence.reset_retest_eligible(
        _record(vwap_distance_pct=2.01)
    ) is False
    assert market_evidence.reset_retest_eligible(
        _record(participation_score=19.9)
    ) is False
    assert market_evidence.reset_retest_eligible(
        _record(
            volume_acceleration=0.99,
            dollar_flow_acceleration=1.24,
        )
    ) is False


def test_phase78_legacy_evidence_name_delegates_lazily(monkeypatch):
    sentinel = {
        "recent": True,
        "trigger": "AUTHORITY",
    }
    monkeypatch.setattr(
        market_evidence,
        "reset_retest_attention_evidence",
        lambda _record: dict(sentinel),
    )
    assert gs404.reset_retest_attention_evidence({}) == sentinel


def test_phase78_stale_market_generation_preserves_local_fallback(monkeypatch):
    monkeypatch.setattr(
        gs404,
        "_market_evidence",
        lambda: SimpleNamespace(),
    )
    evidence = gs404.reset_retest_attention_evidence(
        _record()
    )
    assert evidence["recent"] is True
    assert evidence["trigger"] == "RESET_RETEST_NEAR_VWAP"


def test_phase78_state_and_presentation_semantics_remain_in_gs404_for_later_slices():
    legacy = (
        ROOT / "mide/gs404_reset_retest_look_now.py"
    ).read_text(encoding="utf-8")
    assert "def augment_reset_retest_records(" in legacy
    assert "def reset_retest_opportunity_state(" in legacy
    assert "def install(" in legacy


def test_phase78_evidence_meaning_lives_in_market_evidence():
    legacy = (
        ROOT / "mide/gs404_reset_retest_look_now.py"
    ).read_text(encoding="utf-8")
    authority = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")

    assert "def reset_retest_attention_evidence(" in authority
    assert "def reset_retest_eligible(" in authority
    assert '"reset_retest_attention_evidence"' in legacy
    assert '"reset_retest_eligible"' in legacy


def test_phase78_scope_is_market_evidence_only():
    source = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")
    start = source.index("# GS404 reset/retest attention evidence")
    end = source.index("# GS456 canonical 30s VWAP / SuperTrend alignment evidence", start)
    block = source[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "opportunity_state =",
        "place_order(",
        "submit_order(",
        "play_alert(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in block for token in forbidden)
