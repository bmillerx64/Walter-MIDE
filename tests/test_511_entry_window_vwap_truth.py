from pathlib import Path

from mide import escalation
from mide import gs511_entry_window_vwap_truth as gs511
from mide import live_opportunity_feed


def _record(**updates):
    record = {
        "symbol": "NCPL",
        "candidate_status": "Entry Ready",
        "status": "PASS",
        "vwap_relation": "above",
        "vwap_distance_pct": 1.2,
        "supertrend_bullish": True,
        "participation_score": 75,
        "qualified_for_entry": False,
    }
    record.update(updates)
    return record


def test_entry_ready_inside_two_percent_keeps_entry_window():
    gs511.install()
    assert escalation.escalation_state(_record(vwap_distance_pct=1.9)) == escalation.ENTRY_WINDOW_OPEN


def test_entry_ready_above_two_percent_cannot_open_entry_window():
    gs511.install()
    record = _record(vwap_distance_pct=4.25)

    assert escalation.escalation_state(record) == escalation.WATCH_CLOSELY
    assert escalation.escalation_snapshot(record)["state"] == escalation.WATCH_CLOSELY
    assert live_opportunity_feed.opportunity_feed_snapshot([record])["NCPL"]["entry_open"] is False


def test_above_five_percent_preserves_existing_too_extended_hard_stop():
    gs511.install()
    assert escalation.escalation_state(_record(vwap_distance_pct=5.27)) == escalation.TOO_EXTENDED


def test_below_vwap_entry_ready_never_opens_entry_window():
    gs511.install()
    record = _record(vwap_relation="below", vwap_distance_pct=-0.4)
    assert escalation.escalation_state(record) != escalation.ENTRY_WINDOW_OPEN
    assert live_opportunity_feed.opportunity_feed_snapshot([record])["NCPL"]["entry_open"] is False


def test_qualified_for_entry_still_obeys_same_near_vwap_presentation_guard():
    gs511.install()
    record = _record(
        candidate_status="Watching",
        qualified_for_entry=True,
        vwap_distance_pct=3.1,
    )
    assert escalation.escalation_state(record) == escalation.WATCH_CLOSELY


def test_feed_emits_too_extended_not_entry_open_when_crossing_two_percent():
    gs511.install()
    previous = live_opportunity_feed.opportunity_feed_snapshot(
        [_record(vwap_distance_pct=1.5)]
    )
    current = live_opportunity_feed.opportunity_feed_snapshot(
        [_record(vwap_distance_pct=3.0)]
    )
    events = live_opportunity_feed.opportunity_feed_changes(
        previous,
        current,
        __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    messages = [event["message"] for event in events]
    assert "ENTRY WINDOW OPEN" not in messages
    assert "Entry Window closed" in messages
    assert "Too extended" in messages


def test_startup_installs_gs511_before_app_runtime_imports():
    source = Path("mide/startup.py").read_text(encoding="utf-8")
    body = source.split("def ensure_late_runtime_installers() -> None:", 1)[1]
    assert "gs511_entry_window_vwap_truth" in source
    assert "install_gs511()" in body


def test_scope_lock_is_escalation_presentation_only():
    source = Path("mide/gs511_entry_window_vwap_truth.py").read_text(encoding="utf-8")
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
