from pathlib import Path

from mide import gs419_completed_scan_heartbeat as gs419


def test_gs419_heartbeat_markup_is_tier1_and_requires_completed_scan(monkeypatch):
    from mide import gs367_browser_audio_broker as broker
    from mide import gs366_rerun_alert_dedupe as dedupe

    monkeypatch.setattr(dedupe, "completed_scan_token", lambda _state: "scan-419")
    monkeypatch.setattr(
        broker,
        "browser_broker_markup",
        lambda token, tier: f"<script>\n(() => {{\ntoken={token};tier={tier};\n}})();\n</script>",
    )
    markup = gs419.heartbeat_markup({})
    assert "token=scan-419;tier=1" in markup

    monkeypatch.setattr(dedupe, "completed_scan_token", lambda _state: "no-completed-scan")
    assert gs419.heartbeat_markup({}) == ""


def test_gs419_heartbeat_respects_existing_audible_toggle_in_browser():
    base = "<script>\n(() => {\nconst x = 1;\n})();\n</script>"
    markup = gs419._respect_alert_toggle(base)

    assert "Audible watch/advance alerts" in markup
    assert "if (matched && !enabled) return;" in markup
    assert "const x = 1;" in markup


def test_gs419_does_not_replace_escalation_alert_semantics():
    module = Path("mide/gs419_completed_scan_heartbeat.py").read_text(encoding="utf-8")

    assert "escalation.escalation_alert_phrase =" not in module
    assert "HEARTBEAT_PHRASE" not in module


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
