"""Phase 43: GS487 cached-recorder binding belongs to Replay / Validation."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs487_cached_recorder_instance_bind as gs487
from mide.authorities import replay_validation


ROOT = Path(__file__).resolve().parents[1]


def test_gs487_facade_delegates_exact_recorder_lookup(monkeypatch):
    marker = {"persist_replayable_scan": lambda *_a, **_k: None}
    monkeypatch.setattr(
        replay_validation,
        "exact_cached_recorder_globals",
        lambda recorder: marker,
    )

    assert gs487._exact_recorder_globals(object()) is marker


def test_gs487_install_for_recorder_remains_mutable_historical_seam(monkeypatch):
    marker = object()
    monkeypatch.setattr(
        gs487,
        "install_for_recorder",
        lambda recorder: recorder is marker,
    )

    assert gs487.install_for_recorder(marker) is True


def test_phase43_stale_replay_generation_is_nonfatal(monkeypatch):
    monkeypatch.setattr(
        gs487,
        "_replay",
        lambda: SimpleNamespace(),
    )

    assert gs487.install_for_recorder(object()) is False


def test_phase43_replay_authority_owns_cached_recorder_implementation():
    authority = (
        ROOT / "mide/authorities/replay_validation.py"
    ).read_text(encoding="utf-8")
    facade = (
        ROOT / "mide/gs487_cached_recorder_instance_bind.py"
    ).read_text(encoding="utf-8")

    assert "def exact_cached_recorder_globals(" in authority
    assert "def cached_recorder_news_transport(" in authority
    assert "def cached_recorder_stream_transport(" in authority
    assert "def install_cached_recorder_instance_bind(" in authority

    assert "def _replay(" in facade
    assert "@wraps(current)" not in facade
    assert "for function in gs427._walk_functions" not in facade


def test_phase43_scope_remains_observational_only():
    source = (
        ROOT / "mide/gs487_cached_recorder_instance_bind.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "subscribe(",
        "ensure_stream(",
        "initialize_quotes(",
        "place_order(",
        "submit_order(",
        "execute_order(",
        "import requests",
        "import httpx",
    )
    assert not any(token in source for token in forbidden)
    assert 'truth["extra_provider_calls"] = 0' in source
    assert 'truth["network_repair_attempted_here"] = False' in source
