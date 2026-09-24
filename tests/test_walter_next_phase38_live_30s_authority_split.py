"""Phase 38: GS469/GS470 split across Market Evidence and Replay Validation."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs469_30s_stream_continuity as gs469
from mide import gs470_30s_activation_truth as gs470
from mide.authorities import market_evidence, replay_validation


ROOT = Path(__file__).resolve().parents[1]


def test_gs469_facade_delegates_market_continuity(monkeypatch):
    marker = object()
    monkeypatch.setattr(
        market_evidence,
        "reassert_active_30s_provider",
        lambda provider: provider is marker,
    )

    assert gs469.reassert_active_provider(marker) is True


def test_gs470_facade_delegates_activation(monkeypatch):
    monkeypatch.setattr(
        market_evidence,
        "activate_production_30s_evidence",
        lambda provider: {
            "authority": gs470.AUTHORITY,
            "provider": provider,
        },
    )

    marker = object()
    assert gs470.activate_production_30s(marker)["provider"] is marker


def test_gs470_safe_activate_remains_mutable_historical_seam(monkeypatch):
    marker = object()
    monkeypatch.setattr(
        gs470,
        "_safe_activate",
        lambda provider: {"provider": provider, "wrapped": True},
    )

    assert gs470._safe_activate(marker) == {
        "provider": marker,
        "wrapped": True,
    }


def test_phase38_installers_tolerate_stale_authority_generations(monkeypatch):
    monkeypatch.setattr(gs469, "_market", lambda: SimpleNamespace())
    monkeypatch.setattr(gs470, "_market", lambda: SimpleNamespace())
    monkeypatch.setattr(gs470, "_replay", lambda: SimpleNamespace())

    assert gs469.install() is None
    assert gs470.install() is None


def test_phase38_authority_ownership_is_explicit():
    market_source = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")
    replay_source = (
        ROOT / "mide/authorities/replay_validation.py"
    ).read_text(encoding="utf-8")

    assert "def ensure_live_30s_stream_continuity(" in market_source
    assert "def activate_production_30s_evidence(" in market_source
    assert "def production_30s_health(" in market_source
    assert "def install_30s_recorder_health(" in replay_source
    assert "def install_30s_hard_recorder_health(" in replay_source


def test_phase38_facades_do_not_duplicate_lifecycle_implementations():
    gs469_source = (
        ROOT / "mide/gs469_30s_stream_continuity.py"
    ).read_text(encoding="utf-8")
    gs470_source = (
        ROOT / "mide/gs470_30s_activation_truth.py"
    ).read_text(encoding="utf-8")

    assert "def _market(" in gs469_source
    assert "def _market(" in gs470_source
    assert "def _replay(" in gs470_source
    assert "def _restart_reason(" not in gs469_source
    assert "def _patch_retained_provider_event(" not in gs470_source
    assert "def persist_replayable_scan(" not in gs470_source


def test_phase38_scope_preserves_genuine_tick_only_no_trade_authority():
    sources = [
        (
            ROOT / "mide/gs469_30s_stream_continuity.py"
        ).read_text(encoding="utf-8"),
        (
            ROOT / "mide/gs470_30s_activation_truth.py"
        ).read_text(encoding="utf-8"),
    ]
    forbidden = (
        "provider.bars(",
        "client.bars(",
        "qualified_for_watch =",
        "qualified_for_entry =",
        "qualified_for_alert =",
        "candidate_status =",
        "participation_score =",
        "expansion_score =",
        "vwap_value =",
        "place_order(",
        "submit_order(",
        "play_alert(",
    )
    assert not any(
        token in source
        for source in sources
        for token in forbidden
    )
    assert '"synthetic_30s_bars": False' in sources[0]
    assert '"genuine_webull_tick_only": True' in sources[1]
