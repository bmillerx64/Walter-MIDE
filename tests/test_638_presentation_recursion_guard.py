from __future__ import annotations

from pathlib import Path

import pytest

from mide import ui
from mide.authorities import presentation_audio


def test_gs638_retained_renderer_cycle_falls_through_to_raw_base(monkeypatch):
    calls = []

    def raw_base(records):
        calls.append(("base", [record.get("symbol") for record in records]))
        return "rendered"

    def retained_cycle(records):
        calls.append(("retained", [record.get("symbol") for record in records]))
        return presentation_audio.render_walter_mission_control(records)

    monkeypatch.setattr(
        ui,
        "_walter_base_render_walter_mission_control",
        raw_base,
        raising=False,
    )
    monkeypatch.setattr(ui, "render_walter_mission_control", retained_cycle)

    result = presentation_audio.render_walter_mission_control(
        [{"symbol": "ABC"}]
    )

    assert result == "rendered"
    assert calls == [
        ("retained", ["ABC"]),
        ("base", ["ABC"]),
    ]


def test_gs638_facade_guard_resets_after_render_exception(monkeypatch):
    def exploding(_records):
        raise ValueError("render failed")

    monkeypatch.setattr(ui, "render_walter_mission_control", exploding)
    with pytest.raises(ValueError, match="render failed"):
        presentation_audio.render_walter_mission_control([])

    monkeypatch.setattr(
        ui,
        "render_walter_mission_control",
        lambda _records: "recovered",
    )
    assert presentation_audio.render_walter_mission_control([]) == "recovered"


def test_gs638_ui_exposes_stable_raw_renderer_anchor():
    source = Path("mide/ui.py").read_text(encoding="utf-8")
    assert (
        "_walter_base_render_walter_mission_control = "
        "render_walter_mission_control"
    ) in source


def test_gs638_scope_lock_is_presentation_only():
    authority = Path(
        "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")
    start = authority.index("_MISSION_CONTROL_FACADE_DEPTH")
    end = authority.index("def scanner_v2_dashboard_counts", start)
    block = authority[start:end]

    assert "_walter_base_render_walter_mission_control" in block
    assert "_MISSION_CONTROL_FACADE_DEPTH.reset(token)" in block
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "participation_score =",
        "expansion_score =",
        "request_scan(",
        "place_order(",
        "submit_order(",
        "execute_order(",
    )
    assert not any(token in block for token in forbidden)
