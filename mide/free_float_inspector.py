"""Diagnostic-only inspection of provider free-float fields."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .discovery import is_valid_us_symbol
from .free_float import FreeFloatProvider


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


def inspect_free_float(provider: FreeFloatProvider, symbol: str) -> FreeFloatInspection:
    """Look up one ticker through the same provider contract used by enrichment."""
    ticker = str(symbol or "").strip().upper()
    provider_name = getattr(provider, "provider_name", type(provider).__name__)
    empty_fields = {field: None for field in FIELD_ALIASES}
    if not is_valid_us_symbol(ticker):
        return FreeFloatInspection(
            ticker=ticker,
            provider=provider_name,
            request_succeeded=False,
            returned_fields=empty_fields,
            computed_free_float=None,
            computed_from=None,
            error="Enter a valid U.S. ticker symbol.",
        )

    try:
        values, errors = provider.lookup_many([ticker])
        if ticker in errors:
            raise RuntimeError(errors[ticker])
        computed = values.get(ticker)
        if computed is not None:
            computed = float(computed)
    except Exception as exc:
        return FreeFloatInspection(
            ticker=ticker,
            provider=provider_name,
            request_succeeded=False,
            returned_fields=empty_fields,
            computed_free_float=None,
            computed_from=None,
            error=f"{type(exc).__name__}: {exc}",
        )

    returned = dict(empty_fields)
    returned["floatShares"] = computed
    computed_from = f"{provider_name}.lookup_many" if computed is not None else None

    return FreeFloatInspection(
        ticker=ticker,
        provider=provider_name,
        request_succeeded=True,
        returned_fields=returned,
        computed_free_float=computed,
        computed_from=computed_from,
    )
