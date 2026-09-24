"""Phase 58: GS527 presentation-only attention lives in Presentation + Audio."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs527_explosive_30s_surge_watch as gs527
from mide.authorities import presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def test_phase58_calibration_and_owner_seams_remain_historical():
    assert gs527.FRESH_BURST_SECONDS == 90.0
    assert gs527.MIN_VOLUME_ACCELERATION_30S == 3.0
    assert gs527.MIN_DOLLAR_FLOW_ACCELERATION_30S == 3.0
    assert gs527._PROVENANCE == "GS527_EXPLOSIVE_30S_SURGE"
    assert gs527._STATE_OWNER == "_walter_gs527_explosive_30s_surge_state_owner"
    assert gs527._ORDER_OWNER == "_walter_gs527_explosive_30s_surge_order_owner"
    assert gs527._AUDIO_OWNER == "_walter_gs527_explosive_30s_surge_audio_owner"


def test_phase58_facade_delegates_signal_to_presentation(monkeypatch):
    expected = {
        "active": True,
        "symbol": "TEST",
        "authority": "OPERATOR_ATTENTION_ONLY",
    }
    monkeypatch.setattr(
        presentation_audio,
        "explosive_30s_surge",
        lambda _record: expected,
    )
    assert gs527.explosive_30s_surge({}) is expected


def test_phase58_stale_presentation_generation_fails_closed(monkeypatch):
    monkeypatch.setattr(gs527, "_presentation", lambda: SimpleNamespace())

    event = gs527.explosive_30s_surge({"symbol": "LHSW"})
    assert event["active"] is False
    assert event["symbol"] == "LHSW"
    assert event["entry_authority_changed"] is False

    original = lambda record: {"state": record.get("state", "DEVELOPING")}
    assert gs527.state_with_explosive_30s(
        original,
        {"state": "DEVELOPING"},
    ) == {"state": "DEVELOPING"}

    rows = [{"symbol": "A"}, {"symbol": "B"}]
    assert gs527.ordered_explosive_30s_records(rows) == rows
    assert gs527.ordered_explosive_30s_records(
        rows,
        baseline_order=lambda current: list(reversed(current)),
    ) == list(reversed(rows))
    assert gs527.explosive_30s_audio_phrase(rows) == ""
    assert gs527.install() is None


def test_phase58_facade_is_lazy_and_authority_owns_implementation():
    facade = (
        ROOT / "mide/gs527_explosive_30s_surge_watch.py"
    ).read_text(encoding="utf-8")
    authority = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")

    assert "def _presentation(" in facade
    assert "from .authorities import presentation_audio as _presentation" not in facade

    for name in (
        "explosive_30s_surge",
        "state_with_explosive_30s",
        "ordered_explosive_30s_records",
        "explosive_30s_audio_phrase",
        "install_explosive_30s_state",
        "install_explosive_30s_order",
        "install_explosive_30s_audio",
        "install_explosive_30s_presentation",
    ):
        assert f"def {name}(" in authority

    assert 'thirty = gs462._timeframe_detail(record, "30s")' not in facade
    assert "semantic_chime_count" not in facade


def test_phase58_scope_remains_operator_attention_only():
    authority = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")
    start = authority.index("# GS527 explosive 30s operator-attention watch")
    end = authority.index("def _pe_number(", start)
    block = authority[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "participation_score =",
        "expansion_score =",
        "mission_rank =",
        "place_order(",
        "submit_order(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in block for token in forbidden)
    assert '"entry_authority_changed": False' in block
    assert '"qualification_authority_changed": False' in block
    assert '"readiness_authority_changed": False' in block
