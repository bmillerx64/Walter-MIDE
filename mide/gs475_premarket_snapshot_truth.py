"""GS475/GS476: warm-deploy-safe Market Evidence facade for snapshot price truth.

Market Evidence owns session-aware Webull snapshot source-price truth and entitlement-
safe PRE/ATH transport. This historical module retains the session clock and constants
because live tests and warm-runtime compatibility intentionally patch that exact clock
seam before installation.

Authority contract: WebullSDKClient.stock_snapshot = stock_snapshot_with_session_truth
Entitled PRE/ATH transport uses extend_hour_required=True and ext_price.
The separately entitled overnight snapshot flag is deliberately never requested.

No scanner threshold, qualification, participation, expansion, ranking, alert,
readiness, execution, order, or 30s/1m/3m crossover rule changes.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


LEGACY_OWNER_ATTR = "_walter_gs475_premarket_snapshot_truth_owner"
OWNER_ATTR = "_walter_gs476_night_entitlement_safe_owner"
EASTERN = ZoneInfo("America/New_York")


def _market():
    from mide.authorities import market_evidence

    return market_evidence


def _now_eastern() -> datetime:
    return datetime.now(EASTERN)


def _number(value):
    current = getattr(
        _market(),
        "snapshot_truth_number",
        None,
    )
    if not callable(current):
        try:
            return (
                float(value)
                if value is not None
                else None
            )
        except (TypeError, ValueError):
            return None
    return current(value)


def _session_price_fields(now_et: datetime):
    current = getattr(
        _market(),
        "snapshot_session_price_fields",
        None,
    )
    if not callable(current):
        return None
    return current(now_et)


def _overlay_snapshot_row(
    row: dict,
    now_et: datetime,
) -> dict:
    current = getattr(
        _market(),
        "overlay_snapshot_session_price",
        None,
    )
    if not callable(current):
        return row
    return current(row, now_et)


def apply_snapshot_session_truth(
    payload,
    *,
    now_et: datetime | None = None,
):
    current = getattr(
        _market(),
        "apply_snapshot_session_truth",
        None,
    )
    if not callable(current):
        return payload
    return current(
        payload,
        now_et=now_et,
    )


def _extended_snapshot_without_overnight(
    client,
    symbols,
):
    current = getattr(
        _market(),
        "extended_snapshot_without_overnight",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Market Evidence generation does not yet expose GS475/476"
        )
    return current(client, symbols)


def install() -> None:
    current = getattr(
        _market(),
        "install_snapshot_session_truth",
        None,
    )
    if callable(current):
        current()


def __getattr__(name: str):
    try:
        return getattr(_market(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "LEGACY_OWNER_ATTR",
    "OWNER_ATTR",
    "EASTERN",
    "apply_snapshot_session_truth",
    "install",
]
