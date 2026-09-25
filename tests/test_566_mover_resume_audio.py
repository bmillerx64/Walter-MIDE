from pathlib import Path

from mide import escalation
from mide.authorities import market_evidence, presentation_audio


def _event(
    symbol="MSGY",
    *,
    pct=100.0,
    price=4.0,
    volume=1_000_000,
    event_type="strategy_leader",
    native_fast_mover=False,
):
    return {
        "symbol": symbol,
        "pct_change": pct,
        "rank": 1,
        "price": price,
        "volume": volume,
        "attention_only": True,
        "event_type": event_type,
        "native_fast_mover": native_fast_mover,
    }


def test_gs566_strategy_leader_can_generate_initial_mover_audio():
    presentation_audio.reset_native_market_event_audio_state()

    phrase = presentation_audio.native_market_event_audio_phrase(
        [],
        [_event(symbol="CNET", pct=28.8, price=1.765)],
    )

    assert "CNET. MARKET LEADER. LOOK NOW." in phrase


def test_gs566_material_advance_rearms_same_current_mover():
    presentation_audio.reset_native_market_event_audio_state()
    first = _event(
        pct=202.0,
        price=5.95,
        volume=23_000_000,
        event_type="extreme_mover",
        native_fast_mover=True,
    )
    second = _event(
        pct=358.5,
        price=9.03,
        volume=27_900_000,
        event_type="extreme_mover",
        native_fast_mover=True,
    )

    assert "LOOK NOW" in presentation_audio.native_market_event_audio_phrase([], [first])
    phrase = presentation_audio.native_market_event_audio_phrase([], [second])

    assert "MSGY. MOVER ADVANCE. LOOK NOW." in phrase
    assert "9.03" in phrase


def test_gs566_native_tape_freeze_then_change_emits_resume_cue():
    presentation_audio.reset_native_market_event_audio_state()
    frozen = _event(
        pct=202.0,
        price=5.95,
        volume=23_270_000,
        event_type="extreme_mover",
        native_fast_mover=True,
    )

    # First sighting announces the mover. Two unchanged follow-up scans establish
    # a possible trading pause without claiming exchange halt truth.
    presentation_audio.native_market_event_audio_phrase([], [frozen])
    presentation_audio.native_market_event_audio_phrase([], [frozen])
    pause_phrase = presentation_audio.native_market_event_audio_phrase([], [frozen])
    assert "CHECK TRADING STATUS. LOOK NOW." in pause_phrase
    assert "Possible trading pause or halt" in pause_phrase

    resumed = dict(frozen, price=9.03, volume=27_910_000, pct_change=358.5)
    phrase = presentation_audio.native_market_event_audio_phrase([], [resumed])

    assert "MSGY. FRESH PRINTS RESUMED. LOOK NOW." in phrase
    assert "Do not chase" in phrase


def test_gs566_confirmed_halt_can_emit_halt_release_when_fresh_prints_return():
    presentation_audio.reset_native_market_event_audio_state()
    halted_event = _event(
        symbol="RDGT",
        pct=36.9,
        price=1.24,
        volume=143_200,
        event_type="five_minute_fast_mover",
        native_fast_mover=True,
    )
    halted_record = {
        "symbol": "RDGT",
        "halted": True,
        "source_bar_age_seconds": 121.0,
    }

    pause_phrase = presentation_audio.native_market_event_audio_phrase(
        [halted_record],
        [halted_event],
    )
    assert "CHECK TRADING STATUS. LOOK NOW." in pause_phrase

    resumed_record = {
        "symbol": "RDGT",
        "halted": False,
        "source_bar_age_seconds": 5.0,
    }
    resumed_event = dict(halted_event, price=1.55, volume=250_000, pct_change=70.0)
    phrase = presentation_audio.native_market_event_audio_phrase(
        [resumed_record],
        [resumed_event],
    )

    assert "RDGT. HALT RELEASE. LOOK NOW." in phrase


def test_gs566_senior_candidate_alert_does_not_consume_waiting_mover(monkeypatch):
    presentation_audio.reset_native_market_event_audio_state()
    monkeypatch.setattr(
        presentation_audio,
        "_streamlit_completed_scan_market_events",
        lambda: [_event(symbol="CNET", pct=28.8, price=1.765)],
    )
    calls = {"count": 0}

    def established(_records):
        calls["count"] += 1
        return "ALPHA. LOOK NOW." if calls["count"] == 1 else ""

    monkeypatch.setattr(escalation, "escalation_alert_phrase", established)
    presentation_audio.install_native_market_event_audio()

    assert escalation.escalation_alert_phrase([]) == "ALPHA. LOOK NOW."
    retry = escalation.escalation_alert_phrase([])

    assert "CNET. MARKET LEADER. LOOK NOW." in retry


def test_gs566_app_dedupe_key_includes_actual_spoken_phrase():
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("elif alerts and alert_phrase:")
    block = source[start : start + 1400]

    assert "alert_delivery_key" in block
    assert '" ".join(str(alert_phrase).split())' in block
    assert "state_change_signature" in block
    assert "alert_delivery_key != st.session_state.last_escalation_alert" in block
