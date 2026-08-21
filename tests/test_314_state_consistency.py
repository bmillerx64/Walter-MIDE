from copy import deepcopy

from mide import ui
from mide.gs310_unified_opportunity_state import CHASE_WAIT, WATCH_FOR_ENTRY
from mide.gs314_state_consistency import (
    consistent_display_sections,
    presentation_contract,
)


def record(**overrides):
    value = {
        "symbol": "BRNX",
        "price": 3.71,
        "pct_change": 15.9,
        "volume": 672_736,
        "dollar_volume": 2_495_850.56,
        "attention_score": 29.9,
        "market_dominance_score": 29.5,
        "relative_strength_score": 3.25,
        "relative_strength_benchmark": "IWM",
        "participation_score": 45.6,
        "participation_surge_score": 0.0,
        "participation_tier": "ACTIVE",
        "expansion_quality": 58.0,
        "opportunity_score": 67.7,
        "opportunity_score_v2": 67.7,
        "conviction_score": 67.8,
        "candidate_status": "Entry Ready",
        "status": "ALERT",
        "qualified_for_watch": True,
        "vwap_relation": "above",
        "vwap_distance_pct": 3.6,
        "supertrend_bullish": True,
        "rvol_proxy": 2.7,
        "volume_acceleration": 2.7,
        "spread_pct": 0.5,
        "reasons": [],
    }
    value.update(overrides)
    return value


def test_scanner_entry_ready_cannot_override_chase_wait_presentation():
    item = record()

    contract = presentation_contract(item)

    assert contract["state"] == CHASE_WAIT
    assert contract["section"] == CHASE_WAIT
    assert contract["recommendation"]["label"] == "NO TRADE"


def test_fully_aligned_record_uses_watch_for_entry_and_get_ready():
    item = record(
        vwap_distance_pct=0.7,
        participation_surge_score=83,
        expansion_quality=72,
    )

    contract = presentation_contract(item)

    assert contract["state"] == WATCH_FOR_ENTRY
    assert contract["section"] == WATCH_FOR_ENTRY
    assert contract["recommendation"]["label"] == "GET READY"


def test_display_sections_follow_unified_state_not_scanner_candidate_status():
    extended = record(symbol="EXT", candidate_status="Entry Ready", vwap_distance_pct=3.6)
    aligned = record(
        symbol="READY",
        candidate_status="Watching",
        vwap_distance_pct=0.4,
        participation_surge_score=90,
        expansion_quality=70,
    )

    sections = consistent_display_sections([extended, aligned])

    assert [item["symbol"] for item in sections[WATCH_FOR_ENTRY]] == ["READY"]
    assert [item["symbol"] for item in sections[CHASE_WAIT]] == ["EXT"]


def test_installed_dashboard_section_titles_are_unified_states():
    extended = record(symbol="EXT", candidate_status="Entry Ready", vwap_distance_pct=3.6)

    sections = ui.scanner_v2_display_sections([extended])
    populated = [(title, rows) for title, rows, _expanded in sections if rows]

    assert len(populated) == 1
    assert populated[0][0] == CHASE_WAIT
    assert populated[0][1][0]["symbol"] == "EXT"


def test_card_uses_same_state_and_compatible_action(monkeypatch):
    rendered = []
    monkeypatch.setattr(ui.st, "markdown", lambda body, **_kwargs: rendered.append(body))

    ui.opportunity_card(record())

    markup = rendered[-1]
    assert CHASE_WAIT in markup
    assert "NO TRADE" in markup
    assert "Entry Ready" not in markup


def test_consistency_layer_does_not_mutate_scanner_record():
    item = record()
    before = deepcopy(item)

    presentation_contract(item)
    consistent_display_sections([item])

    assert item == before
