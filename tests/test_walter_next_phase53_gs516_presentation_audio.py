"""Phase 53: GS516 browser audio health belongs to Presentation + Audio."""

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
    monkeypatch.setattr(
        gs516,
        "_presentation",
        lambda: SimpleNamespace(),
    )

    assert gs516.alert_audio_health_markup() == ""
    assert gs516.render_sidebar_audio_health(object()) is None
    assert gs516.install() is None


def test_phase53_presentation_audio_owns_health_markup_and_renderer():
    authority = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")
    facade = (
        ROOT / "mide/gs516_visible_alert_audio_health.py"
    ).read_text(encoding="utf-8")

    assert "def alert_audio_health_markup(" in authority
    assert "def render_sidebar_audio_health(" in authority
    assert "__walterGS367ChimeBroker" in authority
    assert "AUDIO DISARMED AFTER RELOAD · RE-ARM" in authority
    assert "strike(base, 523.25)" in authority
    assert "strike(base + 0.42, 783.99)" in authority

    assert "Compatibility facade" in facade
    assert "def _presentation(" in facade
    assert "__walterGS367ChimeBroker" not in facade


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
