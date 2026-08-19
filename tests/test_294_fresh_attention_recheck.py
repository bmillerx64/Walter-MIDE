from mide.gs294_fresh_attention_recheck import RECHECK_REASON, select_recheck_symbols


def candidate(symbol, **overrides):
    record = {
        "symbol": symbol,
        "discovery_last_seen_scan": 7,
        "discovery_reasons": ["Webull OpenAPI universe"],
        "terminal_outcome": "Rejected",
        "terminal_stage": "Expansion Assessment",
        "conviction_score": 50,
        "participation_score": 60,
        "pct_change": 12,
    }
    record.update(overrides)
    return record


def test_prior_attention_name_gets_one_fresh_recheck_when_native_feed_drops_it():
    records = {"WALT": candidate("WALT")}
    assert select_recheck_symbols(
        records, current_symbols=set(), last_completed_scan=7
    ) == ["WALT"]


def test_current_native_symbol_is_never_duplicated_by_recheck():
    records = {"WALT": candidate("WALT")}
    assert select_recheck_symbols(
        records, current_symbols={"WALT"}, last_completed_scan=7
    ) == []


def test_recheck_does_not_become_permanent_universe_membership():
    records = {
        "WALT": candidate(
            "WALT",
            discovery_reasons=[RECHECK_REASON],
        )
    }
    assert select_recheck_symbols(
        records, current_symbols=set(), last_completed_scan=7
    ) == []


def test_only_immediately_prior_fresh_scan_can_seed_recheck():
    records = {
        "OLD": candidate("OLD", discovery_last_seen_scan=6),
        "NOW": candidate("NOW", discovery_last_seen_scan=7),
    }
    assert select_recheck_symbols(
        records, current_symbols=set(), last_completed_scan=7
    ) == ["NOW"]


def test_technical_failures_and_early_gate_rejections_are_not_carried():
    records = {
        "TECH": candidate("TECH", terminal_outcome="Technical Failure"),
        "PRICE": candidate("PRICE", terminal_stage="Price Gate"),
        "PART": candidate("PART", terminal_stage="Participation Assessment"),
    }
    assert select_recheck_symbols(
        records, current_symbols=set(), last_completed_scan=7
    ) == ["PART"]


def test_recheck_is_bounded_and_prioritizes_ranked_then_stronger_attention():
    records = {
        "R2": candidate("R2", mission_rank=2, conviction_score=40),
        "R1": candidate("R1", mission_rank=1, conviction_score=30),
        "HOT": candidate("HOT", conviction_score=80, participation_score=90),
        "WARM": candidate("WARM", conviction_score=70, participation_score=80),
    }
    assert select_recheck_symbols(
        records,
        current_symbols=set(),
        last_completed_scan=7,
        limit=3,
    ) == ["R1", "R2", "HOT"]


def test_selector_is_observational_and_does_not_mutate_ledger_records():
    records = {"WALT": candidate("WALT")}
    before = repr(records)
    select_recheck_symbols(records, current_symbols=set(), last_completed_scan=7)
    assert repr(records) == before
