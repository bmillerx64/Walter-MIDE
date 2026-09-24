"""Phase 75: GS458 Flight Recorder fragment freshness belongs to Replay / Validation."""

from pathlib import Path
from types import SimpleNamespace

import streamlit as st

from mide import gs350_download_export_reliability as gs350
from mide import gs458_flight_recorder_fragment_freshness as gs458
from mide.authorities import replay_validation


ROOT = Path(__file__).resolve().parents[1]


def test_phase75_authority_preserves_gs458_markers(monkeypatch):
    def leaf(*args, **kwargs):
        return None

    monkeypatch.setattr(st, "download_button", leaf)
    gs350.install()

    replay_validation.install_flight_recorder_fragment_freshness()
    current = st.download_button

    assert getattr(
        current,
        "_gs458_flight_recorder_fragment_freshness",
        False,
    ) is True
    assert getattr(
        current,
        "_gs458_authority",
        None,
    ) == gs458.AUTHORITY
    assert getattr(
        current,
        "_gs458_trading_logic_changed",
        None,
    ) is False


def test_phase75_legacy_install_delegates_lazily(monkeypatch):
    calls = []
    monkeypatch.setattr(
        replay_validation,
        "install_flight_recorder_fragment_freshness",
        lambda: calls.append("authority"),
    )
    gs458.install()
    assert calls == ["authority"]


def test_phase75_stale_replay_generation_preserves_local_fallback(monkeypatch):
    def leaf(*args, **kwargs):
        return None

    monkeypatch.setattr(
        gs458,
        "_replay_validation",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(st, "download_button", leaf)
    gs350.install()

    gs458.install()
    current = st.download_button
    assert getattr(
        current,
        "_gs458_flight_recorder_fragment_freshness",
        False,
    ) is True
    assert getattr(
        current,
        "_gs458_authority",
        None,
    ) == gs458.AUTHORITY


def test_phase75_lifecycle_meaning_lives_in_replay_validation():
    legacy = (
        ROOT / "mide/gs458_flight_recorder_fragment_freshness.py"
    ).read_text(encoding="utf-8")
    authority = (
        ROOT / "mide/authorities/replay_validation.py"
    ).read_text(encoding="utf-8")

    assert "def install_flight_recorder_fragment_freshness(" in authority
    assert '"install_flight_recorder_fragment_freshness"' in legacy
    assert "_gs458_flight_recorder_fragment_freshness" in authority


def test_phase75_scope_is_export_lifecycle_only():
    source = (
        ROOT / "mide/authorities/replay_validation.py"
    ).read_text(encoding="utf-8")
    start = source.index("# GS458 Flight Recorder fragment freshness lifecycle")
    end = source.index("__all__ = [", start)
    block = source[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "request_scan(",
        "record_scan(",
        "participation_score =",
        "vwap_distance_pct =",
        "place_order(",
        "submit_order(",
    )
    assert not any(token in block for token in forbidden)
