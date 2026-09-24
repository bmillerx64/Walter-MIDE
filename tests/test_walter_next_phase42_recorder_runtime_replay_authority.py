"""Phase 42: GS427/GS472 recorder runtime meaning belongs to Replay / Validation."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs427_flight_recorder_latency_hard_bind as gs427
from mide.authorities import replay_validation


ROOT = Path(__file__).resolve().parents[1]


def test_gs427_facade_delegates_active_recorder_globals(monkeypatch):
    marker = {"persist_replayable_scan": lambda *_a, **_k: None}
    monkeypatch.setattr(
        replay_validation,
        "active_recorder_globals",
        lambda: marker,
    )

    assert gs427._active_recorder_globals() is marker


def test_gs427_mutable_provider_health_seam_survives(monkeypatch):
    monkeypatch.setattr(
        gs427,
        "_provider_health",
        lambda provider: {
            "provider": provider,
            "patched": True,
        },
    )
    marker = object()

    assert gs427._provider_health(marker) == {
        "provider": marker,
        "patched": True,
    }


def test_phase42_install_tolerates_stale_replay_generation(monkeypatch):
    monkeypatch.setattr(
        gs427,
        "_replay",
        lambda: SimpleNamespace(),
    )

    assert gs427.install() is None


def test_phase42_replay_authority_owns_runtime_hard_bind():
    authority = (
        ROOT / "mide/authorities/replay_validation.py"
    ).read_text(encoding="utf-8")
    facade = (
        ROOT / "mide/gs427_flight_recorder_latency_hard_bind.py"
    ).read_text(encoding="utf-8")

    assert "def recorder_runtime_walk_functions(" in authority
    assert "def active_recorder_globals(" in authority
    assert "def recorder_active_provider(" in authority
    assert "def recorder_runtime_identity(" in authority
    assert "def install_recorder_runtime_hard_bind(" in authority

    assert "def _replay(" in facade
    assert "for cell in getattr(current" not in facade
    assert "@wraps(current)" not in facade


def test_phase42_scope_remains_observational_only():
    source = (
        ROOT / "mide/gs427_flight_recorder_latency_hard_bind.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        ".ensure_stream(",
        "provider.ensure_stream(",
        "qualified_for_watch =",
        "qualified_for_entry =",
        "qualified_for_alert =",
        "candidate_status =",
        "participation_score =",
        "expansion_score =",
        "vwap_value =",
        "place_order(",
        "play_alert(",
    )
    assert not any(token in source for token in forbidden)
    assert '"network_subscription_started_here": False' in source
    assert '"genuine_webull_tick_only": True' in source
