"""GS464: restore session-aware VWAP parity to the live Webull chart.

Fresh live evidence on 2026-09-16 exposed a material GS391 parity reversal. SNYR was
trading near 0.1554 while Webull visibly showed VWAP near 0.1427. Walter nevertheless
used the all-day 04:00 ET cumulative VWAP near 0.1861 and classified SNYR 16.4% below
VWAP. The same Flight Recorder scan already computed RTH-only VWAP at 0.143289,
matching the operator's Webull chart almost exactly.

GS391's 2026-09-08 evidence had justified an all-day 04:00 ET anchor. Today's direct
chart/recorder comparison shows that policy no longer matches the live chart being
used for decisions. GS464 therefore restores the original session-aware contract:

* before 09:30 ET, primary VWAP is cumulative from 04:00 ET;
* once a 09:30 ET-or-later bar exists, primary VWAP resets to 09:30 ET;
* the old all-day extended VWAP remains available as a diagnostic only;
* every existing 30s/1m/3m/5m/10m/15m consumer continues to read the one installed
  ``gs378.primary_vwap_context`` authority, so the correction stays coherent;
* no provider request, threshold, qualification, readiness, execution, or order rule
  is added by this module.
"""
from __future__ import annotations

from functools import wraps
from typing import Any

import pandas as pd

from . import gs378_live_vwap_st_crossover as gs378
from .indicators import session_vwap

SESSION_POLICY = "SESSION_AWARE_04:00_PREMARKET_09:30_RTH"
PREMARKET_POLICY = "PREMARKET_04:00_ET"
RTH_POLICY = "RTH_09:30_ET"
_OWNER_ATTR = "_walter_gs464_session_aware_vwap_owner"
_APPLY_OWNER_ATTR = "_walter_gs464_session_aware_vwap_apply_owner"
_PARITY_OWNER_ATTR = "_walter_gs464_session_aware_vwap_parity_owner"


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None


def _last_vwap(frame: pd.DataFrame) -> float | None:
    if frame is None or frame.empty:
        return None
    series = session_vwap(frame)
    return _finite(series.iloc[-1]) if len(series) else None


def session_aware_primary_vwap_context(frame: pd.DataFrame | None) -> dict:
    """Use 04:00 ET premarket, then reset primary VWAP at the 09:30 ET open."""
    day = gs378._eastern_day(frame)
    if day.empty:
        return {
            "day": day,
            "series": pd.Series(dtype=float),
            "value": None,
            "anchor_mode": "UNAVAILABLE",
            "anchor_time": None,
            "premarket_value": None,
            "rth_value": None,
            "extended_value": None,
            "session_policy": SESSION_POLICY,
        }

    premarket_start, regular_start = gs378._session_boundaries(day)
    latest = day.index[-1]

    premarket = day[(day.index >= premarket_start) & (day.index < regular_start)].copy()
    rth = day[day.index >= regular_start].copy()
    extended = day[day.index >= premarket_start].copy()

    premarket_value = _last_vwap(premarket)
    rth_value = _last_vwap(rth)
    extended_value = _last_vwap(extended)

    if latest >= regular_start and not rth.empty:
        anchored = rth
        anchor = regular_start
        mode = RTH_POLICY
    else:
        anchored = day[day.index >= premarket_start].copy()
        anchor = premarket_start
        mode = PREMARKET_POLICY

    if anchored.empty:
        anchored = day.copy()
        anchor = day.index[0]
        mode = "FALLBACK_FIRST_AVAILABLE_BAR"

    primary = session_vwap(anchored)
    value = _finite(primary.iloc[-1]) if len(primary) else None
    return {
        "day": day,
        "series": primary,
        "value": value,
        "anchor_mode": mode,
        "anchor_time": anchor,
        "premarket_value": premarket_value,
        "rth_value": rth_value,
        "extended_value": extended_value,
        "session_policy": SESSION_POLICY,
    }


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def _install_primary_authority() -> None:
    current = gs378.primary_vwap_context
    if getattr(current, _OWNER_ATTR, False):
        return
    # Preserve the installed GS391/legacy provenance markers so wrapper-integrity
    # diagnostics continue to describe the complete chain even though GS464 now owns
    # the final decision policy.
    _inherit(session_aware_primary_vwap_context, current)
    session_aware_primary_vwap_context._gs464_session_aware_vwap_parity = True
    session_aware_primary_vwap_context._gs464_original = current
    setattr(session_aware_primary_vwap_context, _OWNER_ATTR, True)
    gs378.primary_vwap_context = session_aware_primary_vwap_context


