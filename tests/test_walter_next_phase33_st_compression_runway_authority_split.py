"""Phase 33: GS460/GS461 split across Market Evidence and Presentation + Audio."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs460_st_flip_compression_ignition as gs460
from mide import gs461_cascade_runway as gs461
from mide.authorities import market_evidence, presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def test_gs460_market_evidence_facade_is_lazy_and_delegating(monkeypatch):
    expected = {"active": True, "phase33": "market"}
    monkeypatch.setattr(
        market_evidence,
        "st_flip_compression",
        lambda record: {**expected, "symbol": record["symbol"]},
    )

    result = gs460.st_flip_compression({"symbol": "RETO"})

    assert result == {**expected, "symbol": "RETO"}


def test_gs460_presentation_facade_delegates_without_freezing_authority(monkeypatch):
    expected = {"state": "delegated"}
    monkeypatch.setattr(
        presentation_audio,
        "state_with_st_flip_compression",
        lambda original, record: {**expected, "symbol": record["symbol"]},
    )

    result = gs460._state_with_compression(
        lambda _record: {"state": "base"},
        {"symbol": "RETO"},
    )

    assert result == {**expected, "symbol": "RETO"}


def test_gs461_market_facade_preserves_local_indicator_monkeypatch_seam(monkeypatch):
    captured = {}

    def delegated(day, label, *, resample_fn=None, supertrend_fn=None):
        captured["day"] = day
        captured["label"] = label
        captured["resample_fn"] = resample_fn
        captured["supertrend_fn"] = supertrend_fn
        return {"available": True}

    fake_resample = lambda *_args, **_kwargs: None
    fake_supertrend = lambda *_args, **_kwargs: None

    monkeypatch.setattr(
        market_evidence,
        "cascade_runway_local_status",
        delegated,
    )
    monkeypatch.setattr(gs461, "resample_ohlcv", fake_resample)
    monkeypatch.setattr(gs461, "supertrend", fake_supertrend)

    result = gs461._local_status(SimpleNamespace(empty=False), "30m")

    assert result == {"available": True}
    assert captured["label"] == "30m"
    assert captured["resample_fn"] is fake_resample
    assert captured["supertrend_fn"] is fake_supertrend


def test_gs461_presentation_facade_delegates_runway_text(monkeypatch):
    monkeypatch.setattr(
        presentation_audio,
        "cascade_runway_text",
        lambda runway: f"runway:{runway['active']}",
    )

    assert gs461._runway_text({"active": True}) == "runway:True"


def test_phase33_install_tolerates_stale_authority_generations(monkeypatch):
    monkeypatch.setattr(gs460, "_presentation", lambda: SimpleNamespace())
    monkeypatch.setattr(gs461, "_market", lambda: SimpleNamespace())
    monkeypatch.setattr(gs461, "_presentation", lambda: SimpleNamespace())

    assert gs460.install() is None
    assert gs461.install() is None


def test_phase33_authority_ownership_is_explicit():
    market_source = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")
    presentation_source = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")

    assert "def st_flip_compression(" in market_source
    assert "def build_cascade_runway(" in market_source
    assert "def install_cascade_runway_evidence(" in market_source
    assert "def state_with_st_flip_compression(" in presentation_source
    assert "def cascade_runway_text(" in presentation_source
    assert "def install_cascade_runway_alerts(" in presentation_source


def test_phase33_facades_do_not_duplicate_moved_implementations():
    gs460_source = (
        ROOT / "mide/gs460_st_flip_compression_ignition.py"
    ).read_text(encoding="utf-8")
    gs461_source = (
        ROOT / "mide/gs461_cascade_runway.py"
    ).read_text(encoding="utf-8")

    assert "def _market(" in gs460_source
    assert "def _presentation(" in gs460_source
    assert "install_st_flip_compression_state" in gs460_source
    assert "median(" not in gs460_source
    assert "def calibrated(" not in gs460_source
    assert "escalation.escalation_alert_phrase =" not in gs460_source

    assert "def _market(" in gs461_source
    assert "def _presentation(" in gs461_source
    assert "install_cascade_runway_evidence" in gs461_source
    assert "def apply_with_runway(" not in gs461_source
    assert "@wraps" not in gs461_source
    assert "escalation.escalation_alert_phrase =" not in gs461_source


def test_phase33_scope_preserves_no_provider_or_trading_authority_changes():
    sources = [
        (
            ROOT / "mide/gs460_st_flip_compression_ignition.py"
        ).read_text(encoding="utf-8"),
        (
            ROOT / "mide/gs461_cascade_runway.py"
        ).read_text(encoding="utf-8"),
    ]
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "request_scan(",
        "client.bars(",
        ".get_bars(",
        ".history(",
        "place_order(",
        "submit_order(",
        "TRIGGER_",
        "PARTICIPATION_MIN_",
    )
    assert not any(
        token in source
        for source in sources
        for token in forbidden
    )
