"""Phase 34: GS462 pre-flip attention belongs to Presentation + Audio."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs459_price_trajectory_attention as gs459
from mide import gs462_preflip_ignition_watch as gs462
from mide.authorities import presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def _record(*, age=60.0, one_gap=1.5):
    price = 2.0
    return {
        "symbol": "TEST",
        "price": price,
        "supertrend_30s_bullish": True,
        "supertrend_30s_last_flip_age_seconds": age,
        "timeframe_alignment": {
            "30s": {
                "above_vwap": True,
                "supertrend_bullish": True,
                "supertrend_value": 1.90,
                "vwap_value": 1.94,
            }
        },
        "thirty_second_tripwire": {
            "latest_close": price,
            "last_flip_age_seconds": age,
        },
        "timeframes": {
            "1m": {
                "current_supertrend_bullish": False,
                "current_above_vwap": True,
                "current_close": price,
                "current_vwap": 1.95,
                "st_vwap_line_cross": {
                    "latest_supertrend_value": (
                        price * (1.0 + one_gap / 100.0)
                    ),
                    "latest_vwap_value": 1.95,
                },
            },
            "3m": {
                "current_supertrend_bullish": False,
                "current_above_vwap": True,
                "current_close": price,
                "current_vwap": 1.95,
                "st_vwap_line_cross": {
                    "latest_supertrend_value": 2.10,
                    "latest_vwap_value": 1.95,
                },
            },
            "5m": {},
            "10m": {},
        },
    }


def test_gs462_facade_delegates_to_presentation_authority(monkeypatch):
    monkeypatch.setattr(
        gs459,
        "_supporting_flow",
        lambda _record: True,
    )

    facade = gs462.preflip_ignition_watch(_record())
    authority = presentation_audio.preflip_ignition_watch(
        _record()
    )

    assert facade == authority
    assert facade["active"] is True
    assert facade["stage"] == "EARLY WATCH"


def test_phase34_preserves_dynamic_freshness_mutation_seam(monkeypatch):
    monkeypatch.setattr(
        gs459,
        "_supporting_flow",
        lambda _record: True,
    )
    original = gs462.RECENT_30S_FLIP_SECONDS
    try:
        gs462.RECENT_30S_FLIP_SECONDS = 30.0
        assert (
            gs462.preflip_ignition_watch(
                _record(age=60.0)
            )["active"]
            is False
        )
    finally:
        gs462.RECENT_30S_FLIP_SECONDS = original


def test_phase34_preserves_dynamic_near_st_calibration(monkeypatch):
    monkeypatch.setattr(
        gs459,
        "_supporting_flow",
        lambda _record: True,
    )
    original = gs462.NEAR_ST_LINE_PCT
    try:
        gs462.NEAR_ST_LINE_PCT = 1.0
        signal = gs462.preflip_ignition_watch(
            _record(one_gap=1.5)
        )
        assert signal["one_minute"]["near_supertrend"] is False
        assert signal["active"] is False
    finally:
        gs462.NEAR_ST_LINE_PCT = original


def test_phase34_install_tolerates_stale_authority_generation(monkeypatch):
    monkeypatch.setattr(
        gs462,
        "_presentation",
        lambda: SimpleNamespace(),
    )

    assert gs462.install() is None


def test_phase34_facade_is_lazy_and_does_not_duplicate_implementation():
    source = (
        ROOT / "mide/gs462_preflip_ignition_watch.py"
    ).read_text(encoding="utf-8")

    assert "def _presentation(" in source
    assert "install_preflip_state" in source
    assert "install_preflip_order" in source
    assert "NEAR_ST_LINE_PCT = 2.0" in source
    assert "PRE_FLIP_ATTENTION_BAND = 39" in source
    assert "def calibrated(" not in source
    assert "baseline.sort(" not in source
    assert "timeframe_alignment" not in source


def test_phase34_presentation_authority_owns_gs462_semantics():
    source = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")

    assert "def preflip_ignition_watch(" in source
    assert "def state_with_preflip(" in source
    assert "def ordered_preflip_records(" in source
    assert "def install_preflip_presentation(" in source


def test_phase34_scope_remains_attention_only():
    source = (
        ROOT / "mide/gs462_preflip_ignition_watch.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "request_scan(",
        ".get_bars(",
        ".history(",
        "place_order(",
        "submit_order(",
        "escalation_alert_phrase",
        "semantic_chime_count",
    )
    assert not any(token in source for token in forbidden)