def _install_record_diagnostics() -> None:
    current = gs378.apply_live_vwap_truth
    if getattr(current, _APPLY_OWNER_ATTR, False):
        return

    @wraps(current)
    def apply_session_aware_truth(records, current_session_raw, current_session_30s_raw, client):
        updated = current(records, current_session_raw, current_session_30s_raw, client)
        observed = 0
        for record in updated or []:
            mode = str(record.get("vwap_anchor_mode") or "")
            if mode not in {PREMARKET_POLICY, RTH_POLICY, "FALLBACK_FIRST_AVAILABLE_BAR"}:
                continue
            observed += 1
            record["vwap_primary_session_policy"] = SESSION_POLICY
            record["vwap_bar_timeframe_source"] = (
                f"{getattr(client, 'provider_name', 'market data provider')} 1Min bars; "
                "primary VWAP 04:00 ET premarket / 09:30 ET regular-session reset"
            )

            # GS391 still computes both diagnostic values locally. Preserve them and
            # explicitly label the all-day value diagnostic-only after the RTH reset.
            record["extended_vwap_role"] = "diagnostic_only_after_09:30"

        diagnostics = getattr(client, "diagnostics", None)
        if isinstance(diagnostics, dict):
            diagnostics["gs464_session_aware_vwap_parity"] = {
                "primary_vwap_policy": SESSION_POLICY,
                "premarket_anchor": PREMARKET_POLICY,
                "rth_anchor": RTH_POLICY,
                "records_observed": observed,
                "extended_vwap_role": "diagnostic_only_after_09:30",
                "additional_market_data_requests": 0,
                "trading_thresholds_changed": False,
            }
        return updated

    _inherit(apply_session_aware_truth, current)
    apply_session_aware_truth._gs464_session_aware_vwap_parity = True
    apply_session_aware_truth._gs464_original = current
    setattr(apply_session_aware_truth, _APPLY_OWNER_ATTR, True)
    gs378.apply_live_vwap_truth = apply_session_aware_truth


def _install_recorder_policy_label() -> None:
    """Make future Flight Recorder parity blocks name the decision policy correctly."""
    from . import gs391_webull_vwap_st_parity as gs391

    current = gs391._build_scan_parity
    if getattr(current, _PARITY_OWNER_ATTR, False):
        return

    @wraps(current)
    def build_scan_parity(records) -> dict:
        payload = dict(current(records) or {})
        payload["legacy_gs391_observation_policy"] = gs391.PRIMARY_POLICY
        payload["primary_vwap_policy"] = SESSION_POLICY
        for item in payload.get("symbols") or []:
            mode = item.get("vwap_anchor_mode")
            item["decision_vwap_policy"] = mode
            parity = item.get("parity")
            if isinstance(parity, dict):
                parity["decision_vwap_policy"] = mode
                parity["legacy_observation_policy"] = gs391.PRIMARY_POLICY
        return payload

    _inherit(build_scan_parity, current)
    build_scan_parity._gs464_session_aware_vwap_parity = True
    build_scan_parity._gs464_original = current
    setattr(build_scan_parity, _PARITY_OWNER_ATTR, True)
    gs391._build_scan_parity = build_scan_parity


def install() -> None:
    """Install one session-aware VWAP authority plus explicit parity diagnostics."""
    _install_primary_authority()
    _install_record_diagnostics()
    _install_recorder_policy_label()
