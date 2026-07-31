from copy import deepcopy

from mide.universe_diagnostics import UniverseVerification


class Client:
    provider_name = "Test Provider"
    warnings = []


def test_source_merge_duplicate_and_membership_accounting_is_read_only():
    source = [{"symbol": " aaa "}, {"symbol": "AAA"}, {"symbol": "BBB"}, {"symbol": ""}]
    before = deepcopy(source)
    verification = UniverseVerification(Client(), feed="iex")
    returned = verification.call("Market movers", "movers", {"top": 50}, lambda: source)
    report = verification.finish(["AAA"], transitions=[{
        "transition_function_name": "rotating slice", "input_count": 2,
        "output_count": 1, "removed_count": 1,
        "exact_reason_categories": ["outside slice"],
        "affected_symbols_grouped_by_reason": {"outside slice": ["BBB"]},
    }], entered_price_gate={"AAA"})

    assert returned == before == source
    assert report["sources"][0]["raw_objects_returned"] == 4
    assert report["sources"][0]["raw_unique_symbols_returned"] == 2
    assert report["sources"][0]["duplicate_symbols_within_source"] == 1
    assert report["merge_accounting"]["final_universe_membership"] == ["AAA"]
    assert report["merge_accounting"]["invalid_or_blank_symbols_removed"] == 1
    assert report["status"] == "PASS"


def test_unexplained_loss_fails_contract():
    verification = UniverseVerification(Client(), feed="sip")
    verification.call("Most active stocks", "most_actives", {},
                      lambda: [{"symbol": "LOST"}])
    report = verification.finish([])
    assert report["status"] == "FAIL"
    assert report["unexplained_losses"] == ["LOST"]
    assert not report["contract_check"]["equation_holds"]


def test_snapshot_transition_documents_price_gate_non_entry():
    verification = UniverseVerification(Client(), feed="iex")
    verification.call("Market movers", "movers", {},
                      lambda: [{"symbol": "GOOD"}, {"symbol": "NO_DATA"}])
    report = verification.finish(["GOOD", "NO_DATA"], transitions=[{
        "transition_function_name": "snapshot retrieval", "input_count": 2,
        "output_count": 1, "removed_count": 1,
        "exact_reason_categories": ["snapshot unavailable"],
        "affected_symbols_grouped_by_reason": {"snapshot unavailable": ["NO_DATA"]},
    }], entered_price_gate={"GOOD"})
    paths = {row["normalized_symbol"]: row for row in report["symbols"]}
    assert paths["NO_DATA"]["admitted_to_universe"]
    assert not paths["NO_DATA"]["entered_price_gate"]
    assert paths["NO_DATA"]["removal_reason"] == "snapshot unavailable"
