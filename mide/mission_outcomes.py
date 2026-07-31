"""Persistent, downstream measurements for candidates published to Mission.

The tracker deliberately consumes copies of the candidate ledger.  It has no
reference to the ranker, its policy, or the objects stored in the authoritative
ledger, so a data/provider failure here cannot change a Walter decision.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from collections import defaultdict
from statistics import mean
from typing import Any, Iterable, Mapping, Sequence


INTERVALS = (("2m", 2), ("5m", 5), ("10m", 10), ("15m", 15), ("30m", 30))
CLASSIFICATIONS = ("Excellent", "Good", "Neutral", "Weak", "Failed", "Never Triggered")
COMPONENTS = (
    "Catalyst Assessment", "Participation Assessment", "Expansion Assessment",
    "Conviction", "Entry Readiness", "Mission Ranking",
)


def _time(value: Any = None) -> datetime:
    if isinstance(value, datetime):
        stamp = value
    elif value:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    else:
        stamp = datetime.now(timezone.utc)
    return (stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp).astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _number(record: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        try:
            value = record.get(key)
            if value not in (None, ""):
                return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _ready(record: Mapping[str, Any]) -> bool:
    state = str(record.get("candidate_status") or record.get("status") or "").lower()
    normalized = state.replace("_", " ")
    return bool(record.get("qualified_for_entry") or normalized in {"entry ready", "entry window", "entry window open"})


def _minutes(start: Any, end: Any) -> float | None:
    if not start or not end:
        return None
    return round((_time(end) - _time(start)).total_seconds() / 60, 3)


def _avg(values: Iterable[Any]) -> float | None:
    numbers = [float(value) for value in values if value is not None]
    return round(mean(numbers), 4) if numbers else None


def _readiness_band(value: Any) -> str:
    text = str(value or "").lower().replace("_", " ")
    if "entry" in text and ("window" in text or "ready" in text):
        return "Entry Window"
    if "early" in text:
        return "Early"
    return "Watch"


def classify_outcome(record: Mapping[str, Any]) -> str:
    """Classify a completed observation using fixed, documented outcome facts."""
    if not record.get("became_entry_ready"):
        return "Never Triggered"
    change = record.get("closing_outcome")
    change = change.get("percentage_change") if isinstance(change, Mapping) else change
    mfe = record.get("maximum_favorable_excursion")
    if record.get("stop_level_reached") or (change is not None and float(change) <= -5):
        return "Failed"
    if record.get("profit_target_reached") or (mfe is not None and float(mfe) >= 10):
        return "Excellent"
    if change is not None and float(change) >= 3:
        return "Good"
    if change is not None and float(change) < 0:
        return "Weak"
    return "Neutral"


def _component_predictions(record: Mapping[str, Any]) -> dict[str, bool]:
    catalyst = record.get("catalyst_evidence")
    readiness = _readiness_band(record.get("initial_readiness_state")) == "Entry Window"
    return {
        "Catalyst Assessment": bool(catalyst),
        "Participation Assessment": float(record.get("initial_participation_score") or 0) >= 50,
        "Expansion Assessment": float(record.get("initial_expansion_score") or 0) >= 50,
        "Conviction": float(record.get("initial_conviction") or 0) >= 50,
        "Entry Readiness": readiness,
        "Mission Ranking": record.get("initial_rank") == 1,
    }


class MissionOutcomeStore:
    """Incrementally persist one record for each contiguous Mission appearance."""

    def __init__(self, path: str | Path = "data/mission_candidate_outcomes.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def all(self) -> list[dict]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, list) else []
        except (OSError, ValueError, TypeError):
            return []

    def _write(self, records: list[dict]) -> None:
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")
        temporary.replace(self.path)

    @staticmethod
    def _identity(candidate: Mapping[str, Any]) -> str:
        return str(candidate.get("candidate_id") or candidate.get("symbol") or "").strip()

    def _new_record(self, candidate: Mapping[str, Any], stamp: datetime, records: list[dict]) -> dict:
        identity = self._identity(candidate)
        session = stamp.date().isoformat()
        appearance = 1 + sum(
            item.get("candidate_identity") == identity and item.get("session_date") == session
            for item in records
        )
        price = _number(candidate, "price", "last_price", "close")
        status = candidate.get("candidate_status") or candidate.get("status")
        record = {
            "outcome_id": f"{session}|{identity}|{appearance}",
            "session_date": session,
            "appearance": appearance,
            "symbol": str(candidate.get("symbol") or "").upper(),
            "candidate_identity": identity,
            "first_mission_timestamp": _iso(stamp),
            "initial_rank": candidate.get("mission_rank"),
            "initial_price": price,
            "initial_conviction": _number(candidate, "conviction_score", "scanner_v2_score", "opportunity_score"),
            "initial_participation_score": _number(candidate, "participation_surge_score", "participation_score"),
            "initial_expansion_score": _number(candidate, "expansion_score", "confluence_score", "momentum_quality_score"),
            "initial_readiness_state": status,
            "configured_profit_target": _number(candidate, "profit_target", "target_price"),
            "configured_stop_level": _number(candidate, "stop_level", "stop_price"),
            "catalyst_evidence": deepcopy(candidate.get("catalyst_evidence", candidate.get("news_evidence"))),
            "recorded_decision_narrative": deepcopy(candidate.get("decision_explanation", candidate.get("decision_narrative"))),
            "measurements": {},
            "observations": [],
            "active": True,
            "removed_before_entry_readiness": False,
            "became_entry_ready": False,
            "entry_ready_timestamp": None,
            "entry_ready_price": None,
            "profit_target_reached": False,
            "stop_level_reached": False,
            "never_became_entry_ready": False,
            "remained_unresolved_at_session_close": False,
            "completed": False,
            "missing_data_events": [],
        }
        records.append(record)
        return record

    @staticmethod
    def _observation(candidate: Mapping[str, Any], stamp: datetime) -> dict:
        return {
            "timestamp": _iso(stamp),
            "price": _number(candidate, "price", "last_price", "close"),
            "high": _number(candidate, "high", "day_high"),
            "low": _number(candidate, "low", "day_low"),
            "volume": _number(candidate, "volume", "day_volume"),
            "relative_volume": _number(candidate, "rvol", "rvol_proxy", "relative_volume"),
            "relative_volume_state": candidate.get("relative_volume_state") or candidate.get("rvol_state"),
            "vwap_position": candidate.get("vwap_relation") or candidate.get("vwap_position"),
            "supertrend_state": candidate.get("supertrend_state") or ("bullish" if candidate.get("supertrend_bullish") else "bearish"),
            "rank": candidate.get("mission_rank"),
            "readiness_state": candidate.get("candidate_status") or candidate.get("status"),
        }

    def _measure(self, record: dict, observation: dict, label: str) -> None:
        initial = record.get("initial_price")
        observations = record["observations"]
        favorable = [item.get("high") or item.get("price") for item in observations]
        adverse = [item.get("low") or item.get("price") for item in observations]
        favorable = [value for value in favorable if value is not None]
        adverse = [value for value in adverse if value is not None]
        price = observation.get("price")
        prior_rank = next((item.get("rank") for item in reversed(observations[:-1]) if item.get("rank") is not None), record.get("initial_rank"))
        current_rank = observation.get("rank")
        movement = "unchanged"
        if current_rank is not None and prior_rank is not None:
            movement = "upgraded" if current_rank < prior_rank else "downgraded" if current_rank > prior_rank else "unchanged"
        record["measurements"][label] = {
            **{key: observation.get(key) for key in ("timestamp", "price", "volume", "relative_volume", "relative_volume_state", "vwap_position", "supertrend_state")},
            "percentage_change": round((price / initial - 1) * 100, 4) if price is not None and initial else None,
            "maximum_favorable_excursion": round((max(favorable) / initial - 1) * 100, 4) if favorable and initial else None,
            "maximum_adverse_excursion": round((min(adverse) / initial - 1) * 100, 4) if adverse and initial else None,
            "walter_rank_change": movement,
        }

    @staticmethod
    def _complete(record: dict, stamp: datetime) -> None:
        """Freeze derived evidence after observation has ended."""
        observations = record.get("observations") or []
        entry = record.get("entry_ready_price")
        eligible = observations
        if record.get("entry_ready_timestamp"):
            ready_at = _time(record["entry_ready_timestamp"])
            eligible = [item for item in observations if _time(item.get("timestamp")) >= ready_at]
        highs = [(item.get("high") or item.get("price"), item) for item in eligible]
        lows = [(item.get("low") or item.get("price"), item) for item in eligible]
        highs = [(value, item) for value, item in highs if value is not None]
        lows = [(value, item) for value, item in lows if value is not None]
        last = eligible[-1] if eligible else (observations[-1] if observations else {})
        close = last.get("price")
        peak = max(highs, key=lambda pair: pair[0]) if highs else None
        trough = min(lows, key=lambda pair: pair[0]) if lows else None
        record["maximum_favorable_excursion"] = round((peak[0] / entry - 1) * 100, 4) if peak and entry else None
        record["maximum_adverse_excursion"] = round((trough[0] / entry - 1) * 100, 4) if trough and entry else None
        record["time_to_entry_ready"] = _minutes(record.get("first_mission_timestamp"), record.get("entry_ready_timestamp"))
        record["time_to_peak"] = _minutes(record.get("entry_ready_timestamp"), peak[1].get("timestamp")) if peak else None
        failure = next((item for item in eligible if record.get("configured_stop_level") is not None and (item.get("low") or item.get("price") or float("inf")) <= record["configured_stop_level"]), None)
        record["time_to_failure"] = _minutes(record.get("entry_ready_timestamp"), failure.get("timestamp")) if failure else None
        record["closing_outcome"] = {
            "price": close,
            "percentage_change": round((close / entry - 1) * 100, 4) if close is not None and entry else None,
            "timestamp": last.get("timestamp") or _iso(stamp),
        }
        record["classification"] = classify_outcome(record)
        actual = record["classification"] in {"Excellent", "Good"}
        record["component_attribution"] = {
            name: {"predicted_success": prediction, "actual_success": actual,
                   "correct": prediction == actual}
            for name, prediction in _component_predictions(record).items()
        }

    def process_scan(
        self, candidates: Iterable[Mapping[str, Any]], *, timestamp: Any = None,
        session_close: bool = False,
    ) -> list[dict]:
        """Consume published ledger snapshots; exceptions are recorded, not raised."""
        stamp = _time(timestamp)
        records = self.all()
        current: set[str] = set()
        try:
            for source in candidates:
                candidate = deepcopy(dict(source))
                identity = self._identity(candidate)
                if not identity:
                    continue
                current.add(identity)
                record = next((item for item in records if item.get("active") and item.get("candidate_identity") == identity), None)
                if record is None:
                    record = self._new_record(candidate, stamp, records)
                observation = self._observation(candidate, stamp)
                if observation["price"] is None:
                    record["missing_data_events"].append({"timestamp": _iso(stamp), "reason": "price unavailable"})
                elif not record["observations"] or record["observations"][-1]["timestamp"] != observation["timestamp"]:
                    record["observations"].append(observation)
                if _ready(candidate) and not record["became_entry_ready"]:
                    record.update(became_entry_ready=True, entry_ready_timestamp=_iso(stamp), entry_ready_price=observation["price"])
                elapsed = (stamp - _time(record["first_mission_timestamp"])).total_seconds() / 60
                for label, minutes in INTERVALS:
                    if elapsed >= minutes and label not in record["measurements"] and observation["price"] is not None:
                        self._measure(record, observation, label)
                if record["became_entry_ready"] and observation["price"] is not None:
                    high = observation.get("high") or observation["price"]
                    low = observation.get("low") or observation["price"]
                    target = _number(candidate, "profit_target", "target_price") or record.get("configured_profit_target")
                    stop = _number(candidate, "stop_level", "stop_price") or record.get("configured_stop_level")
                    if target is not None and high >= target:
                        record["profit_target_reached"] = True
                    if stop is not None and low <= stop:
                        record["stop_level_reached"] = True
            for record in records:
                if record.get("active") and record.get("candidate_identity") not in current:
                    record["active"] = False
                    record["removed_timestamp"] = _iso(stamp)
                    record["removed_before_entry_readiness"] = not record["became_entry_ready"]
                    record["never_became_entry_ready"] = not record["became_entry_ready"]
                    record["completed"] = True
                    self._complete(record, stamp)
            if session_close:
                for record in records:
                    if record.get("session_date") != stamp.date().isoformat() or record.get("completed"):
                        continue
                    if record.get("observations"):
                        self._measure(record, record["observations"][-1], "session_close")
                    record["active"] = False
                    record["never_became_entry_ready"] = not record["became_entry_ready"]
                    record["remained_unresolved_at_session_close"] = bool(record["became_entry_ready"] and not record["profit_target_reached"] and not record["stop_level_reached"])
                    record["completed"] = True
                    self._complete(record, stamp)
        except Exception as exc:  # measurement must never interrupt live scanning
            records.append({"outcome_id": f"missing|{_iso(stamp)}", "completed": True, "missing_data_events": [{"timestamp": _iso(stamp), "reason": str(exc)}]})
        self._write(records)
        return records

    def diagnostics(self) -> dict[str, int]:
        records = self.all()
        return {
            "candidates_being_tracked": sum(bool(item.get("active")) for item in records),
            "completed_outcomes": sum(bool(item.get("completed")) for item in records),
            "unresolved_outcomes": sum(not item.get("completed", False) for item in records),
            "missing_data_events": sum(len(item.get("missing_data_events", [])) for item in records),
        }

    def analytics(self) -> "OutcomeAnalyticsEngine":
        return OutcomeAnalyticsEngine(self.all())


class OutcomeAnalyticsEngine:
    """Pure reporting over copied completed outcomes; never participates in runtime."""

    def __init__(self, records: Sequence[Mapping[str, Any]]):
        self.records = [deepcopy(dict(item)) for item in records if item.get("completed") and item.get("classification")]

    def component_scorecards(self) -> dict[str, dict[str, Any]]:
        cards = {}
        for component in COMPONENTS:
            rows = [(record, (record.get("component_attribution") or {}).get(component)) for record in self.records]
            rows = [(record, result) for record, result in rows if result]
            gains = [self._return(record) for record, _ in rows if (self._return(record) or 0) > 0]
            losses = [self._return(record) for record, _ in rows if (self._return(record) or 0) < 0]
            cards[component] = {
                "observations": len(rows),
                "success_rate": round(100 * sum(bool(result["correct"]) for _, result in rows) / len(rows), 2) if rows else None,
                "false_positives": sum(result["predicted_success"] and not result["actual_success"] for _, result in rows),
                "false_negatives": sum(not result["predicted_success"] and result["actual_success"] for _, result in rows),
                "average_gain": _avg(gains), "average_loss": _avg(losses),
                "average_mfe": _avg(record.get("maximum_favorable_excursion") for record, _ in rows),
                "average_mae": _avg(record.get("maximum_adverse_excursion") for record, _ in rows),
            }
        return cards

    @staticmethod
    def _return(record: Mapping[str, Any]) -> float | None:
        outcome = record.get("closing_outcome") or {}
        return outcome.get("percentage_change") if isinstance(outcome, Mapping) else outcome

    def ranking_validation(self, records: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
        grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for record in records or self.records:
            grouped[str(record.get("session_date"))].append(record)
        comparisons = wins12 = wins23 = lower = 0
        for rows in grouped.values():
            by_rank = {row.get("initial_rank"): row for row in rows if self._return(row) is not None}
            if 1 in by_rank and 2 in by_rank:
                comparisons += 1
                wins12 += self._return(by_rank[1]) > self._return(by_rank[2])
            if 2 in by_rank and 3 in by_rank:
                wins23 += self._return(by_rank[2]) > self._return(by_rank[3])
            if 1 in by_rank:
                lower += any(self._return(row) > self._return(by_rank[1]) for rank, row in by_rank.items() if rank != 1)
        return {"sessions_compared": comparisons, "rank_1_outperformed_rank_2": wins12,
                "rank_2_outperformed_rank_3": wins23, "lower_rank_outperformed_winner": lower,
                "lower_rank_outperformance_rate": round(100 * lower / comparisons, 2) if comparisons else None,
                "accuracy": round(100 * wins12 / comparisons, 2) if comparisons else None}

    def readiness_validation(self, records: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
        cohorts: dict[str, list[float]] = defaultdict(list)
        for record in records or self.records:
            value = self._return(record)
            if value is not None:
                cohorts[_readiness_band(record.get("initial_readiness_state"))].append(value)
        averages = {name: _avg(cohorts.get(name, [])) for name in ("Entry Window", "Early", "Watch")}
        alternatives = [value for name, value in averages.items() if name != "Entry Window" and value is not None]
        superior = averages["Entry Window"] is not None and (not alternatives or averages["Entry Window"] > max(alternatives))
        return {"cohorts": {name: len(cohorts.get(name, [])) for name in averages}, "average_returns": averages,
                "entry_window_superior": superior,
                "accuracy": 100.0 if superior else 0.0 if averages["Entry Window"] is not None else None}

    def daily_summary(self, session_date: str | None = None) -> dict[str, Any]:
        session_date = session_date or max(
            (str(record.get("session_date")) for record in self.records), default=""
        )
        rows = [record for record in self.records if record.get("session_date") == session_date]
        returns = [self._return(row) for row in rows if self._return(row) is not None]
        winners = [value for value in returns if value > 0]
        losers = [value for value in returns if value < 0]
        scores = self.component_scorecards_for(rows)
        return {"session_date": session_date, "total_mission_candidates": len(rows),
                "entry_ready_candidates": sum(bool(row.get("became_entry_ready")) for row in rows),
                "winners": len(winners), "losers": len(losers), "average_gain": _avg(winners), "average_loss": _avg(losers),
                "ranking_accuracy": self.ranking_validation(rows)["accuracy"],
                "readiness_accuracy": self.readiness_validation(rows)["accuracy"],
                "participation_accuracy": scores["Participation Assessment"]["success_rate"],
                "expansion_accuracy": scores["Expansion Assessment"]["success_rate"],
                "catalyst_accuracy": scores["Catalyst Assessment"]["success_rate"]}

    def component_scorecards_for(self, rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
        return OutcomeAnalyticsEngine(rows).component_scorecards()

    def weekly_summary(self, end_date: str | None = None) -> dict[str, Any]:
        dates = sorted({str(row.get("session_date")) for row in self.records})
        if end_date:
            dates = [date for date in dates if date <= end_date]
        dates = dates[-7:]
        daily = [self.daily_summary(date) for date in dates]
        fields = {"Catalyst Assessment": "catalyst_accuracy", "Participation Assessment": "participation_accuracy",
                  "Expansion Assessment": "expansion_accuracy", "Entry Readiness": "readiness_accuracy",
                  "Mission Ranking": "ranking_accuracy"}
        trends = {}
        for name, field in fields.items():
            values = [row[field] for row in daily if row[field] is not None]
            delta = values[-1] - values[0] if len(values) > 1 else 0
            trends[name] = {"performance": "improving" if delta > 2 else "declining" if delta < -2 else "stable", "change": round(delta, 2)}
        for name in ("Conviction",):
            trends[name] = {"performance": "stable", "change": 0} if not daily else self._card_trend(name, dates)
        return {"start_date": dates[0] if dates else None, "end_date": dates[-1] if dates else None, "days": len(dates), "subsystems": trends}

    def _card_trend(self, component: str, dates: list[str]) -> dict[str, Any]:
        values = [OutcomeAnalyticsEngine([r for r in self.records if r.get("session_date") == date]).component_scorecards()[component]["success_rate"] for date in dates]
        values = [value for value in values if value is not None]
        delta = values[-1] - values[0] if len(values) > 1 else 0
        return {"performance": "improving" if delta > 2 else "declining" if delta < -2 else "stable", "change": round(delta, 2)}

    def dashboard(self) -> dict[str, Any]:
        cards = self.component_scorecards()
        distribution = {name: sum(row.get("classification") == name for row in self.records) for name in CLASSIFICATIONS}
        accuracies = [card["success_rate"] for card in cards.values() if card["success_rate"] is not None]
        return {"component_scorecards": cards, "ranking": self.ranking_validation(),
                "readiness": self.readiness_validation(), "rolling_confidence": _avg(accuracies),
                "outcome_distribution": distribution, "weekly": self.weekly_summary()}
