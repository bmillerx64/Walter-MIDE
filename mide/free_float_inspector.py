"""Diagnostic-only inspection of provider free-float fields."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .discovery import is_valid_us_symbol


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
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _containers(payload: dict) -> list[tuple[str, dict]]:
    containers = [("response", payload)]
    for key in ("reference", "results", "ticker"):
        value = payload.get(key)
        if isinstance(value, dict):
            containers.append((key, value))
    return containers


def inspect_free_float(client, symbol: str) -> FreeFloatInspection:
    """Fetch one unmodified snapshot and expose float-related provider fields."""
    ticker = str(symbol or "").strip().upper()
    provider = getattr(client, "provider_name", "Alpaca Market Data")
    empty_fields = {field: None for field in FIELD_ALIASES}
    if not is_valid_us_symbol(ticker):
        return FreeFloatInspection(
            ticker=ticker,
            provider=provider,
            request_succeeded=False,
            returned_fields=empty_fields,
            computed_free_float=None,
            computed_from=None,
            error="Enter a valid U.S. ticker symbol.",
        )

    try:
        payload = client.stock_snapshot(ticker)
        if not isinstance(payload, dict):
            raise ValueError(f"Unexpected response type: {type(payload).__name__}")
    except Exception as exc:
        return FreeFloatInspection(
            ticker=ticker,
            provider=provider,
            request_succeeded=False,
            returned_fields=empty_fields,
            computed_free_float=None,
            computed_from=None,
            error=f"{type(exc).__name__}: {exc}",
        )

    returned = dict(empty_fields)
    found: dict[str, tuple[Any, str]] = {}
    for label, container in _containers(payload):
        for display_name, aliases in FIELD_ALIASES.items():
            for alias in aliases:
                if alias in container and container[alias] is not None:
                    returned[display_name] = container[alias]
                    found[display_name] = (container[alias], f"{label}.{alias}")
                    break

    computed = None
    computed_from = None
    for field in ("floatShares", "freeFloat"):
        if field not in found:
            continue
        value, source = found[field]
        try:
            computed = float(str(value).replace(",", ""))
            computed_from = source
        except (TypeError, ValueError):
            pass
        break

    # This established adapter field explicitly denotes millions of shares.
    for label, container in _containers(payload):
        if computed is None and container.get("float_millions") is not None:
            try:
                computed = float(container["float_millions"]) * 1_000_000
                computed_from = f"{label}.float_millions × 1,000,000"
            except (TypeError, ValueError):
                pass

    return FreeFloatInspection(
        ticker=ticker,
        provider=provider,
        request_succeeded=True,
        returned_fields=returned,
        computed_free_float=computed,
        computed_from=computed_from,
    )
