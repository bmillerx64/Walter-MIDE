from mide import ui
from mide.gs363_operator_attention_hierarchy import (
    alert_chime_count,
    priority_queue_markup,
    sorted_operator_records,
)


def _record(symbol: str, state: str, score: int) -> dict:
    base = {
        "symbol": symbol,
        "qualified_for_ranking": True,
        "participation_surge_score": 20,
        "expansion_quality": 20,
        "volume_acceleration": 0.5,
        "supertrend_bullish": False,
        "vwap_relation": "above",
        "vwap_distance_pct": 1.0,
        "_test_attention": score,
    }
    if state == "WATCH FOR ENTRY":
        base.update(
            supertrend_bullish=True,
            participation_surge_score=80,
            expansion_quality=70,
        )
    elif state == "LOOK NOW":
        base["headline"] = "fresh attention catalyst"
    elif state == "DEVELOPING":
        base.update(supertrend_bullish=True, volume_acceleration=1.4)
    elif state == "CHASE / WAIT":
        base.update(supertrend_bullish=True, vwap_distance_pct=5.0)
    elif state == "HALTED":
        base["halted"] = True
    return base


def test_operator_list_is_sorted_by_state_then_attention(monkeypatch):
    monkeypatch.setattr(ui, "hot_list_priority_score", lambda record: record["_test_attention"])
    records = [
        _record("CHASE", "CHASE / WAIT", 99),
        _record("DEVLOW", "DEVELOPING", 40),
        _record("LOOK", "LOOK NOW", 50),
        _record("ENTRY", "WATCH FOR ENTRY", 10),
        _record("DEVHIGH", "DEVELOPING", 90),
        _record("HALT", "HALTED", 100),
    ]

    ordered = sorted_operator_records(records)

    assert [record["symbol"] for record in ordered] == [
        "ENTRY",
        "LOOK",
        "DEVHIGH",
        "DEVLOW",
        "CHASE",
        "HALT",
    ]


def test_priority_queue_restores_numeric_quick_glance(monkeypatch):
    monkeypatch.setattr(ui, "hot_list_priority_score", lambda record: record["_test_attention"])
    records = [
        _record("LOW", "DEVELOPING", 62),
        _record("HIGH", "LOOK NOW", 94),
    ]

    markup = priority_queue_markup(records)

    assert "OPERATOR PRIORITY · HIGH TO LOW" in markup
    assert markup.index("HIGH") < markup.index("LOW")
    assert "94<span>/100</span>" in markup
    assert "Attention is a display cue, not a trade authorization." in markup


def test_alert_chime_hierarchy_distinguishes_attention_states():
    assert alert_chime_count("VIOT. Developing.") == 1
    assert alert_chime_count("VIOT. Chase / Wait.") == 1
    assert alert_chime_count("VIOT. Look Now.") == 2
    assert alert_chime_count("VIOT. Watch for Entry.") == 3
    assert alert_chime_count("VIOT. Entry Ready.") == 3


def test_gs363_is_final_installed_operator_layer():
    assert getattr(ui.render_walter_mission_control, "_gs363_operator_attention", False)
    assert getattr(ui.play_alert, "_gs363_operator_attention", False)
