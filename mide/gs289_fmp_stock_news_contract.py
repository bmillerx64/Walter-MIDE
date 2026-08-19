"""GS289: explicit FMP Stock News entitlement contract.

This is intentionally diagnostic/configuration hardening only. Trading decisions,
scoring, thresholds, qualification, alerts, execution, and evidence semantics are
unchanged.
"""

from __future__ import annotations


def install() -> None:
    from .news_provider import FMPNewsProvider

    # Make the provider entitlement an explicit, inspectable contract instead of
    # an implicit implementation detail. GS285's bounded fetch already schedules
    # only news/stock; this constant lets diagnostics/tests prove that boundary.
    FMPNewsProvider.ENTITLED_ENDPOINTS = ("news/stock",)
