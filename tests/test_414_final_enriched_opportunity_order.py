from pathlib import Path
import threading

import pytest

from mide import gs310_unified_opportunity_state as unified
from mide import ui
from mide.gs414_final_enriched_opportunity_order import (
    final_enriched_opportunity_records,
    install,
)


def _record(symbol: str, state: str) -> dict:
    return {
        "symbol": symbol,
        "forced_state": state,
        "qualified_for_ranking": True,
        "price": 1.0,
    }


def _force_state(monkeypatch):
    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda record: {"state": record["forced_state"]},
    )


def test_gs414_reorders_late_enriched_developing_ahead_of_chase(monkeypatch):
    _force_state(monkeypatch)
    enriched = [
        _record("AHMA", unified.CHASE_WAIT),
        _record("HPAI", unified.DEVELOPING),
        _record("VIOT", unified.DEVELOPING),
    ]

    visible = final_enriched_opportunity_records(
        [_record("AHMA", unified.CHASE_WAIT)],
        actionable_function=lambda _records: list(enriched),
    )

    assert [record["symbol"] for record in visible] == ["HPAI", "VIOT", "AHMA"]


def test_gs414_freezes_order_across_nested_actionable_calls(monkeypatch):
    _force_state(monkeypatch)
    enriched = [
        _record("CHASE", unified.CHASE_WAIT),
        _record("DEV", unified.DEVELOPING),
        _record("LOOK", unified.LOOK_NOW),
        _record("READY", unified.WATCH_FOR_ENTRY),
    ]
    monkeypatch.setattr(ui, "actionable_candidate_records", lambda _records: list(enriched))

    rendered = []

    def nested_renderer(records):
        # Reproduce GS310's internal actionable call. GS414 must make this nested
        # consumer observe the same final enriched/ordered snapshot.
        nested = ui.actionable_candidate_records(records)[:5]
        rendered.extend(record["symbol"] for record in nested)

    monkeypatch.setattr(ui, "render_escalation_engine", nested_renderer)
    install()
    ui.render_escalation_engine([_record("CHASE", unified.CHASE_WAIT)])

    assert rendered == ["READY", "LOOK", "DEV", "CHASE"]


def test_gs589_keeps_public_actionable_guard_stable_on_render_error(monkeypatch):
    _force_state(monkeypatch)
    original_actionable = lambda records: list(records)
    monkeypatch.setattr(ui, "actionable_candidate_records", original_actionable)

    def failing_renderer(_records):
        raise RuntimeError("render failed")

    monkeypatch.setattr(ui, "render_escalation_engine", failing_renderer)
    install()
    installed_actionable = ui.actionable_candidate_records

    with pytest.raises(RuntimeError, match="render failed"):
        ui.render_escalation_engine([_record("DEV", unified.DEVELOPING)])

    assert ui.actionable_candidate_records is installed_actionable
    assert ui.actionable_candidate_records([_record("A", unified.DEVELOPING)])[0]["symbol"] == "A"


def test_gs589_concurrent_renders_do_not_leak_frozen_records(monkeypatch):
    from mide.authorities import presentation_audio

    _force_state(monkeypatch)
    monkeypatch.setattr(ui, "actionable_candidate_records", lambda records: list(records))

    barrier = threading.Barrier(2)
    seen = {}
    seen_lock = threading.Lock()

    def nested_renderer(records):
        own = records[0]["symbol"]
        barrier.wait(timeout=5)
        nested = ui.actionable_candidate_records(records)
        with seen_lock:
            seen[own] = [record["symbol"] for record in nested]

    monkeypatch.setattr(ui, "render_escalation_engine", nested_renderer)
    presentation_audio.bind_final_enriched_opportunity_order("render_escalation_engine")

    errors = []

    def run(symbol):
        try:
            ui.render_escalation_engine([_record(symbol, unified.DEVELOPING)])
        except Exception as exc:
            errors.append(exc)

    first = threading.Thread(target=run, args=("ALPHA",))
    second = threading.Thread(target=run, args=("BRAVO",))
    first.start()
    second.start()
    first.join(timeout=10)
    second.join(timeout=10)

    assert not errors
    assert seen == {"ALPHA": ["ALPHA"], "BRAVO": ["BRAVO"]}


def test_gs414_installs_last_after_gs413_inflight_guard():
    source = Path("mide/gs392_operator_order_audio.py").read_text(encoding="utf-8")
    assert source.index("install_gs413_inflight()") < source.index("install_gs414()")


def test_gs589_scope_is_presentation_only_and_no_process_global_swap():
    source = Path("mide/gs414_final_enriched_opportunity_order.py").read_text(
        encoding="utf-8"
    )
    authority = Path("mide/authorities/presentation_audio.py").read_text(
        encoding="utf-8"
    )
    assert 'bind_final_order("render_escalation_engine")' in source
    assert 'bind_final_order("render_walter_mission_control", show_legend=True)' in source
    final_boundary = authority[authority.index("# GS414/GS436 final enriched Opportunity render boundary"):]
    assert "context.set(tuple(ordered))" in final_boundary
    assert "context.reset(token)" in final_boundary
    assert "ui.actionable_candidate_records = frozen_actionable" not in final_boundary
    assert "ui.actionable_candidate_records = public_actionable" not in final_boundary



def test_gs539_binds_actual_gs332_live_opportunity_path(monkeypatch):
    from mide import gs539_pe_strength_order as gs539

    enriched = [
        {
            "symbol": "AVAT",
            "participation_surge_score": 32,
            "expansion_quality": 63,
        },
        {
            "symbol": "EDVA",
            "participation_surge_score": 85,
            "expansion_quality": 62,
        },
    ]
    monkeypatch.setattr(ui, "actionable_candidate_records", lambda _records: list(enriched))
    monkeypatch.setattr(
        "mide.gs369_escalation_priority_order.ordered_escalation_records",
        lambda rows: gs539.ordered_pe_strength_records(rows),
    )

    rendered = []
    def live_gs332_path(records):
        nested = ui.actionable_candidate_records(records)[:5]
        rendered.extend(row["symbol"] for row in nested)

    monkeypatch.setattr(ui, "render_escalation_engine", lambda _records: None)
    monkeypatch.setattr(ui, "render_walter_mission_control", live_gs332_path)
    install()

    ui.render_walter_mission_control(enriched)
    assert rendered == ["EDVA", "AVAT"]
