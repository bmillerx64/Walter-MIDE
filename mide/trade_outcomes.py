"""User-entered trade outcomes and descriptive alert analytics.

This module is deliberately downstream from the scanner.  It stores feedback and
produces recommendations, but never mutates scanner settings or thresholds.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

OUTCOME_LABELS = ("No Trade", "Winner", "Loser", "Missed Winner", "Bad Alert")


def _number(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _bucket(
    value: Any, boundaries: tuple[tuple[float, str], ...], unknown="Unknown"
) -> str:
    number = _number(value)
    if number is None:
        return unknown
    for ceiling, label in boundaries:
        if number < ceiling:
            return label
    return boundaries[-1][1]


def float_bucket(value: Any) -> str:
    return _bucket(
        value,
        (
            (2, "<2M"),
            (5, "2–5M"),
            (10, "5–10M"),
            (20, "10–20M"),
            (float("inf"), "20M+"),
        ),
    )


def rvol_bucket(value: Any) -> str:
    return _bucket(value, ((2, "<2"), (4, "2–4"), (8, "4–8"), (float("inf"), ">8")))


def price_bucket(value: Any) -> str:
    return _bucket(
        value,
        ((1, "<$1"), (2, "$1–2"), (5, "$2–5"), (10, "$5–10"), (float("inf"), "$10+")),
    )


def time_bucket(value: Any) -> str:
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return "Unknown"
    hour = stamp.hour
    if hour < 9:
        return "Pre-market"
    if hour < 11:
        return "09:00–11:00"
    if hour < 14:
        return "11:00–14:00"
    if hour < 16:
        return "14:00–16:00"
    return "After-hours"


class TradeOutcomeStore:
    """Persist one user-editable feedback record for each alert."""

    def __init__(self, path: str | Path = "data/trade_outcomes.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def all(self) -> list[dict]:
        if not self.path.is_file():
            return []
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value if isinstance(value, list) else []
        except (OSError, ValueError, TypeError):
            return []

    def _write(self, records: list[dict]) -> None:
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(records, indent=2, default=str), encoding="utf-8"
        )
        temporary.replace(self.path)

    def register_alert(self, alert: dict, *, timestamp: str | None = None) -> dict:
        """Register an alert once and retain the evidence used for analytics."""
        stamp = timestamp or str(
            alert.get("scan_timestamp")
            or alert.get("timestamp")
            or datetime.now(timezone.utc).isoformat()
        )
        symbol = str(alert.get("symbol") or "").strip().upper()
        alert_id = str(alert.get("alert_id") or f"{stamp}|{symbol}")
        records = self.all()
        existing = next(
            (item for item in records if item.get("alert_id") == alert_id), None
        )
        if existing:
            return existing
        structure = alert.get("structure") or {}
        record = {
            "alert_id": alert_id,
            "symbol": symbol,
            "alert_time": stamp,
            "entry_price": _number(alert.get("entry_price", alert.get("price"))),
            "exit_price": None,
            "mfe": None,
            "mae": None,
            "pl_pct": None,
            "outcome": None,
            "alert_grade": alert.get("quality_grade")
            or alert.get("grade")
            or "Unknown",
            "float_millions": _number(
                alert.get("float_millions", structure.get("float_millions"))
            ),
            "rvol": _number(alert.get("rvol_proxy", alert.get("rvol"))),
            "setup_type": alert.get("setup_type")
            or alert.get("candidate_status")
            or alert.get("status")
            or "Unknown",
        }
        records.append(record)
        self._write(records)
        return record

    def mark(
        self,
        alert_id: str,
        *,
        outcome: str,
        entry_price: Any = None,
        exit_price: Any = None,
        mfe: Any = None,
        mae: Any = None,
    ) -> dict:
        if outcome not in OUTCOME_LABELS:
            raise ValueError(f"outcome must be one of {', '.join(OUTCOME_LABELS)}")
        records = self.all()
        record = next(
            (item for item in records if item.get("alert_id") == alert_id), None
        )
        if record is None:
            raise KeyError(f"unknown alert: {alert_id}")
        for key, value in (
            ("entry_price", entry_price),
            ("exit_price", exit_price),
            ("mfe", mfe),
            ("mae", mae),
        ):
            parsed = _number(value)
            if parsed is not None:
                record[key] = parsed
        entry, exit_ = _number(record.get("entry_price")), _number(
            record.get("exit_price")
        )
        record["pl_pct"] = (
            round((exit_ / entry - 1) * 100, 4) if entry and exit_ is not None else None
        )
        record["outcome"] = outcome
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write(records)
        return record

    def for_symbol(self, symbol: str) -> list[dict]:
        symbol = symbol.strip().upper()
        return [item for item in self.all() if item.get("symbol") == symbol]

    def analytics(self) -> dict:
        """Return observed win rates; only completed Winner/Loser trades count."""
        completed = [
            item for item in self.all() if item.get("outcome") in {"Winner", "Loser"}
        ]
        dimensions = {
            "alert_grade": lambda item: str(item.get("alert_grade") or "Unknown"),
            "time_of_day": lambda item: time_bucket(item.get("alert_time")),
            "float_bucket": lambda item: float_bucket(item.get("float_millions")),
            "rvol_bucket": lambda item: rvol_bucket(item.get("rvol")),
            "price_bucket": lambda item: price_bucket(item.get("entry_price")),
            "setup_type": lambda item: str(item.get("setup_type") or "Unknown"),
        }
        result = {}
        for name, classifier in dimensions.items():
            groups = defaultdict(list)
            for item in completed:
                groups[classifier(item)].append(item)
            result[name] = [
                {
                    "bucket": bucket,
                    "wins": sum(i["outcome"] == "Winner" for i in items),
                    "trades": len(items),
                    "win_rate": round(
                        100 * sum(i["outcome"] == "Winner" for i in items) / len(items),
                        1,
                    ),
                }
                for bucket, items in sorted(groups.items())
            ]
        return result

    def recommendations(self, minimum_sample: int = 5) -> list[str]:
        """Describe useful observed cohorts without changing any configuration."""
        rows = []
        for dimension, groups in self.analytics().items():
            for group in groups:
                if group["trades"] >= minimum_sample:
                    rows.append(
                        (group["win_rate"], group["trades"], dimension, group["bucket"])
                    )
        rows.sort(reverse=True)
        labels = {
            "alert_grade": "grade",
            "time_of_day": "time",
            "float_bucket": "float",
            "rvol_bucket": "RVOL",
            "price_bucket": "price",
            "setup_type": "setup",
        }
        recommendations = [
            f"Alerts in the {labels[dimension]} {bucket} cohort have produced a {rate:g}% win rate over the last {trades} trades."
            for rate, trades, dimension, bucket in rows
        ]
        cohorts = defaultdict(list)
        for item in self.all():
            if item.get("outcome") in {"Winner", "Loser"}:
                cohorts[
                    (
                        rvol_bucket(item.get("rvol")),
                        float_bucket(item.get("float_millions")),
                    )
                ].append(item)
        for (rvol, float_), items in cohorts.items():
            if len(items) < minimum_sample:
                continue
            rate = round(
                100 * sum(item["outcome"] == "Winner" for item in items) / len(items), 1
            )
            recommendations.append(
                f"Alerts with RVOL {rvol} and float {float_} have produced a "
                f"{rate:g}% win rate over the last {len(items)} trades."
            )
        return recommendations
