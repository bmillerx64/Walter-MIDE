"""Read-only accounting for live Universe Construction.

The helpers in this module deliberately do not choose candidates.  They observe
the values already returned by discovery and describe the existing decisions.
"""
from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from .discovery import is_valid_us_symbol


OPERATIONS = {
    "movers": "GET https://data.alpaca.markets/v1beta1/screener/stocks/movers",
    "most_actives": "GET https://data.alpaca.markets/v1beta1/screener/stocks/most-actives",
    "assets": "GET {paper-api|api}.alpaca.markets/v2/assets",
    "public_symbol_fallback": "GET Nasdaq Trader nasdaqlisted.txt and otherlisted.txt",
}


def _normal(raw):
    return str(raw or "").strip().upper()


class UniverseVerification:
    """Collect source/merge facts while preserving the original return values."""

    def __init__(self, client, *, feed, market_session="unknown", now=None):
        now = now or datetime.now(timezone.utc)
        self.client = client
        self.report = {
            "scan_metadata": {
                "scan_id": str(uuid4()), "timestamp": now.isoformat(),
                "market_session": market_session, "configured_data_feed": feed,
                "provider_names": [], "provider_methods_called": [],
            },
            "sources": [], "merge_accounting": {}, "pre_price_transitions": [],
            "symbols": [], "unexplained_losses": [], "status": "PENDING",
        }
        self._observations = []

    def call(self, source_name, method_name, parameters, call):
        before_warnings = len(getattr(self.client, "warnings", []))
        started = perf_counter()
        error = None
        try:
            value = call()
        except Exception as exc:
            value, error = [], f"{type(exc).__name__}: {exc}"
        elapsed = (perf_counter() - started) * 1000
        objects = list(value or [])
        new_warnings = list(getattr(self.client, "warnings", [])[before_warnings:])
        raw_symbols = [item.get("symbol") if isinstance(item, dict) else item for item in objects]
        normalized = [_normal(item) for item in raw_symbols]
        valid = [item for item in normalized if is_valid_us_symbol(item)]
        duplicates = len(valid) - len(set(valid))
        provider = getattr(self.client, "provider_name", self.client.__class__.__name__)
        source = {
            "source_name": source_name, "provider": provider,
            "provider_method": method_name, "api_endpoint_or_operation": OPERATIONS[method_name],
            "request_parameters": dict(parameters), "pagination_or_batching": "single request",
            "raw_objects_returned": len(objects), "raw_unique_symbols_returned": len(set(valid)),
            "duplicate_symbols_within_source": duplicates,
            "provider_errors": ([error] if error else []) + [
                warning for warning in new_warnings if "unavailable" in warning.lower()
            ],
            "truncation_or_api_limit_warnings": ([
                "requested top=100 is clamped to the Alpaca endpoint maximum of 50"
            ] if method_name == "most_actives" and int(parameters.get("top", 0)) > 50 else []),
            "elapsed_ms": round(elapsed, 3),
        }
        self.report["sources"].append(source)
        metadata = self.report["scan_metadata"]
        if provider not in metadata["provider_names"]:
            metadata["provider_names"].append(provider)
        metadata["provider_methods_called"].append({
            "method": method_name, "operation": OPERATIONS[method_name]
        })
        for raw, symbol in zip(raw_symbols, normalized):
            self._observations.append({"raw": raw, "symbol": symbol, "source": source_name})
        if error:
            raise RuntimeError(error)
        return value

    def finish(self, final_symbols, *, transitions=(), entered_price_gate=None):
        final = set(final_symbols)
        valid_obs = [row for row in self._observations if is_valid_us_symbol(row["symbol"])]
        raw_unique = {row["symbol"] for row in valid_obs}
        invalid = [row for row in self._observations if not is_valid_us_symbol(row["symbol"])]
        sources_by_symbol = {}
        for row in valid_obs:
            sources_by_symbol.setdefault(row["symbol"], set()).add(row["source"])
        added, seen = {}, set()
        for source in [row["source_name"] for row in self.report["sources"]]:
            values = {r["symbol"] for r in valid_obs if r["source"] == source}
            added[source] = len(values - seen)
            seen |= values
        self.report["merge_accounting"] = {
            "total_raw_symbol_observations": len(self._observations),
            "unique_normalized_symbols_before_merge": len(raw_unique),
            "duplicates_removed_during_merge": len(valid_obs) - len(raw_unique),
            "invalid_or_blank_symbols_removed": len(invalid),
            "symbols_added_by_each_source": added,
            "symbols_shared_by_multiple_sources": sorted(s for s, v in sources_by_symbol.items() if len(v) > 1),
            "final_universe_membership": sorted(final), "final_universe_count": len(final),
        }
        self.report["malformed_identifiers"] = [
            {"raw_identifier": row["raw"], "source": row["source"]} for row in invalid
        ]
        documented = set()
        for transition in transitions:
            row = dict(transition)
            grouped = row.get("affected_symbols_grouped_by_reason", {})
            documented |= {symbol for values in grouped.values() for symbol in values}
            self.report["pre_price_transitions"].append(row)
        # Invalid observations have no valid normalized symbol and are accounted
        # separately. Every valid provider symbol must be admitted or transitioned.
        # Universe Construction is non-filtering: documenting a transition does
        # not make removal of a valid provider symbol acceptable.
        unexplained = sorted((raw_unique - final) | (final - raw_unique))
        entered = final if entered_price_gate is None else set(entered_price_gate)
        reason_by_symbol = {
            symbol: reason for transition in self.report["pre_price_transitions"]
            for reason, symbols in transition.get("affected_symbols_grouped_by_reason", {}).items()
            for symbol in symbols
        }
        all_symbols = sorted(raw_unique | final)
        self.report["symbols"] = [{
            "normalized_symbol": symbol,
            "sources": sorted(sources_by_symbol.get(symbol, set())),
            "admitted_to_universe": symbol in final,
            "entered_price_gate": symbol in entered,
            "removal_reason": reason_by_symbol.get(symbol),
        } for symbol in all_symbols]
        self.report["contract_check"] = {
            "raw_unique_symbols": len(raw_unique), "final_universe_membership": len(final),
            "documented_removals_before_price_gate": len((raw_unique - final) & documented),
            "equation_holds": raw_unique == final,
        }
        self.report["unexplained_losses"] = unexplained
        self.report["status"] = "PASS" if not unexplained else "FAIL"
        return self.report
