from pathlib import Path
from types import SimpleNamespace

from mide import gs419_completed_scan_heartbeat as gs419


def test_gs419_heartbeat_when_scan_has_no_existing_alert():
    records = [
        {"symbol": "DEV", "candidate_status": "Watching", "opportunity_state": "DEVELOPING"},
        {"symbol": "CHASE", "candidate_status": "Watching", "opportunity_state": "CHASE / WAIT"},
    ]
    assert gs419.heartbeat_phrase(records, "") == gs419.HEARTBEAT_PHRASE


def test_gs419_preserves_existing_higher_priority_phrase():
    assert (
        gs419.heartbeat_phrase([], "XYZ. LOOK NOW.")
        == "XYZ. LOOK NOW."
    )


def test_gs419_leaves_strengthening_and_entry_ready_to_existing_app_fallback():
    strengthening = [{"symbol": "AAA", "candidate_status": "Strengthening"}]
    entry_ready = [{"symbol": "BBB", "candidate_status": "Entry Ready"}]

    assert gs419.heartbeat_phrase(strengthening, "") == ""
    assert gs419.heartbeat_phrase(entry_ready, "") == ""


def test_gs419_heartbeat_markup_is_tier1_and_requires_completed_scan(monkeypatch):
    from mide import gs367_browser_audio_broker as broker
    from mide import gs366_rerun_alert_dedupe as dedupe

    monkeypatch.setattr(dedupe, "completed_scan_token", lambda _state: "scan-419")
    monkeypatch.setattr(
        broker,
        "browser_broker_markup",
        lambda token, tier: f"token={token};tier={tier}",
    )
    assert gs419.heartbeat_markup({}) == "token=scan-419;tier=1"

    monkeypatch.setattr(dedupe, "completed_scan_token", lambda _state: "no-completed-scan")
    assert gs419.heartbeat_markup({}) == ""


def test_gs419_installs_after_gs414_and_does_not_touch_trading_authority():
    chain = Path("mide/gs414_final_enriched_opportunity_order.py").read_text(encoding="utf-8")
    module = Path("mide/gs419_completed_scan_heartbeat.py").read_text(encoding="utf-8")

    assert "_install_gs419()" in chain
    assert chain.index("ui.render_escalation_engine = render_with_final_enriched_order") < chain.rindex("_install_gs419()")

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "participation_score =",
        "expansion_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "opportunity_state =",
        "candidate_status =",
    )
    assert not any(token in module for token in forbidden)
