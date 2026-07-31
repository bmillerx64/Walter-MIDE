"""Executable contract for the authoritative Walter Architecture v1.0."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Protocol


STAGES = (
    "Universe Construction",
    "Price Gate",
    "Validity Gate",
    "Free-Float Gate",
    "Catalyst Assessment",
    "Participation Assessment",
    "Expansion Assessment",
    "Mission Ranking and Publication",
)
TERMINAL_OUTCOMES = {"Rejected", "Qualified and Ranked", "Technical Failure"}


@dataclass(frozen=True)
class ArchitecturePolicy:
    """Configurable gate policy; values are deliberately not architecture constants."""

    min_price: float
    max_price: float
    max_free_float: int


@dataclass(frozen=True)
class Decision:
    passed: bool
    category: str
    reason: str
    updates: Mapping[str, object] = field(default_factory=dict)


class ArchitectureViolation(RuntimeError):
    """Raised when an implementation attempts to violate pipeline membership."""


class ResultStore(Protocol):
    def persist(self, results: list[dict]) -> None: ...


Stage = Callable[[list[dict]], Mapping[str, Decision]]
Ranker = Callable[[list[dict]], list[dict]]
Publisher = Callable[[list[dict]], None]


class WalterArchitectureV1:
    """Run the eight stages once, in order, with a complete candidate ledger."""

    def __init__(
        self,
        *,
        policy: ArchitecturePolicy | None = None,
        discover: Callable[[], Iterable[dict]] | None = None,
        catalyst: Stage | None = None,
        participation: Stage | None = None,
        expansion: Stage | None = None,
        rank: Ranker | None = None,
        store: ResultStore | None = None,
        publish: Publisher | None = None,
        runtime_dispatch: Callable[[], Any] | None = None,
    ) -> None:
        self._runtime_dispatch = runtime_dispatch
        if runtime_dispatch is not None:
            return
        components = (
            policy,
            discover,
            catalyst,
            participation,
            expansion,
            rank,
            store,
            publish,
        )
        if any(value is None for value in components):
            raise TypeError("Walter architecture requires a complete pipeline")
        self.policy = policy
        self.discover = discover
        self.catalyst = catalyst
        self.participation = participation
        self.expansion = expansion
        self.rank = rank
        self.store = store
        self.publish = publish
        self.trace: list[dict] = []
        self._ledger: dict[str, dict] = {}

    @classmethod
    def for_runtime(cls, dispatch: Callable[[], Any]) -> "WalterArchitectureV1":
        """Create the production entry point around the unchanged live scanner."""
        return cls(runtime_dispatch=dispatch)

    @staticmethod
    def _symbol(record: Mapping[str, object]) -> str:
        return str(record.get("symbol") or "").strip().upper()

    def _terminal(self, record: dict, outcome: str, stage: str, category: str, reason: str) -> None:
        record.update(
            terminal_outcome=outcome,
            terminal_stage=stage,
            terminal_category=category,
            terminal_reason=reason,
        )

    def _record_trace(self, stage: str, input_count: int, output_count: int) -> None:
        self.trace.append({
            "number": len(self.trace) + 1,
            "stage": stage,
            "executions": 1,
            "input_count": input_count,
            "output_count": output_count,
        })

    def _assess(self, stage: str, candidates: list[dict], operation: Stage) -> list[dict]:
        symbols = [self._symbol(item) for item in candidates]
        try:
            decisions = operation([dict(item) for item in candidates])
        except Exception as exc:
            for item in candidates:
                self._terminal(item, "Technical Failure", stage, "Stage execution", str(exc))
            self._record_trace(stage, len(candidates), 0)
            return []
        if set(decisions) != set(symbols):
            raise ArchitectureViolation(f"{stage} must decide every and only input symbol")
        output = []
        for item in candidates:
            symbol = self._symbol(item)
            decision = decisions[symbol]
            item.update(decision.updates)
            item.setdefault("architecture_audit", []).append({
                "stage": stage,
                "category": decision.category,
                "reason": decision.reason,
                "passed": decision.passed,
            })
            if decision.passed:
                output.append(item)
            else:
                self._terminal(item, "Rejected", stage, decision.category, decision.reason)
        self._record_trace(stage, len(candidates), len(output))
        return output

    def _price(self, candidates: list[dict]) -> Mapping[str, Decision]:
        result = {}
        for item in candidates:
            symbol = self._symbol(item)
            try:
                price = float(item["price"])
                passed = self.policy.min_price <= price <= self.policy.max_price
                reason = "Price within configured range" if passed else "Price outside configured range"
            except (KeyError, TypeError, ValueError):
                passed, reason = False, "Usable price unavailable"
            result[symbol] = Decision(passed, "Price", reason)
        return result

    @staticmethod
    def _validity(candidates: list[dict]) -> Mapping[str, Decision]:
        result = {}
        for item in candidates:
            symbol = WalterArchitectureV1._symbol(item)
            # Halts are intentionally absent from rejection predicates and their
            # provider metadata remains untouched on the record.
            valid_data = bool(item.get("data_usable", True))
            legal = bool(item.get("legally_tradable", item.get("tradable", True)))
            operational = bool(item.get("operationally_tradable", True))
            passed = valid_data and legal and operational
            failures = [name for ok, name in (
                (valid_data, "unusable data"), (legal, "legally non-tradable"),
                (operational, "operationally non-tradable"),
            ) if not ok]
            result[symbol] = Decision(passed, "Validity", "Valid security" if passed else "; ".join(failures))
        return result

    def _float(self, candidates: list[dict]) -> Mapping[str, Decision]:
        result = {}
        for item in candidates:
            symbol = self._symbol(item)
            try:
                value = float(item["free_float"])
                passed = value <= self.policy.max_free_float
                reason = "Free float within configured limit" if passed else "Free float exceeds configured limit"
            except (KeyError, TypeError, ValueError):
                passed, reason = False, "Usable free-float value unavailable"
            result[symbol] = Decision(passed, "Free Float", reason)
        return result

    def run(self) -> Any:
        runtime_dispatch = self._runtime_dispatch
        if runtime_dispatch is not None:
            return runtime_dispatch()

        discovered = list(self.discover())
        for source in discovered:
            symbol = self._symbol(source)
            if not symbol:
                raise ArchitectureViolation("Universe candidate has no symbol")
            if symbol not in self._ledger:
                record = dict(source, symbol=symbol, architecture_audit=[])
                self._ledger[symbol] = record
        candidates = list(self._ledger.values())
        self._record_trace(STAGES[0], len(discovered), len(candidates))
        candidates = self._assess(STAGES[1], candidates, self._price)
        candidates = self._assess(STAGES[2], candidates, self._validity)
        candidates = self._assess(STAGES[3], candidates, self._float)
        candidates = self._assess(STAGES[4], candidates, self.catalyst)
        candidates = self._assess(STAGES[5], candidates, self.participation)
        candidates = self._assess(STAGES[6], candidates, self.expansion)

        ranked = self.rank([dict(item) for item in candidates])
        before = [self._symbol(item) for item in candidates]
        after = [self._symbol(item) for item in ranked]
        if len(after) != len(set(after)) or set(after) != set(before):
            raise ArchitectureViolation("Mission Ranking must preserve Expansion membership")
        for position, ranked_record in enumerate(ranked, 1):
            symbol = self._symbol(ranked_record)
            self._ledger[symbol].update(ranked_record, mission_rank=position)
            self._terminal(self._ledger[symbol], "Qualified and Ranked", STAGES[7], "Ranking", "Expansion-qualified candidate ranked")
        self._record_trace(STAGES[7], len(candidates), len(ranked))
        results = list(self._ledger.values())
        if any(item.get("terminal_outcome") not in TERMINAL_OUTCOMES for item in results):
            raise ArchitectureViolation("Every discovered candidate requires a terminal outcome")
        self.store.persist(results)
        self.publish(ranked)
        return results


SCANNER_IMPLEMENTATIONS = {
    "Walter Architecture v1.0": WalterArchitectureV1,
    # Existing programmatic callers retain their selections while the live UI
    # now names the authoritative architecture. All selections resolve here.
    "Decision Funnel 3.0": WalterArchitectureV1,
    "Scanner V1 (classic screener)": WalterArchitectureV1,
    "Scanner V2 (adaptive momentum)": WalterArchitectureV1,
}


def scanner_implementation(selection: str):
    """Resolve the UI selection without a fallback or alternate pipeline."""
    return SCANNER_IMPLEMENTATIONS[selection]
