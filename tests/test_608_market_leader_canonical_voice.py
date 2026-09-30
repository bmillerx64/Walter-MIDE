from copy import deepcopy
from pathlib import Path

from mide.authorities import presentation_audio


def _leader_event():
    return {
        "symbol": "CNTB",
        "state": "WAIT FOR RESET",
        "pct_change": 63.6,
        "dollar_volume": 23_000_000,
        "dominance": 79.0,
        "vwap_distance_pct": 19.4,
        "alignment_score": 0,
        "pe_strength": 58,
        "headline": "Connect Biopharma reports positive Phase 2 COPD results",
        "guidance": (
            "Dominant current mover, but extended above VWAP. Keep the chart "
            "available; do not chase. Reassess only after a constructive reset."
        ),
        "provenance": ("WEBULL_TOP_MOVER",),
    }


def _primary_state(*, changed: bool):
    current = {
        "scan_token": "scan-2",
        "surface": "opportunity_first",
        "symbol": "VBIO",
        "state_label": "CHASE / WAIT",
        "event": None,
        "record": {"symbol": "VBIO"},
    }
    previous = {
        "scan_token": "scan-1",
        "surface": "opportunity_first",
        "symbol": "PFSA" if changed else "VBIO",
        "state_label": "DEVELOPING" if changed else "CHASE / WAIT",
        "record": {"symbol": "PFSA" if changed else "VBIO"},
    }
    return current, previous


def test_gs608_market_leader_markup_mirrors_catalyst_and_pe_strength():
    markup = presentation_audio.market_leader_markup(_leader_event())

    assert "MARKET LEADER RADAR" in markup
    assert "WATCH ONLY" in markup
    assert "NO ENTRY AUTHORITY" in markup
    assert "CNTB" in markup
    assert "WAIT FOR RESET" in markup
    assert "P/E Strength 58/100" in markup
    assert "Catalyst:" in markup
    assert "positive Phase 2 COPD results" in markup


def test_gs608_market_leader_event_carries_existing_catalyst(monkeypatch):
    from mide.gs305_second_wave_attention import attention_evaluation
    from mide.gs309_current_attention_mission import current_attention_provenance
    from mide.gs333_extreme_mover_operator_priority import prioritized_extreme_event

    monkeypatch.setattr(
        "mide.gs305_second_wave_attention.attention_evaluation",
        lambda _record: {"eligible": False},
    )
    monkeypatch.setattr(
        "mide.gs309_current_attention_mission.current_attention_provenance",
        lambda _record: ("WEBULL_TOP_MOVER",),
    )
    monkeypatch.setattr(
        "mide.gs333_extreme_mover_operator_priority.prioritized_extreme_event",
        lambda _rows: (None, None),
    )

    record = {
        "symbol": "CNTB",
        "pct_change": 63.6,
        "dollar_volume": 23_000_000,
        "market_dominance_score": 79.0,
        "vwap_distance_pct": 19.4,
        "vwap_relation": "above",
        "alignment_score": 0,
        "participation_surge_score": 71,
        "expansion_quality": 45,
        "headline": "Positive Phase 2 COPD results",
    }
    selected, event = presentation_audio.market_leader_candidate(
        [record],
        mission={},
    )

    assert selected is record
    assert event["symbol"] == "CNTB"
    assert event["state"] == "WAIT FOR RESET"
    assert event["pe_strength"] == 58
    assert event["headline"] == "Positive Phase 2 COPD results"


