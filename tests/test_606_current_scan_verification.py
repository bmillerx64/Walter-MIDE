from copy import deepcopy

from mide.architecture import ArchitecturePolicy, Decision, STAGES, WalterArchitectureV1
from mide import architecture_verification


class Store:
    def persist(self, _records):
        pass


def _pass(records):
    return {
        row["symbol"]: Decision(True, "assessment", "recorded pass")
        for row in records
    }


def test_gs606_runtime_verification_uses_only_current_scan_audits(monkeypatch):
    discovered = [
        {"symbol": "A", "price": 1.0, "free_float": 1},
        {"symbol": "B", "price": 1.0, "free_float": 1},
    ]

    architecture = WalterArchitectureV1(
        policy=ArchitecturePolicy(.05, 5, 3_500_000),
        discover=lambda: deepcopy(discovered),
        catalyst=_pass,
        participation=_pass,
        expansion=_pass,
        rank=lambda rows: rows,
        store=Store(),
        publish=lambda _rows: None,
    )

    architecture.run()

    captured = {}
    real_verify = architecture_verification.verify_architecture

    def capture_verify(ledger, stages, **kwargs):
        captured["ledger"] = deepcopy(list(ledger))
        return real_verify(ledger, stages, **kwargs)

    monkeypatch.setattr(
        architecture_verification,
        "verify_architecture",
        capture_verify,
    )

    discovered[:] = [
        {"symbol": "B", "price": 1.0, "free_float": 1},
        {"symbol": "C", "price": 1.0, "free_float": 1},
    ]
    results = architecture.run()

    assert [row["symbol"] for row in captured["ledger"]] == ["B", "C"]
    assert all(
        len(row["architecture_audit"]) == len(STAGES)
        for row in captured["ledger"]
    )

    # Session history is still retained on the authoritative ledger.
    by_symbol = {row["symbol"]: row for row in results}
    assert len(by_symbol["B"]["architecture_audit"]) == 2 * len(STAGES)
    assert "A" in by_symbol
    assert architecture.verification_report["passed"] is True


def test_gs606_verification_input_is_compact_and_read_only_contract():
    source = open("mide/architecture.py", encoding="utf-8").read()
    start = source.index("verification_ledger = []")
    end = source.index("self.post_stage_timing[\"architecture_verification_ms\"]", start)
    block = source[start:end]

    assert "for symbol in current_order:" in block
    assert "audit_starts[symbol]" in block
    assert "verify_architecture(\n            verification_ledger," in block
    assert "results, self.trace" not in block

    forbidden = (
        "record.update(",
        "self._terminal(",
        "self._audit(",
        "qualified_for_entry =",
        "mission_rank =",
        "place_order(",
        "submit_order(",
    )
    assert not any(token in block for token in forbidden)
