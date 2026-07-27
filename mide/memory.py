from __future__ import annotations
from pathlib import Path
import json
from datetime import datetime, timezone


class MemoryStore:
    def __init__(self, path="data/candidate_history.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def latest_by_symbol(self, limit_lines=5000):
        if not self.path.exists():
            return {}
        lines = self.path.read_text(errors="ignore").splitlines()[-limit_lines:]
        latest = {}
        for line in lines:
            try:
                item = json.loads(line)
                latest[item["symbol"]] = item
            except Exception:
                continue
        return latest

    def export_bytes(self) -> bytes:
        """Return the untouched history file for a browser download."""
        return self.path.read_bytes() if self.path.exists() else b""

    def history_for_symbol(self, symbol: str) -> list[dict]:
        """Return every valid persisted candidate record for ``symbol``."""
        symbol = symbol.strip().upper()
        if not symbol or not self.path.exists():
            return []
        matches = []
        for line in self.path.read_text(errors="ignore").splitlines():
            try:
                item = json.loads(line)
            except (ValueError, TypeError):
                continue
            if str(item.get("symbol", "")).upper() == symbol:
                matches.append(item)
        return matches

    def append(self, records):
        if not records:
            return
        with self.path.open("a", encoding="utf-8") as handle:
            for item in records:
                handle.write(json.dumps(item, default=str) + "\n")

    def enrich_velocity(self, records, previous=None):
        """Add prior-score velocity fields using an optional preloaded history map.

        The live scan path also passes the same ``previous`` snapshot into
        Scanner V2, so the explicit ``enrich_velocity(records, previous=None)``
        signature keeps V1/V2 enrichment based on a single consistent prior
        state while preserving the no-argument Scanner V1 API.
        """
        previous = previous if previous is not None else self.latest_by_symbol()
        output = []
        for item in records:
            prior = previous.get(item["symbol"], {})
            score_key = (
                "current_momentum"
                if "current_momentum" in item
                else "opportunity_score"
            )
            old = float(
                prior.get(score_key, prior.get("opportunity_score", item[score_key]))
            )
            item = dict(item)
            item["previous_score"] = round(old, 1)
            item["velocity"] = round(item[score_key] - old, 1)
            item["status_changed"] = bool(
                prior and prior.get("status") != item["status"]
            )
            output.append(item)
        return output
