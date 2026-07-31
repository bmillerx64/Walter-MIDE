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
from typing import Any, Iterable, Mapping


INTERVALS = (("2m", 2), ("5m", 5), ("10m", 10), ("15m", 15), ("30m", 30))


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
    return bool(record.get("qualified_for_entry") or state.replace("_", " ") == "entry ready")


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
