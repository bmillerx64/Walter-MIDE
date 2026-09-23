"""Phase 17 ownership contract for native market-awareness evidence."""

from pathlib import Path

from mide import gs334_market_event_lane as gs334
from mide import gs340_high_liquidity_trend_watch as gs340
from mide import gs377_strategy_leader_awareness as gs377
from mide.authorities import market_evidence, presentation_audio


def test_gs334_and_gs340_use_market_evidence_owner():
    assert gs334.market_event_rows is market_evidence.market_event_rows
    assert gs340.high_liquidity_trend_rows is market_evidence.high_liquidity_trend_rows
    assert gs334.EXTREME_MOVER_PCT == market_evidence.EXTREME_MOVER_PCT == 75.0
    assert (
        gs340.LIQUIDITY_TREND_MIN_GAIN_PCT
        == market_evidence.LIQUIDITY_TREND_MIN_GAIN_PCT
        == 30.0
    )
    assert (
        gs340.LIQUIDITY_TREND_MIN_VOLUME
        == market_evidence.LIQUIDITY_TREND_MIN_VOLUME
        == 50_000_000.0
    )


def test_gs377_strategy_leader_truth_uses_market_evidence_owner():
    assert gs377.strategy_leader_rows is market_evidence.strategy_leader_rows
    assert (
        gs377.merge_strategy_leader_events
        is market_evidence.merge_strategy_leader_events
    )
    assert (
        gs377.STRATEGY_LEADER_MIN_GAIN_PCT
        == market_evidence.STRATEGY_LEADER_MIN_GAIN_PCT
        == 15.0
    )
    assert (
        gs377.STRATEGY_LEADER_PRICE_CEILING
        == market_evidence.STRATEGY_LEADER_PRICE_CEILING
        == 5.0
    )


def test_gs334_display_helpers_use_presentation_owner():
    assert gs334.visible_market_events is presentation_audio.visible_market_events
    assert gs334.market_event_markup is presentation_audio.market_event_markup


def test_gs334_install_preserves_evidence_then_presentation_order(monkeypatch):
    calls = []
    monkeypatch.setattr(
        market_evidence,
        "install_market_event_capture",
        lambda: calls.append("evidence"),
    )
    monkeypatch.setattr(
        presentation_audio,
        "install_market_event_presentation",
        lambda: calls.append("presentation"),
    )

    gs334.install()
    assert calls == ["evidence", "presentation"]


def test_gs340_activation_does_not_replace_market_event_callable(monkeypatch):
    current = market_evidence.market_event_rows
    monkeypatch.setattr(
        market_evidence,
        "_market_event_liquidity_stage_active",
        False,
    )

    gs340.install()

    assert market_evidence.market_event_rows is current
    assert market_evidence._market_event_liquidity_stage_active is True
    assert getattr(
        market_evidence.market_event_rows,
        "_gs340_high_liquidity_trend_watch",
        False,
    )


def test_numbered_modules_are_compatibility_surfaces():
    gs334_source = Path("mide/gs334_market_event_lane.py").read_text(encoding="utf-8")
    gs340_source = Path("mide/gs340_high_liquidity_trend_watch.py").read_text(
        encoding="utf-8"
    )
    gs377_source = Path("mide/gs377_strategy_leader_awareness.py").read_text(
        encoding="utf-8"
    )
    market = Path("mide/authorities/market_evidence.py").read_text(encoding="utf-8")
    presentation = Path("mide/authorities/presentation_audio.py").read_text(
        encoding="utf-8"
    )

    assert "Compatibility facade" in gs334_source
    assert "Compatibility facade" in gs340_source
    assert "Compatibility facade" in gs377_source
    assert "def base_market_event_rows(" in market
    assert "def high_liquidity_trend_rows(" in market
    assert "def strategy_leader_rows(" in market
    assert "def install_market_event_capture(" in market
    assert "def market_event_markup(" in presentation
    assert "def install_market_event_presentation(" in presentation
