"""Phase 22: GS511 Entry Window VWAP truth belongs to Presentation + Audio."""

from pathlib import Path

from mide import escalation
from mide import gs511_entry_window_vwap_truth as gs511
from mide import live_opportunity_feed
from mide.authorities import presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def _record(**updates):
    record = {
        "symbol": "NCPL",
        "candidate_status": "Entry Ready",
        "status": "PASS",
        "vwap_relation": "above",
        "vwap_distance_pct": 1.2,
        "supertrend_bullish": True,
        "qualified_for_entry": False,
    }
    record.update(updates)
    return record


def test_gs511_compatibility_seams_delegate_to_presentation_audio():
    assert (
        gs511.NEAR_VWAP_MAX_PCT
        == presentation_audio.ENTRY_WINDOW_NEAR_VWAP_MAX_PCT
    )
    assert gs511._near_vwap is presentation_audio.entry_window_near_vwap
    assert gs511._number is presentation_audio._entry_window_number


def test_authority_install_preserves_two_percent_entry_window_truth():
    presentation_audio.install_entry_window_vwap_truth()

    assert (
        escalation.escalation_state(_record(vwap_distance_pct=1.9))
        == escalation.ENTRY_WINDOW_OPEN
    )
    assert (
        escalation.escalation_state(_record(vwap_distance_pct=4.25))
        == escalation.WATCH_CLOSELY
    )
    assert (
        escalation.escalation_state(_record(vwap_distance_pct=5.27))
        == escalation.TOO_EXTENDED
    )


def test_authority_install_keeps_live_feed_bound_to_corrected_snapshot():
    presentation_audio.install_entry_window_vwap_truth()
    record = _record(vwap_distance_pct=3.0)

    assert (
        live_opportunity_feed.escalation_snapshot(record)["state"]
        == escalation.WATCH_CLOSELY
    )
    assert (
        live_opportunity_feed.opportunity_feed_snapshot([record])["NCPL"]["entry_open"]
        is False
    )


def test_gs511_source_is_compatibility_facade_not_duplicate_implementation():
    source = (ROOT / "mide/gs511_entry_window_vwap_truth.py").read_text(
        encoding="utf-8"
    )

    assert "from mide.authorities import presentation_audio as _presentation" in source
    assert "def _near_vwap(" not in source
    assert "def escalation_state(" not in source
    assert "def escalation_snapshot(" not in source


def test_phase22_facade_remains_presentation_only():
    source = (ROOT / "mide/gs511_entry_window_vwap_truth.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "opportunity_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "place_order(",
        "submit_order(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in source for token in forbidden)
