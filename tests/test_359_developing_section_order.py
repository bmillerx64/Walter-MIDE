from contextlib import contextmanager

from mide import ui
from mide import gs349_operator_first_layout as layout


def _record(symbol: str, state: str) -> dict:
    return {
        "symbol": symbol,
        "candidate_status": state,
        "opportunity_state": state,
        "price": 1.0,
        "pct_change": 10.0,
    }


def test_operator_first_split_moves_only_developing(monkeypatch):
    developing = _record("DEV", "DEVELOPING")
    chase = _record("CHASE", "CHASE / WAIT")
    monkeypatch.setattr(
        ui,
        "scanner_v2_display_sections",
        lambda records: [
            ("DEVELOPING", [developing], True),
            ("CHASE / WAIT", [chase], False),
        ],
    )

    moved, remaining = layout.operator_first_sections([developing, chase])

    assert moved == [("DEVELOPING", [developing], True)]
    assert remaining == [("CHASE / WAIT", [chase], False)]


def test_full_developing_detail_reuses_existing_radar_card_and_table(monkeypatch):
    first = _record("FIRST", "DEVELOPING")
    second = _record("SECOND", "DEVELOPING")
    events = []

    class FakeStreamlit:
        @contextmanager
        def expander(self, label, expanded=False):
            events.append(("expander", label, expanded))
            yield

        def dataframe(self, rows, **kwargs):
            events.append(("table", rows, kwargs))

    monkeypatch.setattr(ui, "st", FakeStreamlit())
    monkeypatch.setattr(
        ui,
        "scanner_v2_display_sections",
        lambda records: [("DEVELOPING", [first, second], True)],
    )
    monkeypatch.setattr(
        ui,
        "trader_priority_sort_key",
        lambda record: 2 if record["symbol"] == "SECOND" else 1,
    )
    monkeypatch.setattr(
        ui,
        "opportunity_card",
        lambda record: events.append(("card", record["symbol"])),
    )
    monkeypatch.setattr(
        ui,
        "radar_table",
        lambda records: [record["symbol"] for record in records],
    )

    layout.render_developing_detail([first, second])

    assert events[0] == ("expander", "DEVELOPING (2)", True)
    assert events[1:3] == [("card", "SECOND"), ("card", "FIRST")]
    assert events[3][0] == "table"
    assert events[3][1] == ["SECOND", "FIRST"]


def test_installed_contract_marks_one_shot_lower_duplicate_suppression():
    assert getattr(
        ui.scanner_v2_display_sections,
        "_gs359_developing_section_order",
        False,
    )
    assert getattr(
        ui.render_walter_mission_control,
        "_gs359_developing_section_order",
        False,
    )
