"""GS475: make Webull snapshot price truth session-aware in live Walter.

Sep. 17 premarket validation exposed a data-truth split rather than a scanner-threshold
problem. Webull native discovery was seeing the real premarket leaders and current
session volume, while Walter's REST snapshot normalization was still consuming the
regular-session ``price`` field. Examples in the Flight Recorder included AEMD,
DAIC, CTNT, TURB and DTSS: discovery/volume were current, but snapshot price and
percent-change could reflect the prior regular session until the opening bell.

Webull's snapshot API can return separate extended-hours and overnight fields when
explicitly requested. GS475 therefore does two narrowly-scoped things at the SDK
snapshot boundary:

* always request extended-hours + overnight snapshot fields for Walter's live snapshot
  call; and
* during PRE/ATH use ``ext_price`` (and its trade time) when present, during OVN use
  ``ovn_price``, and during RTH preserve the ordinary ``price`` field.

No threshold, qualification, participation, expansion, ranking, alert, readiness,
anti-chase, execution, order, or 30s/1m/3m crossover rule changes here. This is only
source-price truth before those existing rules run. The wrapper is deliberately on
``WebullSDKClient.stock_snapshot`` so a warm runtime with an already-constructed
provider self-heals on the next snapshot call; a hard provider rebuild is not required
for the code path itself.
"""
from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo


OWNER_ATTR = "_walter_gs475_premarket_snapshot_truth_owner"
EASTERN = ZoneInfo("America/New_York")


def _number(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _now_eastern() -> datetime:
    return datetime.now(EASTERN)


def _session_price_fields(now_et: datetime) -> tuple[str, str, str] | None:
    """Return (price field, trade-time field, session label) outside RTH."""
    if now_et.tzinfo is None:
        now_et = now_et.replace(tzinfo=EASTERN)
    else:
        now_et = now_et.astimezone(EASTERN)
    clock = now_et.time().replace(tzinfo=None)
    if time(4, 0) <= clock < time(9, 30):
        return ("ext_price", "ext_trade_time", "PRE")
    if time(9, 30) <= clock < time(16, 0):
        return None
    if time(16, 0) <= clock < time(20, 0):
        return ("ext_price", "ext_trade_time", "ATH")
    return ("ovn_price", "ovn_trade_time", "OVN")


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
    """Overlay only the session-appropriate price field in a plain SDK payload."""
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


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Hard-bind session-aware snapshot truth at the final live SDK boundary."""
    from . import webull_sdk

    current = webull_sdk.WebullSDKClient.stock_snapshot
    if getattr(current, OWNER_ATTR, False):
        return

    def stock_snapshot_with_session_truth(self, symbols, *, extended_hours: bool = False):
        # Walter always needs the optional PRE/ATH/OVN fields available so the same
        # scanner can operate truthfully before, during and after RTH. During RTH the
        # overlay intentionally leaves the ordinary ``price`` untouched.
        payload = current(self, symbols, extended_hours=True)
        now_et = _now_eastern()
        result = apply_snapshot_session_truth(payload, now_et=now_et)
        self.last_snapshot_extended_requested = True
        fields = _session_price_fields(now_et)
        self.last_snapshot_session_price_field = fields[0] if fields else "price"
        return result

    _inherit(stock_snapshot_with_session_truth, current)
    stock_snapshot_with_session_truth._gs475_premarket_snapshot_truth = True
    stock_snapshot_with_session_truth._gs475_original = current
    setattr(stock_snapshot_with_session_truth, OWNER_ATTR, True)
    webull_sdk.WebullSDKClient.stock_snapshot = stock_snapshot_with_session_truth
