"""Phase 39: GS473 operator-attention audio belongs to Presentation + Audio."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs473_operator_attention_audio as gs473
from mide.authorities import presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def test_gs473_facade_delegates_candidate(monkeypatch):
    monkeypatch.setattr(
        presentation_audio,
        "operator_attention_candidate",
        lambda record: {
            "active": True,
            "symbol": record["symbol"],
        },
    )

    assert gs473.operator_attention_candidate(
        {"symbol": "LESL"}
    ) == {
        "active": True,
        "symbol": "LESL",
    }


def test_gs473_gate_helper_remains_mutable_runtime_seam(monkeypatch):
    monkeypatch.setattr(
        gs473,
        "_gate_passed",
        lambda record, name: name == "structure_gate",
    )

    assert gs473._gate_passed({}, "structure_gate") is True
    assert gs473._gate_passed({}, "participation_gate") is False


def test_phase39_install_tolerates_stale_presentation_generation(monkeypatch):
    monkeypatch.setattr(
        gs473,
        "_presentation",
        lambda: SimpleNamespace(),
    )

    assert gs473.install() is None


def test_phase39_authority_ownership_and_facade_shape():
    authority = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")
    facade = (
        ROOT / "mide/gs473_operator_attention_audio.py"
    ).read_text(encoding="utf-8")

    assert "def operator_attention_candidate(" in authority
    assert "def operator_attention_audio_phrase(" in authority
    assert "def install_operator_attention_audio(" in authority
    assert "gs473._gate_passed(" in authority

    assert "def _presentation(" in facade
    assert "def _cascade(" not in facade
    assert "def _supportive(" not in facade
    assert "from functools import wraps" not in facade


def test_phase39_scope_remains_audio_only():
    source = (
        ROOT / "mide/gs473_operator_attention_audio.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_watch =",
        "qualified_for_entry =",
        "qualified_for_alert =",
        "candidate_status =",
        "participation_score =",
        "expansion_score =",
        "vwap_distance_pct =",
        "place_order(",
        "ensure_stream(",
    )
    assert not any(token in source for token in forbidden)
    assert '"entry_authority_changed": False' in source
    assert '"alert_authority_changed": False' in source
