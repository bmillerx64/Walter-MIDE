"""Phase 28: GS416 Validity suffix handling belongs to Entry Authority."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs416_validity_symbol_suffix as gs416
from mide.authorities import entry_authority


ROOT = Path(__file__).resolve().parents[1]


def test_gs416_security_shape_delegates_to_entry_authority():
    records = (
        ({"symbol": "SNYR", "asset_status": "active"}, True),
        ({"symbol": "ATER", "asset_status": "active"}, True),
        ({"symbol": "ABC-W", "asset_status": "active"}, False),
        ({"symbol": "ABC.R", "asset_status": "active"}, False),
        ({"symbol": "ABCU", "asset_type": "unit", "asset_status": "active"}, False),
    )
    for record, expected in records:
        assert gs416.supported_security(record, include_etfs=False) is expected
        assert (
            entry_authority.supported_security(record, include_etfs=False)
            is expected
        )


def test_gs416_warm_deploy_install_tolerates_older_entry_authority(monkeypatch):
    stale = SimpleNamespace()
    monkeypatch.setattr(gs416, "_entry", lambda: stale)

    assert gs416.install() is None


def test_gs416_source_is_lazy_facade_not_duplicate_validity_implementation():
    source = (ROOT / "mide/gs416_validity_symbol_suffix.py").read_text(
        encoding="utf-8"
    )

    assert "def _entry(" in source
    assert "install_validity_symbol_suffix" in source
    assert "WalterArchitectureV1" not in source
    assert "Decision(" not in source
    assert "_EXPLICIT_DERIVATIVE_SUFFIX" not in source
    assert "from mide.authorities import entry_authority as" not in source


def test_phase28_scope_preserves_validity_gate_only():
    source = (ROOT / "mide/gs416_validity_symbol_suffix.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "participation_score =",
        "expansion_score =",
        "opportunity_score =",
        "candidate_status =",
        "request_scan(",
        "place_order(",
        "submit_order(",
        "requests.get(",
        "requests.post(",
    )
    assert not any(token in source for token in forbidden)
