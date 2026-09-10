"""GS416: prevent bare common-stock suffix letters from failing Validity.

Sep. 10 live evidence showed Webull correctly discovering SNYR from DAY_GAINERS
and ABSOLUTE_VOLUME, with a usable snapshot and passing price prefilter, but the
authoritative Validity Gate rejected it as an unsupported security.  The cause was
an optional-separator fallback regex that treated every symbol ending in W, R, or
U as a warrant/right/unit even when the letter was simply part of the ordinary
stock ticker (for example SNYR or ATER).

This module changes only that last-mile symbol-shape heuristic.  Explicit provider
security type, ETF policy, OTC status, inactive status, legal/operational
tradability, and explicit dot/hyphen derivative suffixes remain authoritative.
No discovery breadth, price/float threshold, participation, expansion, ranking,
VWAP, trigger, entry, alert, execution, or order rule changes.
"""
from __future__ import annotations

import re

_EXPLICIT_DERIVATIVE_SUFFIX = re.compile(r"(?:\.|-)[WRU]$")


def supported_security(record: dict, *, include_etfs: bool) -> bool:
    """Return the existing Validity security decision without bare-letter false positives."""
    asset_type = str(record.get("asset_type") or record.get("type") or "").lower()
    symbol = str(record.get("symbol") or "").strip().upper()
    return not (
        asset_type in {"warrant", "right", "unit"}
        or (asset_type in {"etf", "fund"} and not include_etfs)
        or bool(_EXPLICIT_DERIVATIVE_SUFFIX.search(symbol))
        or str(record.get("exchange") or "").upper() == "OTC"
        or str(record.get("asset_status") or "active").lower() != "active"
    )


def install() -> None:
    """Patch only WalterArchitectureV1's Validity security-shape fallback."""
    from .architecture import Decision, WalterArchitectureV1

    current = WalterArchitectureV1._validity
    if getattr(current, "_gs416_validity_symbol_suffix", False):
        return

    def validity_without_bare_suffix_false_positive(self, candidates: list[dict]):
        result = {}
        for item in candidates:
            symbol = self._symbol(item)
            valid_data = bool(item.get("data_usable", True))
            legal = bool(item.get("legally_tradable", item.get("tradable", True)))
            operational = bool(item.get("operationally_tradable", True))
            security_ok = supported_security(
                item, include_etfs=bool(self.policy.include_etfs)
            )
            passed = valid_data and legal and operational and security_ok
            failures = [
                name
                for ok, name in (
                    (valid_data, "unusable data"),
                    (legal, "legally non-tradable"),
                    (operational, "operationally non-tradable"),
                    (security_ok, "unsupported security type or status"),
                )
                if not ok
            ]
            result[symbol] = Decision(
                passed,
                "Validity",
                "Valid security" if passed else "; ".join(failures),
            )
        return result

    validity_without_bare_suffix_false_positive._gs416_validity_symbol_suffix = True
    validity_without_bare_suffix_false_positive._gs416_original = current
    WalterArchitectureV1._validity = validity_without_bare_suffix_false_positive
