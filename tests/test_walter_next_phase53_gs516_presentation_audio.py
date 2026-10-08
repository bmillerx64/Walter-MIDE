"""Phase 53/GS653: browser audio health remains behind Presentation + Audio."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs516_visible_alert_audio_health as gs516
from mide.authorities import presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def test_gs516_facade_delegates_markup(monkeypatch):
    monkeypatch.setattr(
        presentation_audio,
        "alert_audio_health_markup",
        lambda: "<div>authority-health</div>",
    )
    assert gs516.alert_audio_health_markup() == "<div>authority-health</div>"


def test_phase53_stale_presentation_generation_is_nonfatal(monkeypatch):
    monkeypatch.setattr(gs516, "_presentation", lambda: SimpleNamespace())
    assert gs516.alert_audio_health_markup() == ""
    assert gs516.render_sidebar_audio_health(object()) is None
    assert gs516.install() is None


def test_gs653_presentation_authority_delegates_transport_to_single_owner_module():
    authority = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")
    guard = (ROOT / "mide/audio_guard_v2.py").read_text(encoding="utf-8")
    facade = (
        ROOT / "mide/gs516_visible_alert_audio_health.py"
    ).read_text(encoding="utf-8")

    assert "def alert_audio_health_markup(" in authority
    assert "from mide.audio_guard_v2 import alert_audio_health_markup as current" in authority
    assert "def render_sidebar_audio_health(" in authority

    assert "AUDIO GUARD ACTIVE · WEB AUDIO VOICE + BELL" in guard
    assert "decodeAudioData" in guard
    assert "createBufferSource" in guard
    assert "speechSynthesis" not in guard

    assert "Compatibility facade" in facade
    assert "def _presentation(" in facade


def test_phase53_scope_remains_alert_transport_presentation_only():
    source = (
        ROOT / "mide/gs516_visible_alert_audio_health.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "opportunity_score =",
        "candidate_status =",
        "place_order(",
        "submit_order(",
        "request_scan(",
    )
    assert not any(token in source for token in forbidden)
