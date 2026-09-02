from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from mide import ui
from mide.gs366_rerun_alert_dedupe import (
    _SUPPRESSED_COUNT_KEY,
    should_deliver_alert,
)


def _state(completed_at: datetime) -> dict:
    scan = SimpleNamespace(completed_at=completed_at)
    context = SimpleNamespace(
        completed_scan=scan,
        provider_instance=None,
        pipeline=None,
    )
    return {"scan_context": context}


def _allow(state: dict, phrase: str, voice: str = "System Default") -> bool:
    return should_deliver_alert(
        state,
        sound_path="assets/alert.wav",
        phrase=phrase,
        voice_name=voice,
    )


def test_same_alert_is_delivered_only_once_for_same_completed_scan():
    state = _state(datetime(2026, 9, 2, 16, 58, 33, tzinfo=timezone.utc))

    assert _allow(state, "VIVK. Developing.") is True
    assert _allow(state, "VIVK. Developing.") is False
    assert _allow(state, "VIVK. Developing.") is False
    assert state[_SUPPRESSED_COUNT_KEY] == 2


def test_distinct_alerts_in_same_scan_are_each_allowed_once():
    state = _state(datetime(2026, 9, 2, 16, 58, 33, tzinfo=timezone.utc))

    assert _allow(state, "VIVK. Developing.") is True
    assert _allow(state, "LHAI. Developing.") is True
    assert _allow(state, "VIVK. Developing.") is False


def test_same_phrase_is_allowed_again_on_new_completed_scan():
    first = datetime(2026, 9, 2, 16, 58, 33, tzinfo=timezone.utc)
    state = _state(first)

    assert _allow(state, "MNTK. Chase / Wait.") is True
    assert _allow(state, "MNTK. Chase / Wait.") is False

    state["scan_context"].completed_scan = SimpleNamespace(
        completed_at=first + timedelta(minutes=1)
    )
    assert _allow(state, "MNTK. Chase / Wait.") is True


def test_voice_or_phrase_change_is_not_mistaken_for_duplicate():
    state = _state(datetime(2026, 9, 2, 16, 58, 33, tzinfo=timezone.utc))

    assert _allow(state, "LOOK NOW.", "Voice A") is True
    assert _allow(state, "LOOK NOW.", "Voice B") is True
    assert _allow(state, "WATCH FOR ENTRY.", "Voice B") is True


def test_empty_phrase_is_not_blocked_by_delivery_guard():
    state = _state(datetime(2026, 9, 2, 16, 58, 33, tzinfo=timezone.utc))
    assert _allow(state, "") is True


def test_gs366_is_final_installed_audio_delivery_layer():
    assert getattr(ui.play_alert, "_gs366_rerun_alert_dedupe", False)
    assert getattr(ui.play_alert, "_gs365_chime_semantics", False)
