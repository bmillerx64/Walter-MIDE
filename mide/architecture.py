"""Executable contract for the authoritative Walter Architecture v1.0."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from time import perf_counter
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


class WalterCandidateLedger:
    """Session-long candidate identity and ranking history.

    The architecture owns mutations of these records.  Callers may keep one ledger
    across live scans without carrying forward stale scanner snapshots themselves.
    """

    def __init__(self) -> None:
        self.records: dict[str, dict] = {}
        self.scan_number = 0


def _number(record: Mapping[str, object], *keys: str) -> float:
    for key in keys:
        try:
            if record.get(key) is not None:
                return float(record[key])
        except (TypeError, ValueError):
            pass
    return 0.0


def _ranking_evidence(record: Mapping[str, object]) -> dict[str, object]:
    """Capture the four live dimensions used to explain ranking movement."""
    status = str(record.get("candidate_status") or record.get("status") or "")
    return {
        "conviction": _number(record, "conviction_score", "scanner_v2_score", "opportunity_score"),
        "participation": _number(record, "participation_surge_score", "participation_score"),
        "expansion": _number(record, "expansion_score", "confluence_score", "momentum_quality_score"),
        "entry_readiness": bool(record.get("qualified_for_entry", status.lower() == "entry ready")),
        "vwap_reclaimed": str(record.get("vwap_relation") or "").lower() == "above",
        "supertrend_bullish": bool(record.get("supertrend_bullish")),
        "volume_expansion": _number(record, "volume_expansion", "volume_acceleration", "volume_ratio"),
        "catalyst_age_minutes": _number(record, "catalyst_age_minutes", "news_age_minutes"),
    }


def _movement_reasons(previous: Mapping[str, object], current: Mapping[str, object]) -> list[str]:
    reasons = []
    if current["participation"] > previous["participation"]:
        reasons.append("increased participation")
    elif current["participation"] < previous["participation"]:
        reasons.append("weakening participation")
    if current["vwap_reclaimed"] and not previous["vwap_reclaimed"]:
        reasons.append("VWAP reclaim")
    elif previous["vwap_reclaimed"] and not current["vwap_reclaimed"]:
        reasons.append("failed reclaim")
    if current["supertrend_bullish"] != previous["supertrend_bullish"]:
        reasons.append("SuperTrend flip")
    if current["volume_expansion"] > previous["volume_expansion"]:
        reasons.append("volume expansion")
    if (current["catalyst_age_minutes"] > previous["catalyst_age_minutes"]
            and current["catalyst_age_minutes"] >= 60):
        reasons.append("stale catalyst")
    return reasons


@dataclass(frozen=True)
class ArchitecturePolicy:
    """Configurable gate policy; values are deliberately not architecture constants."""

    min_price: float
    max_price: float
    max_free_float: int
    include_etfs: bool = False


@dataclass(frozen=True)
class Decision:
    passed: bool
    category: str
    reason: str
    updates: Mapping[str, object] = field(default_factory=dict)
    evidence: object = field(default_factory=dict)
    provenance: object = field(default_factory=dict)


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
        free_float: Stage | None = None,
        rank: Ranker | None = None,
        store: ResultStore | None = None,
        publish: Publisher | None = None,
        runtime_dispatch: Callable[[], Any] | None = None,
        stage_observer: Callable[[int, str, list[dict]], None] | None = None,
        failure_observer: Callable[[str, str, BaseException], None] | None = None,
        clock: Callable[[], datetime] | None = None,
        timer: Callable[[], float] | None = None,
        after_price_gate: Callable[[list[dict]], None] | None = None,
        ledger: WalterCandidateLedger | None = None,
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
        self.free_float = free_float or self._float
        self.rank = rank
        self.store = store
        self.publish = publish
        self.stage_observer = stage_observer
        self.failure_observer = failure_observer
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.timer = timer or perf_counter
        self.after_price_gate = after_price_gate
        self.trace: list[dict] = []
        self.purity_observations: list[dict] = []
        self.candidate_ledger = ledger or WalterCandidateLedger()
        self._ledger = self.candidate_ledger.records
        self.operational_summary: dict[str, object] = {}

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

    def _timestamp(self) -> str:
        value = self.clock()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def _audit(
        self, record: dict, stage: str, *, input_status: str, decision: str,
        reason: str, evidence: object = None, provenance: object = None,
    ) -> None:
        record["architecture_audit"].append({
            "stage": stage,
            "input_status": input_status,
            "decision": decision,
            "evidence": {} if evidence is None else evidence,
            "reason": reason,
            "provenance": {} if provenance is None else provenance,
            "timestamp": self._timestamp(),
        })

    def _record_trace(
        self, stage: str, input_count: int, output_count: int, *,
        started_at: float, technical_failures: int = 0,
    ) -> None:
        rejected = max(0, input_count - output_count - technical_failures)
        self.trace.append({
            "number": len(self.trace) + 1,
            "stage": stage,
            "executions": 1,
            "input_count": input_count,
            "output_count": output_count,
            "passed_count": output_count,
            "rejection_count": rejected,
            "rejected_count": rejected,
            "technical_failure_count": technical_failures,
            "execution_time_ms": round((self.timer() - started_at) * 1000, 3),
        })

    def _assess(self, stage: str, candidates: list[dict], operation: Stage) -> list[dict]:
        started_at = self.timer()
        symbols = [self._symbol(item) for item in candidates]
        try:
            decisions = operation([dict(item) for item in candidates])
        except Exception as exc:
            # A provider/enricher commonly raises for just one bad symbol. Retry
            # independently so that candidate cannot terminate or erase its peers.
            decisions = {}
            for item in candidates:
                symbol = self._symbol(item)
                try:
                    one = operation([dict(item)])
                    if set(one) != {symbol}:
                        raise ArchitectureViolation(
                            f"{stage} must decide candidate {symbol}"
                        )
                    decisions[symbol] = one[symbol]
                except Exception as candidate_exc:
                    if self.failure_observer:
                        self.failure_observer(stage, symbol, candidate_exc)
                    self._terminal(
                        item, "Technical Failure", stage, "Stage execution",
                        f"{type(candidate_exc).__name__}: {candidate_exc}",
                    )
                    self._audit(
                        item, stage, input_status="Active", decision="Technical Failure",
                        reason=item["terminal_reason"],
                        evidence={"exception_type": type(candidate_exc).__name__},
                    )
        active_symbols = {
            self._symbol(item) for item in candidates
            if item.get("terminal_outcome") != "Technical Failure"
        }
        if set(decisions) != active_symbols:
            raise ArchitectureViolation(f"{stage} must decide every and only input symbol")
        output = []
        for item in candidates:
            symbol = self._symbol(item)
            if item.get("terminal_outcome") == "Technical Failure":
                continue
            decision = decisions[symbol]
            forbidden = {
                "Catalyst Assessment": {"price", "free_float", "mission_rank", "ranking"},
                "Participation Assessment": {"price", "free_float", "catalyst", "mission_rank", "ranking"},
                "Expansion Assessment": {"price", "free_float", "catalyst", "mission_rank", "ranking"},
            }.get(stage, set())
            impure = sorted(forbidden.intersection(decision.updates))
            if impure:
                self.purity_observations.append({
                    "stage": stage, "symbols": [symbol],
                    "violation": f"{stage} wrote fields owned by another stage: {', '.join(impure)}",
                })
            item.update(decision.updates)
            self._audit(
                item, stage, input_status="Active",
                decision="Qualified" if decision.passed else "Rejected",
                reason=decision.reason, evidence=decision.evidence,
                provenance=decision.provenance,
            )
            if decision.passed:
                output.append(item)
            else:
                self._terminal(item, "Rejected", stage, decision.category, decision.reason)
        failures = sum(
            item.get("terminal_outcome") == "Technical Failure" for item in candidates
        )
        self._record_trace(
            stage, len(candidates), len(output), started_at=started_at,
            technical_failures=failures,
        )
        return output

    def _price(self, candidates: list[dict]) -> Mapping[str, Decision]:
        result = {}
        for item in candidates:
            symbol = self._symbol(item)
            try:
                price = float(item["price"])
                passed = self.policy.min_price <= price <= self.policy.max_price
                reason = "Price within configured range" if passed else "Price outside configured range"
            except (KeyError, StopIteration, TypeError, ValueError):
                passed, reason = False, "Usable price unavailable"
            result[symbol] = Decision(passed, "Price", reason)
        return result

    def _validity(self, candidates: list[dict]) -> Mapping[str, Decision]:
        result = {}
        for item in candidates:
            symbol = WalterArchitectureV1._symbol(item)
            # Halts are intentionally absent from rejection predicates and their
            # provider metadata remains untouched on the record.
            valid_data = bool(item.get("data_usable", True))
            legal = bool(item.get("legally_tradable", item.get("tradable", True)))
            operational = bool(item.get("operationally_tradable", True))
            asset_type = str(item.get("asset_type") or item.get("type") or "").lower()
            symbol = self._symbol(item)
            supported_security = not (
                asset_type in {"warrant", "right", "unit"}
                or (asset_type in {"etf", "fund"} and not self.policy.include_etfs)
                or bool(re.search(r"(?:\.|-)?[WRU]$", symbol))
                or str(item.get("exchange") or "").upper() == "OTC"
                or str(item.get("asset_status") or "active").lower() != "active"
            )
            passed = valid_data and legal and operational and supported_security
            failures = [name for ok, name in (
                (valid_data, "unusable data"), (legal, "legally non-tradable"),
                (operational, "operationally non-tradable"),
                (supported_security, "unsupported security type or status"),
            ) if not ok]
            result[symbol] = Decision(passed, "Validity", "Valid security" if passed else "; ".join(failures))
        return result

    def _float(self, candidates: list[dict]) -> Mapping[str, Decision]:
        result = {}
        for item in candidates:
            symbol = self._symbol(item)
            try:
                value = next(
                    float(item[key])
                    for key in ("free_float", "float_shares", "shares_float")
                    if item.get(key) is not None
                )
                passed = value <= self.policy.max_free_float
                reason = "Free float within configured limit" if passed else "Free float exceeds configured limit"
            except (KeyError, StopIteration, TypeError, ValueError):
                passed, reason = False, "Usable free-float value unavailable"
            result[symbol] = Decision(passed, "Free Float", reason)
        return result

    def run(self) -> Any:
        runtime_dispatch = self._runtime_dispatch
        if runtime_dispatch is not None:
            return runtime_dispatch()

        # A run is one complete live scan. Trace counts therefore remain an
        # eight-stage proof of ordering rather than accumulating across scans.
        self.trace = []
        self.purity_observations = []
        self.candidate_ledger.scan_number += 1
        scan_number = self.candidate_ledger.scan_number
        scan_timestamp = self._timestamp()
        audit_starts = {
            symbol: len(record.get("architecture_audit", []))
            for symbol, record in self._ledger.items()
        }
        universe_started = self.timer()
        self.stage_observer and self.stage_observer(1, STAGES[0], [])
        discovered = list(self.discover())
        current_symbols: set[str] = set()
        current_order: list[str] = []
        for source in discovered:
            symbol = self._symbol(source)
            if not symbol:
                raise ArchitectureViolation("Universe candidate has no symbol")
            if symbol not in current_symbols:
                current_order.append(symbol)
            current_symbols.add(symbol)
            if symbol not in self._ledger:
                record = dict(
                    source, symbol=symbol, candidate_id=symbol,
                    architecture_audit=[], ranking_history=[],
                )
                self._ledger[symbol] = record
                audit_starts[symbol] = 0
            else:
                # Merge the newest market evidence into the authoritative object;
                # never replace it (UI/store references and candidate_id stay stable).
                record = self._ledger[symbol]
                protected = {
                    "candidate_id": record["candidate_id"],
                    "architecture_audit": record["architecture_audit"],
                    "ranking_history": record.setdefault("ranking_history", []),
                }
                record.update(source, symbol=symbol)
                record.update(protected)
            for key in ("terminal_outcome", "terminal_stage", "terminal_category", "terminal_reason", "mission_rank"):
                self._ledger[symbol].pop(key, None)
        candidates = [self._ledger[symbol] for symbol in current_order]
        for record in candidates:
            provenance = {
                key: record[key] for key in ("provider", "source", "sources", "discovery_reasons")
                if record.get(key) is not None
            }
            self._audit(
                record, STAGES[0], input_status="Discovered", decision="Admitted",
                reason="Normalized symbol admitted by Universe Construction",
                evidence={"normalized_symbol": record["symbol"]}, provenance=provenance,
            )
        self._record_trace(
            STAGES[0], len(discovered), len(candidates),
            started_at=universe_started,
            technical_failures=0,
        )
        for number, stage, operation in (
            (2, STAGES[1], self._price), (3, STAGES[2], self._validity),
            (4, STAGES[3], self.free_float), (5, STAGES[4], self.catalyst),
            (6, STAGES[5], self.participation), (7, STAGES[6], self.expansion),
        ):
            self.stage_observer and self.stage_observer(number, stage, candidates)
            candidates = self._assess(stage, candidates, operation)
            # Runtime adapters may hydrate the survivors after the cheap price
            # decision.  This deliberately sits between Price and Validity so
            # the eight-stage architecture and every decision predicate remain
            # unchanged.
            if number == 2 and self.after_price_gate:
                self.after_price_gate(candidates)

        ranking_started = self.timer()
        self.stage_observer and self.stage_observer(8, STAGES[7], candidates)
        ranked = self.rank([dict(item) for item in candidates])
        before = [self._symbol(item) for item in candidates]
        after = [self._symbol(item) for item in ranked]
        if len(after) != len(set(after)) or set(after) != set(before):
            raise ArchitectureViolation("Mission Ranking must preserve Expansion membership")
        for position, ranked_record in enumerate(ranked, 1):
            symbol = self._symbol(ranked_record)
            if ranked_record.get("candidate_id") != self._ledger[symbol]["candidate_id"]:
                raise ArchitectureViolation("Mission Ranking must preserve candidate identity")
            self._ledger[symbol].update(ranked_record, mission_rank=position)
            self._terminal(self._ledger[symbol], "Qualified and Ranked", STAGES[7], "Ranking", "Expansion-qualified candidate ranked")
            self._audit(
                self._ledger[symbol], STAGES[7], input_status="Expansion Qualified",
                decision="Qualified and Ranked",
                reason="Expansion-qualified candidate ranked",
                evidence={"mission_rank": position},
            )
        qualified_symbols = set(after)
        for symbol in current_symbols:
            record = self._ledger[symbol]
            evidence = _ranking_evidence(record)
            history = record.setdefault("ranking_history", [])
            prior = history[-1] if history else None
            previous_evidence = prior.get("evidence", {}) if prior else {}
            delta = evidence["conviction"] - previous_evidence.get("conviction", evidence["conviction"])
            record["conviction_change"] = round(delta, 3)
            record["conviction_trend"] = "↑" if delta > 0 else "↓" if delta < 0 else "→"
            reasons = _movement_reasons(previous_evidence, evidence) if prior else []
            previous_rank = prior.get("rank") if prior else None
            rank_now = record.get("mission_rank") if symbol in qualified_symbols else None
            if prior and previous_rank != rank_now and not reasons:
                reasons.append("relative ranking changed")
            record["ranking_move_reasons"] = reasons
            history.append({
                "scan": scan_number, "timestamp": scan_timestamp, "rank": rank_now,
                "qualified": symbol in qualified_symbols, "previous_rank": previous_rank,
                "conviction_change": round(delta, 3), "conviction_trend": record["conviction_trend"],
                "reasons": list(reasons), "evidence": evidence,
            })
        # Candidates no longer present remain in history, but cannot leak into
        # Today's Mission from an earlier scan.
        for symbol, record in self._ledger.items():
            if symbol not in current_symbols:
                record.pop("mission_rank", None)
                self._terminal(record, "Rejected", STAGES[0], "Universe", "Not present in current live universe")
                history = record.setdefault("ranking_history", [])
                previous_rank = history[-1].get("rank") if history else None
                record["ranking_move_reasons"] = ["removed from live universe"]
                history.append({
                    "scan": scan_number, "timestamp": scan_timestamp, "rank": None,
                    "qualified": False, "previous_rank": previous_rank,
                    "conviction_change": 0.0, "conviction_trend": "→",
                    "reasons": ["removed from live universe"],
                    "evidence": _ranking_evidence(record),
                })
        self._record_trace(
            STAGES[7], len(candidates), len(ranked), started_at=ranking_started,
        )
        results = list(self._ledger.values())
        for record in (self._ledger[symbol] for symbol in current_order):
            audited = {
                entry["stage"]
                for entry in record["architecture_audit"][audit_starts[record["symbol"]]:]
            }
            for stage in STAGES:
                if stage not in audited:
                    self._audit(
                        record, stage, input_status="Not eligible",
                        decision="Not evaluated",
                        reason=f"Candidate already terminated at {record['terminal_stage']}",
                    )
        from mide.decision_narrative import attach_decision_narratives

        attach_decision_narratives(results)
        if any(item.get("terminal_outcome") not in TERMINAL_OUTCOMES for item in results):
            raise ArchitectureViolation("Every discovered candidate requires a terminal outcome")
        self.store.persist(results)
        # Publish the authoritative ledger objects in ranking order so the UI
        # receives the terminal outcome, complete audit, and mission rank that
        # were persisted—not the ranker's detached working copies.
        published = sorted(
            (item for item in results if item["terminal_outcome"] == "Qualified and Ranked"),
            key=lambda item: item["mission_rank"],
        )
        self.publish(published)
        from mide.operational_validation import validate_runtime

        self.operational_summary = validate_runtime(
            ledger=results, published=published, stages=self.trace,
            persistence_completed=True,
        )
        from mide.architecture_verification import verify_architecture

        self.verification_report = verify_architecture(
            results, self.trace, purity_observations=self.purity_observations,
        ).as_dict()
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
