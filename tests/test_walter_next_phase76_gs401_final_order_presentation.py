"""Phase 76: GS401 final Opportunity ordering belongs to Presentation + Audio."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs369_escalation_priority_order as gs369
from mide import gs401_final_opportunity_order as gs401
from mide import ui
from mide.authorities import presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def test_phase76_authority_sorts_after_actionable_enrichment(monkeypatch):
    enriched = [
        {"symbol": "B"},
        {"symbol": "A"},
    ]
    monkeypatch.setattr(
        ui,
        "actionable_candidate_records",
        lambda _records: list(enriched),
    )
    monkeypatch.setattr(
        gs369,
        "ordered_escalation_records",
        lambda rows: sorted(
            list(rows),
            key=lambda record: record["symbol"],
        ),
    )

    visible = presentation_audio.final_visible_opportunity_records(
        [{"symbol": "IGNORED"}]
    )
    assert [record["symbol"] for record in visible] == ["A", "B"]


def test_phase76_legacy_final_visible_name_delegates_lazily(monkeypatch):
    sentinel = [{"symbol": "AUTH"}]
    monkeypatch.setattr(
        presentation_audio,
        "final_visible_opportunity_records",
        lambda _records: list(sentinel),
    )
    assert gs401.final_visible_records([]) == sentinel


def test_phase76_installer_preserves_gs401_lineage(monkeypatch):
    def renderer(records):
        return list(records)

    monkeypatch.setattr(
        ui,
        "render_escalation_engine",
        renderer,
    )
    presentation_audio.install_final_opportunity_order()
    installed = ui.render_escalation_engine

    assert installed is not renderer
    assert getattr(
        installed,
        "_gs401_final_opportunity_order",
        False,
    ) is True
    assert getattr(
        installed,
        "_gs401_original",
        None,
    ) is renderer

    presentation_audio.install_final_opportunity_order()
    assert ui.render_escalation_engine is installed


def test_phase76_authority_resolves_late_installed_sorter(monkeypatch):
    rendered = []

    def actionable(rows):
        return list(rows)

    def renderer(records):
        nested = ui.actionable_candidate_records(records)
        rendered.extend(record["symbol"] for record in nested)

    monkeypatch.setattr(
        ui,
        "actionable_candidate_records",
        actionable,
    )
    monkeypatch.setattr(
        ui,
        "render_escalation_engine",
        renderer,
    )
    monkeypatch.setattr(
        gs369,
        "ordered_escalation_records",
        lambda rows: list(rows),
    )

    presentation_audio.install_final_opportunity_order()

    monkeypatch.setattr(
        gs369,
        "ordered_escalation_records",
        lambda rows: sorted(
            list(rows),
            key=lambda record: record["symbol"] == "READY",
            reverse=True,
        ),
    )
    ui.render_escalation_engine(
        [
            {"symbol": "CHASE"},
            {"symbol": "READY"},
        ]
    )
    assert rendered == ["READY", "CHASE"]


def test_phase76_stale_presentation_generation_preserves_local_fallback(monkeypatch):
    def renderer(records):
        return list(records)

    monkeypatch.setattr(
        gs401,
        "_presentation_audio",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        ui,
        "render_escalation_engine",
        renderer,
    )

    gs401.install()
    installed = ui.render_escalation_engine
    assert installed is not renderer
    assert getattr(
        installed,
        "_gs401_final_opportunity_order",
        False,
    ) is True


def test_phase76_ordering_meaning_lives_in_presentation_audio():
    legacy = (
        ROOT / "mide/gs401_final_opportunity_order.py"
    ).read_text(encoding="utf-8")
    authority = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")

    assert "def final_visible_opportunity_records(" in authority
    assert "def install_final_opportunity_order(" in authority
    assert '"final_visible_opportunity_records"' in legacy
    assert '"install_final_opportunity_order"' in legacy


def test_phase76_scope_is_presentation_only():
    source = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")
    start = source.index("# GS401 final Opportunity render ordering")
    end = source.index("# GS414/GS436 final enriched Opportunity render boundary", start)
    block = source[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "place_order(",
        "submit_order(",
        "request_scan(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in block for token in forbidden)
