"""GS292: make candidate re-evaluation continuity explicit and auditable.

This layer observes the authoritative architecture ledger after each completed scan.
It does not admit stale candidates, alter stage decisions, change thresholds, rank,
alert, or execute. Its purpose is to distinguish 'seen and re-evaluated' from
'seen previously but absent from this refresh' before GS293 adds urgency semantics.
"""
from __future__ import annotations


def install() -> None:
    from .architecture import WalterArchitectureV1

    if getattr(WalterArchitectureV1, "_gs292_installed", False):
        return

    original_run = WalterArchitectureV1.run

    def run(self):
        results = original_run(self)

        # WalterArchitectureV1.for_runtime() is intentionally a thin dispatch
        # shell and returns from __init__ before ledger/clock fields are created.
        # The live scanner already owns its own state in that mode, so GS292 must
        # be a transparent no-op there rather than assuming architecture-ledger
        # attributes exist. This preserves the production dispatch contract and
        # keeps continuity telemetry scoped to completed ledger-backed scans.
        ledger = getattr(self, "candidate_ledger", None)
        records = getattr(self, "_ledger", None)
        if ledger is None or records is None:
            return results

        scan = ledger.scan_number
        timestamp = self._timestamp()
        for record in records.values():
            current = record.get("discovery_last_seen_scan") == scan
            history = record.setdefault("reevaluation_history", [])
            prior = history[-1] if history else None
            prior_evaluated_scan = record.get("last_reevaluated_scan")

            if current:
                gap = 0 if prior_evaluated_scan is None else max(0, scan - prior_evaluated_scan - 1)
                record["last_reevaluated_scan"] = scan
                record["last_reevaluated_at"] = timestamp
                record["reevaluation_gap_scans"] = gap
                record["reevaluation_status"] = "REEVALUATED"
                record["consecutive_reevaluations"] = (
                    int(record.get("consecutive_reevaluations") or 0) + 1
                    if gap == 0 else 1
                )
                event = {
                    "scan": scan,
                    "timestamp": timestamp,
                    "status": "REEVALUATED",
                    "gap_scans": gap,
                    "terminal_stage": record.get("terminal_stage"),
                    "terminal_outcome": record.get("terminal_outcome"),
                    "conviction": record.get("conviction"),
                    "conviction_change": record.get("conviction_change"),
                    "conviction_trend": record.get("conviction_trend"),
                }
            else:
                record["reevaluation_status"] = "NOT_IN_CURRENT_REFRESH"
                record["reevaluation_gap_scans"] = (
                    scan - prior_evaluated_scan if prior_evaluated_scan is not None else None
                )
                record["consecutive_reevaluations"] = 0
                event = {
                    "scan": scan,
                    "timestamp": timestamp,
                    "status": "NOT_IN_CURRENT_REFRESH",
                    "gap_scans": record["reevaluation_gap_scans"],
                    "terminal_stage": record.get("terminal_stage"),
                    "terminal_outcome": record.get("terminal_outcome"),
                    "conviction": record.get("conviction"),
                    "conviction_change": record.get("conviction_change"),
                    "conviction_trend": record.get("conviction_trend"),
                }

            # One deterministic continuity event per symbol per completed scan.
            if not prior or prior.get("scan") != scan:
                history.append(event)
        return results

    WalterArchitectureV1.run = run
    WalterArchitectureV1._gs292_installed = True
