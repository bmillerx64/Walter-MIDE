"""Phase 80: GS404 reset/retest visible awareness belongs to Presentation + Audio."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs404_reset_retest_look_now as gs404
from mide.authorities import presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def _eligible_record(symbol="ZTG"):
    return {
        "symbol": symbol,
        "qualified_for_watch": False,
        "qualified_for_entry": False,
        "qualified_for_alert": False,
    }


def test_phase80_authority_tags_visible_eligible_record_once(monkeypatch):
    monkeypatch.setattr(
        gs404,
        "reset_retest_eligible",
        lambda _record: True,
    )
    source = _eligible_record()
    result = presentation_audio.augment_reset_retest_visible_records(
        [source],
        [source],
    )
    assert len(result) == 1
    assert result[0][gs404.RESET_RETEST_KEY] is True
    assert result[0] is not source


def test_phase80_authority_injects_awareness_only_copy_when_not_actionable(monkeypatch):
    monkeypatch.setattr(
        gs404,
        "reset_retest_eligible",
        lambda _record: True,
    )
    source = _eligible_record()
    result = presentation_audio.augment_reset_retest_visible_records(
        [source],
        [],
    )
    assert len(result) == 1
    row = result[0]
    assert row[gs404.RESET_RETEST_KEY] is True
    assert row["operator_awareness_only"] is True
    assert row["qualified_for_watch"] is False
    assert row["qualified_for_entry"] is False
    assert row["qualified_for_alert"] is False


def test_phase80_legacy_augment_name_delegates_lazily(monkeypatch):
    sentinel = [{"symbol": "AUTH"}]
    monkeypatch.setattr(
        presentation_audio,
        "augment_reset_retest_visible_records",
        lambda _records, _visible: list(sentinel),
    )
    assert gs404.augment_reset_retest_records([], []) == sentinel


def test_phase80_stale_presentation_generation_preserves_local_fallback(monkeypatch):
    monkeypatch.setattr(
        gs404,
        "_presentation_audio",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        gs404,
        "reset_retest_eligible",
        lambda _record: True,
    )
    source = _eligible_record()
    result = gs404.augment_reset_retest_records(
        [source],
        [],
    )
    assert result[0][gs404.RESET_RETEST_KEY] is True
    assert result[0]["operator_awareness_only"] is True


def test_phase80_state_and_runtime_binding_remain_for_final_gs404_slice():
    legacy = (
        ROOT / "mide/gs404_reset_retest_look_now.py"
    ).read_text(encoding="utf-8")
    assert "def reset_retest_opportunity_state(" in legacy
    assert "def install(" in legacy
    assert "_gs404_reset_retest" in legacy


def test_phase80_awareness_meaning_lives_in_presentation_audio():
    legacy = (
        ROOT / "mide/gs404_reset_retest_look_now.py"
    ).read_text(encoding="utf-8")
    authority = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")

    assert "def reset_retest_awareness_copy(" in authority
    assert "def augment_reset_retest_visible_records(" in authority
    assert '"augment_reset_retest_visible_records"' in legacy


def test_phase80_scope_is_presentation_only():
    source = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")
    start = source.index("# GS404 reset/retest visible-record awareness")
    end = source.index("# GS401 final Opportunity render ordering", start)
    block = source[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "opportunity_state =",
        "place_order(",
        "submit_order(",
        "request_scan(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in block for token in forbidden)
