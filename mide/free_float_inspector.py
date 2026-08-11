"""Diagnostic-only inspection of provider free-float fields."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .discovery import is_valid_us_symbol
from .free_float import FreeFloatProvider, YahooFinanceFloatProvider
from .webull_live import LiveWebullProvider


FIELD_ALIASES = {
    "sharesOutstanding": ("sharesOutstanding", "shares_outstanding"),
    "floatShares": ("floatShares", "float_shares", "shares_float"),
    "freeFloat": ("freeFloat", "free_float"),
    "marketCap": ("marketCap", "market_cap"),
}


@dataclass(frozen=True)
class FreeFloatInspection:
    ticker: str
    provider: str
    request_succeeded: bool
    returned_fields: dict[str, Any]
    computed_free_float: float | None
    computed_from: str | None
    source: str | None = None
    cache_status: str | None = None
    cache_bypassed: bool = False
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_snapshot_float(snapshot: dict) -> float | None:
    """Normalize all established snapshot float fields conservatively."""
    reference = snapshot.get("reference") or {}
    values = []
    for key in ("float_shares", "shares_float", "free_float"):
        raw = snapshot.get(key)
        if raw is None and isinstance(reference, dict):
            raw = reference.get(key)
        if raw is not None:
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if value > 0:
                values.append(value)
    raw_millions = snapshot.get("float_millions")
    if raw_millions is None and isinstance(reference, dict):
        raw_millions = reference.get("float_millions")
    if raw_millions is not None:
        try:
            value = float(raw_millions) * 1_000_000
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            values.append(value)
    return max(values) if values else None


def _webull_enrich_free_float(self, snapshots: dict[str, dict], symbols) -> dict[str, dict]:
    """Refresh every Live Webull candidate's float and fail closed.

    A populated FMP/cache value must not suppress the live refresh: stale small
    values can otherwise pass the 3.5M squeeze gate after capital-structure
    changes. Conflicting evidence uses the larger value conservatively.
    """
    wanted = []
    existing = {}
    normalized = 0
    for symbol in dict.fromkeys(str(s or "").strip().upper() for s in symbols if s):
        snapshot = snapshots.get(symbol)
        if not isinstance(snapshot, dict):
            continue
        shares = _normalize_snapshot_float(snapshot)
        if shares is not None:
            existing[symbol] = shares
            normalized += 1
        wanted.append(symbol)

    values = {}
    errors = {}
    if wanted:
        provider = YahooFinanceFloatProvider(timeout=5, max_workers=24)
        values, errors = provider.lookup_many(wanted)

    resolved = 0
    failed_closed = 0
    conflicts = 0
    for symbol in wanted:
        snapshot = snapshots.get(symbol)
        if not isinstance(snapshot, dict):
            continue
        prior = existing.get(symbol)
        refreshed = values.get(symbol)
        try:
            refreshed = float(refreshed) if refreshed is not None else None
        except (TypeError, ValueError):
            refreshed = None
        if refreshed is not None and refreshed > 0:
            chosen = max(prior or 0, refreshed)
            if prior is not None and abs(prior - refreshed) > 1:
                conflicts += 1
            snapshot["float_shares"] = chosen
            snapshot["shares_float"] = chosen
            snapshot["free_float"] = chosen
            snapshot["free_float_source"] = (
                "conservative max of existing evidence and Yahoo Finance "
                "defaultKeyStatistics.floatShares.raw"
            )
            resolved += 1
        elif prior is not None:
            snapshot["float_shares"] = prior
            snapshot["shares_float"] = prior
            snapshot["free_float"] = prior
            snapshot.setdefault("free_float_source", "normalized existing provider float")
            resolved += 1
        else:
            snapshot["float_shares"] = float("inf")
            snapshot["shares_float"] = float("inf")
            snapshot["free_float"] = float("inf")
            snapshot["free_float_source"] = "unresolved live float; fail closed"
            failed_closed += 1

    self.diagnostics["free_float_fallback_requested"] = len(wanted)
    self.diagnostics["free_float_fallback_resolved"] = resolved
    self.diagnostics["free_float_snapshot_normalized"] = normalized
    self.diagnostics["free_float_fallback_failed"] = len(errors)
    self.diagnostics["free_float_fail_closed"] = failed_closed
    self.diagnostics["free_float_provider_conflicts"] = conflicts
    if errors:
        sample = "; ".join(f"{k}: {v}" for k, v in list(errors.items())[:3])
        self.warnings.append(
            f"Free-float refresh unresolved for {len(errors)}/{len(wanted)} symbols"
            + (f" ({sample})" if sample else "")
        )
    return snapshots


if not hasattr(LiveWebullProvider, "enrich_free_float"):
    LiveWebullProvider.enrich_free_float = _webull_enrich_free_float


def inspect_free_float(provider: FreeFloatProvider, symbol: str,
                       fallback_provider: FreeFloatProvider | None = None) -> FreeFloatInspection:
    """Inspect cache-first FMP resolution and an optional Yahoo fallback."""
    ticker = str(symbol or "").strip().upper()
    provider_name = getattr(provider, "provider_name", type(provider).__name__)
    empty_fields = {field: None for field in FIELD_ALIASES}
    if not is_valid_us_symbol(ticker):
        return FreeFloatInspection(ticker, provider_name, False, empty_fields, None, None,
                                   error="Enter a valid U.S. ticker symbol.")
    source = None
    cache_status = None
    primary_error = None
    requests_before = int(getattr(provider, "requests_made", 0))
    try:
        values, errors = provider.lookup_many([ticker])
        if ticker in errors:
            raise RuntimeError(errors[ticker])
        computed = values.get(ticker)
        if computed is not None:
            computed = float(computed)
    except Exception as exc:
        computed = None
        primary_error = f"{type(exc).__name__}: {exc}"
    requests_after = int(getattr(provider, "requests_made", requests_before))
    if computed is not None:
        source = "FMP" if requests_after > requests_before else "Cache"
        cache_status = ("Cache miss; FMP requested live data (cache was not bypassed)."
                        if source == "FMP" else "Cache hit; no live FMP request was made.")
    elif fallback_provider is not None:
        try:
            fallback_values, fallback_errors = fallback_provider.lookup_many([ticker])
            if ticker in fallback_errors:
                raise RuntimeError(fallback_errors[ticker])
            computed = fallback_values.get(ticker)
            if computed is not None:
                computed = float(computed)
                source = "Yahoo fallback"
                cache_status = "FMP cache miss; Yahoo fallback used after FMP did not resolve the symbol."
        except Exception as exc:
            fallback_error = f"{type(exc).__name__}: {exc}"
            primary_error = (f"{primary_error}; Yahoo fallback: {fallback_error}"
                             if primary_error else f"Yahoo fallback: {fallback_error}")
    if computed is None and primary_error:
        return FreeFloatInspection(ticker, provider_name, False, empty_fields, None, None,
                                   source=source, cache_status=cache_status, error=primary_error)
    returned = dict(empty_fields)
    returned["floatShares"] = computed
    resolved_provider = (getattr(fallback_provider, "provider_name", type(fallback_provider).__name__)
                         if source == "Yahoo fallback" else provider_name)
    computed_from = f"{resolved_provider}.lookup_many" if computed is not None else None
    return FreeFloatInspection(ticker, provider_name, True, returned, computed, computed_from,
                               source=source, cache_status=cache_status)
