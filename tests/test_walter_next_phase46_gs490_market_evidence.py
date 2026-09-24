"""Phase 46: GS490 TICK initiation lifecycle belongs to Market Evidence."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs490_webull_stream_window_guard as gs490
from mide.authorities import market_evidence


ROOT = Path(__file__).resolve().parents[1]


def test_gs490_facade_delegates_window_truth(monkeypatch):
    monkeypatch.setattr(
        market_evidence,
        "webull_tick_stream_window_open",
        lambda value=None: True,
    )
    assert gs490.stream_window_open() is True


def test_gs490_install_for_provider_remains_mutable_seam(monkeypatch):
    marker = object()
    monkeypatch.setattr(
        gs490,
        "install_for_provider",
        lambda provider: provider is marker,
    )
    assert gs490.install_for_provider(marker) is True


def test_phase46_stale_market_generation_is_nonfatal(monkeypatch):
    monkeypatch.setattr(
        gs490,
        "_market",
        lambda: SimpleNamespace(),
    )
    assert gs490.install_for_provider(object()) is False


def test_phase46_market_evidence_owns_stream_window_lifecycle():
    authority = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")
    facade = (
        ROOT / "mide/gs490_webull_stream_window_guard.py"
    ).read_text(encoding="utf-8")

    assert "def webull_tick_stream_window_open(" in authority
    assert "def ensure_stream_in_window(" in authority
    assert "def install_stream_window_for_provider(" in authority

    assert "def _market(" in facade
    assert "@wraps(current)" not in facade
    assert "def guarded(" not in facade


def test_phase46_scope_remains_stream_initiation_lifecycle_only():
    source = (
        ROOT / "mide/gs490_webull_stream_window_guard.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "opportunity_score =",
        "conviction_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "place_order(",
        "submit_order(",
        "execute_order(",
    )
    assert not any(token in source for token in forbidden)
    assert "STREAM_START_ET = time(4, 0)" in source
    assert "STREAM_END_ET = time(20, 0)" in source
    assert "rest_snapshot_history_unchanged" in source
    assert '"trading_authority_changed": False' in source
