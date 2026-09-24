"""Phase 63: GS455 literal line-cross enrichment belongs to Market Evidence."""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

from mide import gs455_early_ignition_3m_confirmation as gs455
from mide.authorities import market_evidence


ROOT = Path(__file__).resolve().parents[1]


def test_phase63_current_facade_delegates_finite_truth():
    assert gs455._finite(1.25) == market_evidence.maturation_finite(1.25)
    assert gs455._finite(np.nan) is None


def test_phase63_stale_market_evidence_line_cross_fails_closed(monkeypatch):
    monkeypatch.setattr(
        gs455,
        "_market_evidence",
        lambda: SimpleNamespace(),
    )

    event = gs455._line_cross_event(
        None,
        None,
        None,
        None,
        "3m",
        latest_source_time=None,
    )
    assert event["crossed"] is False
    assert event["current_confirmed"] is False
    assert gs455._confirmation_details_with_line_cross(None, None) == (0, {})
    assert gs455._install_existing_maturation_source() is None


def test_phase63_line_cross_normalizes_nan_in_authority():
    index = pd.date_range(
        "2026-09-15 10:00",
        periods=2,
        freq="1min",
        tz="America/New_York",
    )
    frame = pd.DataFrame(
        {
            "close": [1.0, 1.0],
            "volume": [1000, 1000],
        },
        index=index,
    )
    vwap = pd.Series([1.0, 1.0], index=index)
    st_line = pd.Series([np.nan, np.nan], index=index)
    trend = pd.Series([False, False], index=index)

    event = gs455._line_cross_event(
        frame,
        vwap,
        st_line,
        trend,
        "10m",
        latest_source_time=index[-1],
    )
    assert event["latest_supertrend_value"] is None
    assert event["latest_vwap_value"] == 1.0
    assert event["crossed"] is False


def test_phase63_implementation_lives_in_market_evidence():
    legacy = (
        ROOT / "mide/gs455_early_ignition_3m_confirmation.py"
    ).read_text(encoding="utf-8")
    authority = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")

    for name in (
        "maturation_finite",
        "maturation_line_cross_event",
        "maturation_confirmation_details_with_line_cross",
        "maturation_timeframe_event_with_line_cross",
        "install_maturation_line_cross_enrichment",
    ):
        assert f"def {name}(" in authority

    start = legacy.index("def _line_cross_event(")
    end = legacy.index("def _confirmation_details_with_line_cross(", start)
    legacy_line_cross = legacy[start:end]
    assert "line_delta = st_line - vwap" not in legacy_line_cross
    assert "maturation_line_cross_event" in legacy_line_cross


def test_phase63_existing_callback_identity_and_markers_are_preserved(monkeypatch):
    from mide import gs378_live_vwap_st_crossover as gs378
    from mide import gs421_multitimeframe_convergence_recorder as gs421
    from mide import gs423_convergence_handoff_efficiency as gs423

    monkeypatch.setattr(gs423, "install", lambda: None)
    monkeypatch.setattr(
        gs378,
        "_confirmation_details",
        lambda day, primary: (0, {}),
    )
    monkeypatch.setattr(
        gs421,
        "_timeframe_event",
        lambda day, primary, label: {},
    )

    gs455._install_existing_maturation_source()

    assert gs378._confirmation_details is gs455._confirmation_details_with_line_cross
    assert gs421._timeframe_event is gs455._timeframe_event_with_line_cross
    assert getattr(gs378._confirmation_details, "_gs455_line_cross", False)
    assert getattr(gs421._timeframe_event, "_gs455_line_cross", False)


def test_phase63_scope_is_zero_extra_request_market_evidence():
    authority = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")
    start = authority.index("# GS455 literal ST/VWAP line-cross enrichment")
    end = authority.index("# GS460/GS461 ST compression", start)
    block = authority[start:end]

    forbidden = (
        "client.bars(",
        "provider.bars(",
        ".history(",
        "qualified_for_entry =",
        "qualified_for_alert =",
        "candidate_status =",
        "place_order(",
        "submit_order(",
        "play_alert(",
    )
    assert not any(token in block for token in forbidden)
