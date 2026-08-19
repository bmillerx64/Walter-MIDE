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


def _webull_enrich_free_float(
    self,
    snapshots: dict[str, dict],
    symbols,
    *,
    max_free_float: float = 50_000_000,
) -> dict[str, dict]:
    """Resolve free float without letting a provider outage zero Walter's universe.

    Existing provider/cache evidence remains preferred. Yahoo is a secondary
    resolver and freshness check. Individual unresolved symbols still fail closed,
    but a cohort-wide secondary-provider outage is treated as degraded evidence,
    not proof that every stock has excessive float. This prevents a transient
    fundamentals outage from turning a healthy live Webull scan into 20+ false
    terminal rejections at the Free-Float Gate.
    """
    threshold = max(0.0, float(max_free_float))
    wanted: list[str] = []
    existing: dict[str, float] = {}
    lookup_symbols: list[str] = []
    normalized = 0

    for symbol in dict.fromkeys(str(s or "").strip().upper() for s in symbols if s):
        snapshot = snapshots.get(symbol)
        if not isinstance(snapshot, dict):
            continue
        wanted.append(symbol)
        shares = _normalize_snapshot_float(snapshot)
        if shares is None:
            lookup_symbols.append(symbol)
            continue
        existing[symbol] = shares
        normalized += 1
        if shares <= threshold:
            lookup_symbols.append(symbol)

    values: dict[str, float] = {}
    errors: dict[str, str] = {}
    if lookup_symbols:
        provider = YahooFinanceFloatProvider(
            timeout=5,
            max_workers=min(8, len(lookup_symbols)),
        )
        values, errors = provider.lookup_many(lookup_symbols)

    resolved_lookup_count = sum(1 for symbol in lookup_symbols if symbol in values)
    resolution_rate = (
        resolved_lookup_count / len(lookup_symbols) if lookup_symbols else 1.0
    )
    # A single unresolved ticker can be bad symbol evidence. A broad cohort with
    # almost no resolutions is provider evidence. Do not convert provider failure
    # into a fabricated +infinity float for every symbol.
    provider_outage = len(lookup_symbols) >= 5 and resolution_rate < 0.20

    resolved = 0
    failed_closed = 0
    conflicts = 0
    unresolved_primary = 0
    refresh_failed = 0
    degraded_unverified = 0

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

        if prior is None:
            if refreshed is not None and refreshed > 0:
                snapshot["float_shares"] = refreshed
                snapshot["shares_float"] = refreshed
                snapshot["free_float"] = refreshed
                snapshot["free_float_source"] = (
                    "Yahoo Finance defaultKeyStatistics.floatShares.raw secondary resolution"
                )
                snapshot["free_float_verified"] = True
                snapshot["free_float_verification_status"] = "verified-secondary-source"
                resolved += 1
                continue

            unresolved_primary += 1
            if provider_outage:
                # Leave float absent. Walter's production float decision treats
                # unavailable evidence as unverified instead of pretending the
                # company has infinite float. The safety/audit layer can then show
                # the provider degradation without erasing the market universe.
                snapshot.pop("float_shares", None)
                snapshot.pop("shares_float", None)
                snapshot.pop("free_float", None)
                snapshot["free_float_source"] = "secondary float provider outage; unresolved"
                snapshot["free_float_verified"] = False
                snapshot["free_float_verification_status"] = "provider-outage-unverified"
                degraded_unverified += 1
                continue

            snapshot["float_shares"] = float("inf")
            snapshot["shares_float"] = float("inf")
            snapshot["free_float"] = float("inf")
            snapshot["free_float_source"] = "primary and secondary float unresolved; fail closed"
            snapshot["free_float_verified"] = False
            snapshot["free_float_verification_status"] = "unavailable-reject"
            failed_closed += 1
            continue

        if prior > threshold:
            snapshot["float_shares"] = prior
            snapshot["shares_float"] = prior
            snapshot["free_float"] = prior
            snapshot.setdefault("free_float_source", "normalized existing provider float")
            snapshot["free_float_verified"] = True
            snapshot["free_float_verification_status"] = "verified-above-limit"
            resolved += 1
            continue

        if refreshed is not None and refreshed > 0:
            chosen = max(prior, refreshed)
            if abs(prior - refreshed) > 1:
                conflicts += 1
            snapshot["float_shares"] = chosen
            snapshot["shares_float"] = chosen
            snapshot["free_float"] = chosen
            snapshot["free_float_source"] = (
                "conservative max of existing evidence and Yahoo Finance "
                "defaultKeyStatistics.floatShares.raw"
            )
            snapshot["free_float_verified"] = True
            snapshot["free_float_verification_status"] = "verified-live-refresh"
            resolved += 1
        elif provider_outage:
            # Preserve known primary evidence during a systemic refresh outage.
            # The actual float ceiling still applies to that value downstream.
            snapshot["float_shares"] = prior
            snapshot["shares_float"] = prior
            snapshot["free_float"] = prior
            snapshot["free_float_source"] = "existing float retained; secondary provider outage"
            snapshot["free_float_verified"] = False
            snapshot["free_float_verification_status"] = "provider-outage-primary-retained"
            degraded_unverified += 1
            refresh_failed += 1
        else:
            snapshot["float_shares"] = float("inf")
            snapshot["shares_float"] = float("inf")
            snapshot["free_float"] = float("inf")
            snapshot["free_float_source"] = "low-float live refresh unresolved; fail closed"
            snapshot["free_float_verified"] = False
            snapshot["free_float_verification_status"] = "refresh-unavailable-reject"
            failed_closed += 1
            refresh_failed += 1

    self.diagnostics["free_float_fallback_requested"] = len(lookup_symbols)
    self.diagnostics["free_float_fallback_resolved"] = resolved_lookup_count
    self.diagnostics["free_float_snapshot_normalized"] = normalized
    self.diagnostics["free_float_fallback_failed"] = len(errors)
    self.diagnostics["free_float_fail_closed"] = failed_closed
    self.diagnostics["free_float_unresolved_primary"] = unresolved_primary
    self.diagnostics["free_float_refresh_failed"] = refresh_failed
    self.diagnostics["free_float_provider_conflicts"] = conflicts
    self.diagnostics["free_float_refresh_ceiling"] = threshold
    self.diagnostics["free_float_provider_outage"] = provider_outage
    self.diagnostics["free_float_provider_resolution_rate"] = round(resolution_rate, 4)
    self.diagnostics["free_float_degraded_unverified"] = degraded_unverified
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