def test_gs608_unchanged_primary_allows_new_visible_market_leader_voice(monkeypatch):
    from mide import gs310_unified_opportunity_state as unified

    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda _record: {
            "state": "CHASE / WAIT",
            "reason": "Price is extended; wait for reset.",
        },
    )
    monkeypatch.setattr(unified, "look_now_context", lambda _record, _view: "")

    current, previous = _primary_state(changed=False)
    state = {
        "_walter_canonical_render_audio_focus": current,
        "_walter_previous_render_audio_focus": previous,
        "_walter_render_market_leader_audio": {
            "scan_token": "scan-2",
            "event": _leader_event(),
        },
    }

    event = presentation_audio.current_render_audio_event(
        state,
        expected_scan_token="scan-2",
    )

    assert event["triggered"] is True
    assert event["surface"] == "market_leader_radar"
    assert event["symbol"] == "CNTB"
    assert "Market leader radar" in event["phrase"]
    assert "WAIT FOR RESET" in event["phrase"]
    assert "P E strength 58" in event["phrase"]
    assert "Positive Phase 2 COPD results" in event["phrase"]
    assert "ENTRY READY" not in event["phrase"]


def test_gs608_changed_primary_keeps_first_voice_priority(monkeypatch):
    from mide import gs310_unified_opportunity_state as unified

    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda _record: {
            "state": "CHASE / WAIT",
            "reason": "Price is extended; wait for reset.",
        },
    )
    monkeypatch.setattr(unified, "look_now_context", lambda _record, _view: "")

    current, previous = _primary_state(changed=True)
    state = {
        "_walter_canonical_render_audio_focus": current,
        "_walter_previous_render_audio_focus": previous,
        "_walter_render_market_leader_audio": {
            "scan_token": "scan-2",
            "event": _leader_event(),
        },
    }

    event = presentation_audio.current_render_audio_event(
        state,
        expected_scan_token="scan-2",
    )

    assert event["triggered"] is True
    assert event["surface"] == "opportunity_first"
    assert event["symbol"] == "VBIO"
    assert "CNTB" not in event["phrase"]


def test_gs608_market_leader_is_once_per_symbol_state_headline_until_changed(monkeypatch):
    from mide import gs310_unified_opportunity_state as unified

    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda _record: {
            "state": "CHASE / WAIT",
            "reason": "Still extended.",
        },
    )
    monkeypatch.setattr(unified, "look_now_context", lambda _record, _view: "")

    current, previous = _primary_state(changed=False)
    state = {
        "_walter_canonical_render_audio_focus": current,
        "_walter_previous_render_audio_focus": previous,
        "_walter_render_market_leader_audio": {
            "scan_token": "scan-2",
            "event": _leader_event(),
        },
    }

    first = presentation_audio.current_render_audio_event(
        state,
        expected_scan_token="scan-2",
    )
    assert first["surface"] == "market_leader_radar"
    assert first["triggered"] is True

    presentation_audio.mark_render_audio_event_spoken(state, first)
    again = presentation_audio.current_render_audio_event(
        state,
        expected_scan_token="scan-2",
    )
    assert again["triggered"] is False

    changed = deepcopy(_leader_event())
    changed["state"] = "TRACK RE-IGNITION"
    state["_walter_render_market_leader_audio"]["event"] = changed
    later = presentation_audio.current_render_audio_event(
        state,
        expected_scan_token="scan-2",
    )
    assert later["triggered"] is True
    assert "TRACK RE-IGNITION" in later["phrase"]


def test_gs608_app_marks_secondary_delivery_inside_single_live_authority():
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("_audio_scan_token = (")
    end = source.index("\ntab_names = [", start)
    block = source[start:end]

    assert "current_render_audio_event(" in block
    assert "mark_render_audio_event_spoken(st.session_state, _audio_event)" in block
    assert "escalation_alert_phrase(" not in block
    assert "native_market_event_audio_phrase(" not in block


def test_gs608_scope_does_not_change_entry_or_trading_authority():
    source = Path("mide/authorities/presentation_audio.py").read_text(
        encoding="utf-8"
    )
    start = source.index("# Market-leader continuity presentation")
    end = source.index(
        "# Authoritative extreme-mover presentation semantics",
        start,
    )
    block = source[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "candidate_status =",
        "mission_rank =",
        "place_order(",
        "submit_order(",
        "request_scan(",
    )
    assert not any(token in block for token in forbidden)
