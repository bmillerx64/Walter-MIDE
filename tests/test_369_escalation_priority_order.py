from mide import ui
from mide.gs369_escalation_priority_order import install, ordered_escalation_records


def _record(symbol: str, state: str, score: int) -> dict:
    record = {
        "symbol": symbol,
        "qualified_for_ranking": True,
        "vwap_relation": "above",
        "vwap_distance_pct": 1.0,
        "supertrend_bullish": False,
        "participation_surge_score": 20,
        "expansion_quality": 20,
        "volume_acceleration": 0.5,
        "_test_attention": score,
    }
    if state == "WATCH FOR ENTRY":
        record.update(
            supertrend_bullish=True,
            participation_surge_score=80,
            expansion_quality=70,
        )
    elif state == "LOOK NOW":
        record["headline"] = "fresh attention catalyst"
    elif state == "DEVELOPING":
        record.update(supertrend_bullish=True, volume_acceleration=1.4)
    elif state == "CHASE / WAIT":
        record.update(supertrend_bullish=True, vwap_distance_pct=8.0)
    return record


def test_opportunity_state_cards_follow_existing_state_priority(monkeypatch):
    monkeypatch.setattr(ui, "hot_list_priority_score", lambda record: record["_test_attention"])
    records = [
        _record("CHASE", "CHASE / WAIT", 99),
        _record("DEV", "DEVELOPING", 80),
        _record("LOOK", "LOOK NOW", 40),
        _record("READY", "WATCH FOR ENTRY", 20),
    ]

    ordered = ordered_escalation_records(records)
    assert [record["symbol"] for record in ordered] == ["READY", "LOOK", "DEV", "CHASE"]


def test_install_sorts_before_existing_escalation_renderer(monkeypatch):
    seen = {}

    def original(records):
        seen["symbols"] = [record["symbol"] for record in records]

    monkeypatch.setattr(ui, "hot_list_priority_score", lambda record: record["_test_attention"])
    monkeypatch.setattr(ui, "render_escalation_engine", original)
    install()

    ui.render_escalation_engine(
        [
            _record("CHASE", "CHASE / WAIT", 99),
            _record("LOOK", "LOOK NOW", 10),
            _record("DEV", "DEVELOPING", 90),
        ]
    )

    assert seen["symbols"] == ["LOOK", "DEV", "CHASE"]
    assert getattr(ui.render_escalation_engine, "_gs369_escalation_priority_order", False)
