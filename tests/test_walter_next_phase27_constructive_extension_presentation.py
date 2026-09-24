"""Phase 27: GS453 constructive-extension semantics belong to Presentation + Audio."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs453_constructive_extension_developing as gs453
from mide.authorities import presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def _record():
    return {
        "symbol": "VSME",
        "vwap_relation": "above",
        "vwap_distance_pct": 2.4,
        "alignment_score": 2,
        "timeframe_alignment": {
            "30s": {"aligned": True},
            "1m": {"aligned": True},
            "3m": {"aligned": False},
        },
        "price_change_10m_pct": 2.8,
        "participation_score": 36.0,
        "volume_acceleration": 0.71,
        "dollar_flow_acceleration": 0.84,
    }


def test_gs453_helpers_delegate_to_presentation_audio():
    evidence = gs453.constructive_extension_evidence(_record())
    authoritative = presentation_audio.constructive_extension_evidence(_record())

    assert evidence == authoritative


def test_gs453_warm_deploy_install_tolerates_older_authority_generation(monkeypatch):
    stale = SimpleNamespace()
    monkeypatch.setattr(gs453, "_presentation", lambda: stale)

    # Critical deployment-safety contract: import/install must not crash merely
    # because a warm Streamlit process retained the prior authority generation.
    assert gs453.install() is None


def test_gs453_source_is_lazy_facade_not_duplicate_implementation():
    source = (ROOT / "mide/gs453_constructive_extension_developing.py").read_text(
        encoding="utf-8"
    )

    assert "def _presentation(" in source
    assert "install_constructive_extension_presentation" in source
    assert "def constructive_extension_evidence(record: dict) -> dict:" in source
    assert "def _state_with_constructive_extension(original, record: dict) -> dict:" in source
    assert "timeframe_alignment" not in source
    assert "view[\"state\"]" not in source


def test_phase27_scope_remains_presentation_only():
    source = (ROOT / "mide/gs453_constructive_extension_developing.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "participation_score =",
        "expansion_score =",
        "alignment_score =",
        "request_scan(",
        "place_order(",
        "submit_order(",
        "client.bars(",
        "client.snapshots(",
        "requests.get(",
        "requests.post(",
    )
    assert not any(token in source for token in forbidden)
