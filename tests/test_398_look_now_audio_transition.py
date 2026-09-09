from mide import early_setup, escalation
from mide import gs311_unified_voice as voice
from mide import gs398_look_now_audio_transition as gs398
from mide.gs365_chime_semantic_classifier import semantic_chime_count
from mide.gs366_rerun_alert_dedupe import should_deliver_alert


def _look_now_change(symbol="GCDT"):
    return {"symbol": symbol, "from": "DEVELOPING", "to": "LOOK NOW"}


def test_new_visible_look_now_builds_distinct_tier2_phrase(monkeypatch):
    monkeypatch.setattr(voice, "unified_state_changes", lambda _records: [_look_now_change()])

    phrase = gs398.look_now_alert_phrase([{"symbol": "GCDT"}])

    assert phrase == "GCDT. LOOK NOW."
    assert semantic_chime_count(phrase) == 2


def test_no_new_look_now_transition_does_not_manufacture_alert(monkeypatch):
    monkeypatch.setattr(voice, "unified_state_changes", lambda _records: [])

    assert gs398.look_now_alert_phrase([{"symbol": "GCDT"}]) == ""
    assert gs398.prioritize_visible_look_now_alert(
        [{"symbol": "GCDT"}], "Watching 1."
    ) == "Watching 1."


def test_look_now_outranks_routine_but_never_tier3(monkeypatch):
    monkeypatch.setattr(voice, "unified_state_changes", lambda _records: [_look_now_change()])
    rows = [{"symbol": "GCDT"}]

    assert gs398.prioritize_visible_look_now_alert(rows, "Watching 2.") == (
        "GCDT. LOOK NOW."
    )
    assert gs398.prioritize_visible_look_now_alert(
        rows, "ABCD. WATCH FOR ENTRY."
    ) == "ABCD. WATCH FOR ENTRY."
    assert gs398.blocks_lower_priority_coiling("GCDT. LOOK NOW.") is True
    assert gs398.blocks_lower_priority_coiling("GCDT. Coiling.") is False


def test_multiple_new_look_now_transitions_keep_explicit_mid_tier_language(monkeypatch):
    monkeypatch.setattr(
        voice,
        "unified_state_changes",
        lambda _records: [_look_now_change("GCDT"), _look_now_change("SST")],
    )

    phrase = gs398.look_now_alert_phrase([{"symbol": "GCDT"}, {"symbol": "SST"}])

    assert phrase == "GCDT. LOOK NOW. 1 additional LOOK NOW opportunity."
    assert semantic_chime_count(phrase) == 2


def test_installed_state_signature_includes_look_now_transition(monkeypatch):
    monkeypatch.setattr(voice, "unified_state_changes", lambda _records: [_look_now_change()])

    changes = escalation.escalation_state_changes([{"symbol": "GCDT"}])

    assert changes
    assert changes[0]["symbol"] == "GCDT"
    assert changes[0]["to"] == "LOOK NOW"
    assert getattr(escalation.escalation_state_changes, "_gs398_look_now_signature", False)


def test_visible_look_now_suppresses_only_lower_tier_coiling_delivery(monkeypatch):
    monkeypatch.setattr(voice, "unified_state_changes", lambda _records: [_look_now_change()])
    record = {
        "symbol": "GCDT",
        "coiled_alert_eligible": True,
        "qualified_for_watch": True,
        "vwap_distance_pct": 0.4,
    }

    entered, active = early_setup.newly_entered_symbols([record], set())

    assert entered == []
    assert active == {"GCDT"}
    assert getattr(early_setup.newly_entered_symbols, "_gs398_look_now_priority", False)


def test_look_now_delivery_is_exactly_once_per_completed_scan(monkeypatch):
    monkeypatch.setattr(voice, "unified_state_changes", lambda _records: [_look_now_change()])
    phrase = gs398.look_now_alert_phrase([{"symbol": "GCDT"}])
    state = {}

    first = should_deliver_alert(
        state,
        sound_path="assets/alert.wav",
        phrase=phrase,
        voice_name="System Default",
    )
    second = should_deliver_alert(
        state,
        sound_path="assets/alert.wav",
        phrase=phrase,
        voice_name="System Default",
    )

    assert first is True
    assert second is False
