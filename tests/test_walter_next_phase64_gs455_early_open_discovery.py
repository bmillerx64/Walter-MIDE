"""Phase 64: GS455 bounded early-open admission belongs to Discovery + News."""

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from mide import gs455_early_ignition_3m_confirmation as gs455
from mide.authorities import discovery_news


ROOT = Path(__file__).resolve().parents[1]
EASTERN = ZoneInfo("America/New_York")


def test_phase64_historical_early_open_calibration_is_preserved():
    assert gs455.EARLY_OPEN_START.hour == 9
    assert gs455.EARLY_OPEN_START.minute == 30
    assert gs455.EARLY_OPEN_END.hour == 9
    assert gs455.EARLY_OPEN_END.minute == 45
    assert gs455.EARLY_OPEN_MIN_PCT_CHANGE == 2.0
    assert gs455.EARLY_OPEN_MIN_VOLUME == 15_000.0


def test_phase64_authority_respects_historical_clock_seam(monkeypatch):
    monkeypatch.setattr(
        gs455,
        "_market_now",
        lambda: datetime(
            2026,
            9,
            15,
            9,
            33,
            tzinfo=EASTERN,
        ),
    )
    assert gs455._inside_early_open_window() is True

    monkeypatch.setattr(
        gs455,
        "_market_now",
        lambda: datetime(
            2026,
            9,
            15,
            9,
            45,
            tzinfo=EASTERN,
        ),
    )
    assert gs455._inside_early_open_window() is False


def test_phase64_stale_discovery_generation_never_relaxes_prefilter(monkeypatch):
    monkeypatch.setattr(
        gs455,
        "_discovery_news",
        lambda: SimpleNamespace(),
    )

    called = {"count": 0}

    def original(symbol, snapshot, settings):
        called["count"] += 1
        return {
            "passed": False,
            "failed_rule": "Percent change and average volume below thresholds",
        }

    result = gs455._early_open_prefilter_decision(
        original,
        "TEST",
        {},
        object(),
    )
    assert called["count"] == 1
    assert result["passed"] is False
    assert gs455._install_prefilter() is None


def test_phase64_early_open_meaning_lives_in_discovery_news():
    legacy = (
        ROOT / "mide/gs455_early_ignition_3m_confirmation.py"
    ).read_text(encoding="utf-8")
    authority = (
        ROOT / "mide/authorities/discovery_news.py"
    ).read_text(encoding="utf-8")

    for name in (
        "early_open_market_now",
        "early_open_inside_window",
        "early_open_prefilter_decision",
        "install_early_open_ignition_admission",
    ):
        assert f"def {name}(" in authority

    start = legacy.index("def _early_open_prefilter_decision(")
    end = legacy.index("def _line_cross_event(", start)
    facade_block = legacy[start:end]
    assert "early_open_prefilter_decision" in facade_block
    assert 'decision["passed"] = True' not in facade_block


def test_phase64_prefilter_wrapper_marker_and_boundary_are_preserved(monkeypatch):
    from mide import discovery, flight_recorder

    def baseline(symbol, snapshot, settings):
        return {
            "passed": True,
            "symbol": symbol,
        }

    monkeypatch.setattr(
        flight_recorder,
        "prefilter_decision",
        baseline,
    )
    monkeypatch.setattr(
        discovery,
        "prefilter_decision",
        baseline,
        raising=False,
    )

    gs455._install_prefilter()

    assert getattr(
        flight_recorder.prefilter_decision,
        "_gs455_early_open_ignition",
        False,
    )
    assert (
        discovery.prefilter_decision
        is flight_recorder.prefilter_decision
    )


def test_phase64_scope_is_discovery_admission_only():
    source = (
        ROOT / "mide/authorities/discovery_news.py"
    ).read_text(encoding="utf-8")
    start = source.index("# GS455 bounded early-open ignition admission")
    end = source.index("# GS540 news-corroborated shadow RVOL discovery", start)
    block = source[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "candidate_status =",
        "mission_rank =",
        "place_order(",
        "submit_order(",
        "play_alert(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in block for token in forbidden)
