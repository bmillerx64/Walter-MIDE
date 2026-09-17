"""GS475/GS476: keep Webull snapshot price truth session-aware and entitlement-safe.

Sep. 17 premarket validation exposed a data-truth split rather than a scanner-threshold
problem. Webull native discovery was seeing the real premarket leaders and current
session volume, while Walter's REST snapshot normalization could still consume the
prior regular-session ``price`` field.

GS475 initially solved that by always requesting both extended-hours and overnight
snapshot fields. Live RTH validation immediately exposed the flaw: Webull treats the
overnight flag as a separately entitled NIGHT TRADING STOCK QUOTES product, so an
account without that entitlement receives HTTP 403 MARKET_DATA_NOT_SUBSCRIBED and the
entire live scan stops.

GS476 narrows the transport request to the evidence Walter actually needs:
- PRE (04:00-09:30 ET) and ATH (16:00-20:00 ET) request only
  ``extend_hour_required=True`` and may overlay ``ext_price``;
- RTH uses the ordinary snapshot request with no optional-session flags;
- overnight never requests the separately entitled night feed and falls back to the
  ordinary snapshot contract rather than breaking Walter;
- warm runtimes that still retain the old GS475 wrapper are explicitly unwrapped and
  rebound, so the correction takes effect without requiring a provider rebuild.

No threshold, qualification, participation, expansion, ranking, alert, readiness,
anti-chase, execution, order, or 30s/1m/3m crossover rule changes here. This is only
source-price truth and transport entitlement safety before those existing rules run.
"""
from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo


LEGACY_OWNER_ATTR = "_walter_gs475_premarket_snapshot_truth_owner"
OWNER_ATTR = "_walter_gs476_night_entitlement_safe_owner"
EASTERN = ZoneInfo("America/New_York")


def _number(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _now_eastern() -> datetime:
    return datetime.now(EASTERN)


def _session_price_fields(now_et: datetime) -> tuple[str, str, str] | None:
    """Return the entitled extended-hours price source, if one should be requested."""
    if now_et.tzinfo is None:
        now_et = now_et.replace(tzinfo=EASTERN)
    else:
        now_et = now_et.astimezone(EASTERN)
    clock = now_et.time().replace(tzinfo=None)
    if time(4, 0) <= clock < time(9, 30):
        return ("ext_price", "ext_trade_time", "PRE")
    if time(16, 0) <= clock < time(20, 0):
        return ("ext_price", "ext_trade_time", "ATH")
    return None


def _overlay_snapshot_row(row: dict, now_et: datetime) -> dict:
    fields = _session_price_fields(now_et)
    if fields is None:
        return row
    price_field, trade_time_field, session = fields
    session_price = _number(row.get(price_field))
    if session_price is None or session_price <= 0:
        return row
    updated = dict(row)
    updated["_walter_regular_session_price"] = row.get("price")
    updated["price"] = row.get(price_field)
    session_trade_time = row.get(trade_time_field)
    if session_trade_time not in (None, ""):
        updated["last_trade_time"] = session_trade_time
    updated["_walter_snapshot_price_source"] = price_field
    updated["_walter_snapshot_session"] = session
    return updated


def apply_snapshot_session_truth(payload, *, now_et: datetime | None = None):
    """Overlay only the entitled session-appropriate price field in an SDK payload."""
    now_et = now_et or _now_eastern()
    if isinstance(payload, list):
        return [apply_snapshot_session_truth(item, now_et=now_et) for item in payload]
    if isinstance(payload, tuple):
        return tuple(apply_snapshot_session_truth(item, now_et=now_et) for item in payload)
    if not isinstance(payload, dict):
        return payload

    updated = {
        key: apply_snapshot_session_truth(value, now_et=now_et)
        for key, value in payload.items()
    }
    symbol = updated.get("symbol") or updated.get("ticker") or updated.get("ticker_symbol")
    if symbol:
        return _overlay_snapshot_row(updated, now_et)
    return updated


def _extended_snapshot_without_overnight(client, symbols):
    """Request PRE/ATH fields without touching Webull's separately entitled night feed."""
    from . import webull_sdk

    symbols = list(symbols)
    if len(symbols) > webull_sdk.MAX_SNAPSHOT_SYMBOLS:
        raise ValueError("Webull snapshot requests are limited to 100 symbols")
    method = client._operation(("get_snapshot", "get_stock_snapshot"))
    response = method(
        symbols=",".join(symbols),
        category="US_STOCK",
        extend_hour_required=True,
    )
    client._capture_first_snapshot_response(response)
    return webull_sdk._plain(response)


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Hard-bind entitlement-safe session-aware snapshot truth at the live SDK boundary."""
    from . import webull_sdk

    current = webull_sdk.WebullSDKClient.stock_snapshot
    if getattr(current, OWNER_ATTR, False):
        return

    # A warm Streamlit runtime may still own GS475's old always-extended wrapper. Do
    # not stack on top of it: recover the callable it captured before GS475 so RTH and
    # overnight can truly return to the plain snapshot request.
    base = getattr(current, "_gs475_original", current)

    def stock_snapshot_with_session_truth(self, symbols, *, extended_hours: bool = False):
        now_et = _now_eastern()
        fields = _session_price_fields(now_et)
        request_extended = fields is not None

        if request_extended:
            payload = _extended_snapshot_without_overnight(self, symbols)
        else:
            payload = base(self, symbols, extended_hours=False)

        result = apply_snapshot_session_truth(payload, now_et=now_et)
        self.last_snapshot_extended_requested = request_extended
        self.last_snapshot_overnight_requested = False
        self.last_snapshot_session_price_field = fields[0] if fields else "price"
        return result

    _inherit(stock_snapshot_with_session_truth, current)
    stock_snapshot_with_session_truth._gs475_premarket_snapshot_truth = True
    stock_snapshot_with_session_truth._gs476_night_entitlement_safe = True
    stock_snapshot_with_session_truth._gs475_original = base
    setattr(stock_snapshot_with_session_truth, OWNER_ATTR, True)
    webull_sdk.WebullSDKClient.stock_snapshot = stock_snapshot_with_session_truth
