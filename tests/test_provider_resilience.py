from mide.architecture import ArchitecturePolicy, Decision, WalterArchitectureV1
from mide.news_provider import NewsProvider, NewsService
from mide.resilience import record_provider_failure


class MemoryStore:
    def __init__(self): self.items = None
    def persist(self, items): self.items = items


def test_candidate_exception_is_isolated_and_empty_later_stages_complete(tmp_path):
    store = MemoryStore()
    published = []

    def stage(records):
        symbol = records[0]["symbol"] if len(records) == 1 else None
        if symbol == "BAD" or len(records) > 1:
            raise ValueError("malformed indicator response")
        return {records[0]["symbol"]: Decision(True, "ok", "ok")}

    architecture = WalterArchitectureV1(
        policy=ArchitecturePolicy(1, 10, 10_000_000),
        discover=lambda: [
            {"symbol": "GOOD", "price": 2, "free_float": 10},
            {"symbol": "BAD", "price": 2, "free_float": 10},
        ], catalyst=stage, participation=stage, expansion=stage,
        free_float=stage, rank=lambda records: records, store=store,
        publish=published.extend,
    )
    ledger = architecture.run()
    outcomes = {item["symbol"]: item["terminal_outcome"] for item in ledger}
    assert outcomes == {"GOOD": "Qualified and Ranked", "BAD": "Technical Failure"}
    assert len(architecture.trace) == 8


def test_news_outage_falls_back_and_records_complete_diagnostic(tmp_path):
    class Failed(NewsProvider):
        name = "failed news"
        def fetch(self, **kwargs): raise TimeoutError("timed out")
    class Empty(NewsProvider):
        name = "backup news"
        def fetch(self, **kwargs): return []

    service = NewsService([Failed(), Empty()], state_path=tmp_path / "state.json")
    assert service.fetch(symbols=["ABC"]) == []
    assert service.metrics["active_provider"] == "backup news"
    event = service.metrics["provider_failure_diagnostics"][0]
    assert set(event) == {"provider", "operation", "exception", "affected_symbols", "recovery_action"}
    assert event["affected_symbols"] == ["ABC"]


def test_structured_diagnostics_support_partial_symbol_failures():
    diagnostics = {}
    record_provider_failure(
        diagnostics, provider="float", operation="lookup", exception=ValueError("bad payload"),
        affected_symbols=["BAD"], recovery_action="preserve prior data and continue",
    )
    assert diagnostics["provider_failures"][0]["affected_symbols"] == ["BAD"]
