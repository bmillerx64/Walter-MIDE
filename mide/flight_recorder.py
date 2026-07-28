"""Persistent, diagnostic-only decision tracing for Walter scans."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

STAGES = (
    "discovery",
    "snapshot",
    "prefilter",
    "Scanner V2",
    "Participation Gate",
    "Structure Gate",
    "qualified_for_ranking",
    "actionable display",
)


def prefilter_decision(symbol: str, snapshot: dict, settings) -> dict:
    """Explain the existing prefilter rules without changing their behavior."""
    trade = snapshot.get("latestTrade") or {}
    quote = snapshot.get("latestQuote") or {}
    daily = snapshot.get("dailyBar") or {}
    previous = snapshot.get("prevDailyBar") or {}
    price = float(trade.get("p") or daily.get("c") or 0)
    prev_close = float(previous.get("c") or 0)
    volume = float(daily.get("v") or 0)
    pct_change = ((price / prev_close) - 1) * 100 if prev_close else 0
    bid = float(quote.get("bp") or 0)
    ask = float(quote.get("ap") or 0)
    spread = (
        ((ask - bid) / ((ask + bid) / 2) * 100) if bid and ask and ask >= bid else 99
    )
    dollar_volume = price * volume
    thresholds = {
        "min_price": settings.min_price,
        "max_price": settings.max_price,
        "min_pct_change": settings.min_pct_change,
        "min_day_volume": settings.min_day_volume,
        "min_dollar_volume": 50_000,
    }
    measured = {
        "price": price,
        "pct_change": pct_change,
        "volume": volume,
        "dollar_volume": dollar_volume,
        "spread_pct": spread,
    }
    if not settings.min_price <= price <= settings.max_price:
        reason = (
            f"price {price:g} outside [{settings.min_price:g}, {settings.max_price:g}]"
        )
    elif pct_change < settings.min_pct_change and volume < settings.min_day_volume:
        reason = (
            f"pct_change {pct_change:.4g} < {settings.min_pct_change:g} and "
            f"volume {volume:g} < {settings.min_day_volume:g}"
        )
    elif dollar_volume < 50_000:
        reason = f"dollar_volume {dollar_volume:g} < 50000"
    else:
        reason = "passed all prefilter rules"
    return {
        "symbol": symbol,
        "passed": reason == "passed all prefilter rules",
        "reason": reason,
        "measured_values": measured,
        "thresholds": thresholds,
    }


class FlightRecorder:
    """Append complete scans and retrieve the newest trace for a symbol."""

    def __init__(self, path="data/flight_recorder.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record_scan(
        self,
        *,
        seeds,
        discovery_reasons,
        snapshots,
        candidates,
        analyzed,
        records,
        settings,
        scanner_v2=True,
        recent_news_log=None,
        timestamp=None,
    ) -> dict:
        timestamp = timestamp or datetime.now(timezone.utc)
        stamp = timestamp.astimezone(timezone.utc).isoformat()
        scan_id = f"{timestamp.strftime('%Y%m%dT%H%M%S')}-{uuid4().hex[:8]}"
        candidate_symbols = {item.get("symbol") for item in candidates}
        analyzed_by_symbol = {item.get("symbol"): item for item in analyzed}
        records_by_symbol = {item.get("symbol"): item for item in records}
        paths = []
        for symbol in seeds:
            events = []

            def event(stage, passed, reason, measured=None, thresholds=None):
                events.append(
                    {
                        "stage": stage,
                        "passed": bool(passed),
                        "reason": reason,
                        "measured_values": measured or {},
                        "thresholds": thresholds or {},
                        "timestamp": stamp,
                    }
                )

            event(
                "discovery",
                True,
                "; ".join(discovery_reasons.get(symbol, [])) or "discovered",
            )
            snap = snapshots.get(symbol)
            event(
                "snapshot",
                snap is not None,
                "snapshot received" if snap is not None else "snapshot unavailable",
            )
            if snap is not None:
                decision = prefilter_decision(symbol, snap, settings)
                event(
                    "prefilter",
                    decision["passed"],
                    decision["reason"],
                    decision["measured_values"],
                    decision["thresholds"],
                )
            else:
                event("prefilter", False, "not evaluated: snapshot unavailable")
            analyzed_record = analyzed_by_symbol.get(symbol)
            if symbol in candidate_symbols:
                event(
                    "Scanner V2",
                    analyzed_record is not None,
                    (
                        "analysis completed"
                        if analyzed_record is not None
                        else "analysis unavailable: insufficient or missing bar data"
                    ),
                )
            else:
                event("Scanner V2", False, "not evaluated: prefilter failed")
            record = records_by_symbol.get(symbol)
            participation = (record or {}).get("participation_gate") or {}
            structure = (record or {}).get("structure_gate") or {}
            event(
                "Participation Gate",
                participation.get("passed", False),
                (
                    "; ".join(participation.get("failed_reasons", []))
                    if not participation.get("passed")
                    else participation.get("reason")
                )
                or "not evaluated: Scanner V2 analysis unavailable",
                {
                    item.get("condition"): item.get("measured")
                    for item in participation.get("checks", [])
                },
                {
                    item.get("condition"): item.get("threshold")
                    for item in participation.get("checks", [])
                },
            )
            event(
                "Structure Gate",
                structure.get("passed", False),
                (
                    "; ".join(structure.get("failed_reasons", []))
                    if not structure.get("passed")
                    else structure.get("reason")
                )
                or "not evaluated: Scanner V2 analysis unavailable",
                {
                    item.get("condition"): item.get("measured")
                    for item in structure.get("checks", [])
                },
                {
                    item.get("condition"): item.get("threshold")
                    for item in structure.get("checks", [])
                },
            )
            # TODO Walter 2.0 Phase 2: replace this compatibility-stage trace
            # with the three explicit workflow predicates.
            qualified = bool(
                record and record.get("qualified_for_ranking", not scanner_v2)
            )
            rejection = (record or {}).get("rejection_reason")
            event(
                "qualified_for_ranking",
                qualified,
                (
                    "qualified for ranking"
                    if qualified
                    else rejection or "not qualified because an earlier stage failed"
                ),
            )
            displayed = qualified and (record or {}).get("status") not in {
                "PASS",
                "Removed",
            }
            event(
                "actionable display",
                displayed,
                (
                    "shown in actionable display"
                    if displayed
                    else (
                        f"status {(record or {}).get('status')} is hidden from actionable display"
                        if qualified
                        else "not displayed: not qualified for ranking"
                    )
                ),
                {"status": (record or {}).get("status")},
                {"hidden_statuses": ["PASS", "Removed"]},
            )
            reached = next(
                (e["stage"] for e in reversed(events) if e["passed"]), "discovery"
            )
            prefilter = next(e for e in events if e["stage"] == "prefilter")
            trigger = (record or {}).get("trigger_diagnostics") or {}
            evidence = {
                "symbol": symbol,
                "scan_timestamp": stamp,
                "discovery_status": "; ".join(discovery_reasons.get(symbol, []))
                or "discovered",
                "snapshot_prefilter_result": prefilter["passed"],
                "snapshot_prefilter_rejection_reason": (
                    None if prefilter["passed"] else prefilter["reason"]
                ),
                "workflow_state": (record or {}).get("candidate_status")
                or (record or {}).get("status")
                or "Candidate",
                "qualified_for_watch": bool(
                    (record or {}).get("qualified_for_watch", False)
                ),
                "qualified_for_entry": bool(
                    (record or {}).get("qualified_for_entry", False)
                ),
                "qualified_for_alert": bool(
                    (record or {}).get("qualified_for_alert", False)
                ),
                "participation_score": (record or {}).get("participation_score"),
                "participation_surge_score": (record or {}).get(
                    "participation_surge_score"
                ),
                "vpi": (record or {}).get("volume_pace_ratio"),
                "five_minute_vpi_acceleration": (record or {}).get(
                    "acceleration_ratio"
                ),
                "legacy_volume_acceleration": (record or {}).get("volume_acceleration"),
                "dollar_flow_acceleration": (record or {}).get(
                    "dollar_flow_acceleration_5m",
                    (record or {}).get("dollar_flow_acceleration"),
                ),
                "price": (record or {}).get("price"),
                "vwap": (record or {}).get("vwap_value"),
                "vwap_distance": (record or {}).get("vwap_distance_pct"),
                "supertrend_state": (record or {}).get(
                    "supertrend_state",
                    (
                        "bullish"
                        if (record or {}).get("supertrend_bullish")
                        else "bearish" if record else None
                    ),
                ),
                "supertrend_flip_age": (record or {}).get(
                    "supertrend_30s_flip_age_seconds",
                    (record or {}).get(
                        "supertrend_flip_age_seconds",
                        (record or {}).get("supertrend_flip_age"),
                    ),
                ),
                "structure_gate": structure,
                "participation_gate": participation,
                "trigger_result": trigger.get("trigger", (record or {}).get("trigger")),
                "trigger_failed_conditions": [
                    c.get("failed_reason") or c.get("condition")
                    for c in trigger.get("checks", [])
                    if not c.get("passed")
                ],
                "trigger_diagnostics": trigger,
                "opportunity_score": (record or {}).get("opportunity_score"),
                "conviction_score": (record or {}).get(
                    "conviction_v2_score", (record or {}).get("conviction_score")
                ),
                "source_bar_timestamp": (record or {}).get(
                    "source_bar_timestamp",
                    (record or {}).get(
                        "last_bar_timestamp", (record or {}).get("bar_timestamp")
                    ),
                ),
                "source_bar_age": (record or {}).get(
                    "source_bar_age", (record or {}).get("bar_age_seconds")
                ),
                "latest_rejection_or_blocker": (record or {}).get("rejection_reason")
                or next(
                    iter((record or {}).get("entry_blockers_explained") or []), None
                ),
            }
            paths.append(
                {
                    "symbol": symbol,
                    "stage_reached": reached,
                    "events": events,
                    "evidence": evidence,
                }
            )

        funnel = {
            "Sampled": len(seeds),
            "Prefiltered": len(candidate_symbols),
            "Analyzed": len(analyzed_by_symbol),
            "Participation PASS": sum(
                bool((r.get("participation_gate") or {}).get("passed")) for r in records
            ),
            "Structure PASS": sum(
                bool((r.get("structure_gate") or {}).get("passed")) for r in records
            ),
            "Qualified": sum(
                bool(r.get("qualified_for_ranking", not scanner_v2)) for r in records
            ),
            "Displayed": sum(
                bool(r.get("qualified_for_ranking", not scanner_v2))
                and r.get("status") not in {"PASS", "Removed"}
                for r in records
            ),
        }
        scan = {
            "scan_id": scan_id,
            "timestamp": stamp,
            "scanner_version": "V2" if scanner_v2 else "V1",
            "funnel": funnel,
            "symbols": paths,
        }
        if recent_news_log is not None:
            scan["recent_wire_news"] = recent_news_log
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(scan, default=str) + "\n")
        return scan

    def latest_scan(self) -> dict | None:
        if not self.path.exists():
            return None
        for line in reversed(self.path.read_text(errors="ignore").splitlines()):
            try:
                return json.loads(line)
            except (ValueError, TypeError):
                continue
        return None

    def export_bytes(self) -> bytes:
        """Return the untouched recorder file for a browser download."""
        return self.path.read_bytes() if self.path.exists() else b""

    def scans(self) -> list[dict]:
        """Read every valid scan, preserving its on-disk order."""
        if not self.path.exists():
            return []
        scans = []
        for line in self.path.read_text(errors="ignore").splitlines():
            try:
                scans.append(json.loads(line))
            except (ValueError, TypeError):
                continue
        return scans

    def history_for_symbol(self, symbol: str) -> list[dict]:
        """Return this symbol's trace from every scan where it was discovered."""
        symbol = symbol.strip().upper()
        history = []
        for scan in self.scans():
            path = next(
                (
                    item
                    for item in scan.get("symbols", [])
                    if str(item.get("symbol", "")).upper() == symbol
                ),
                None,
            )
            if path:
                history.append(
                    {
                        "scan_id": scan.get("scan_id"),
                        "timestamp": scan.get("timestamp"),
                        "scanner_version": scan.get("scanner_version"),
                        **path,
                    }
                )
        return history

    def latest_for_symbol(self, symbol: str) -> dict | None:
        scan = self.latest_scan()
        symbol = symbol.strip().upper()
        if not scan:
            return None
        path = next(
            (item for item in scan.get("symbols", []) if item.get("symbol") == symbol),
            None,
        )
        return (
            {"scan_id": scan["scan_id"], "timestamp": scan["timestamp"], **path}
            if path
            else None
        )
