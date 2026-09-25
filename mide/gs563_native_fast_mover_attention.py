"""GS563: native fast-mover attention and pause-awareness facade.

Live validation on 2026-09-25 exposed a gap between Walter's already-fetched Webull
native radar and the trade-qualified candidate pipeline. RDGT entered the native
five-minute-movers feed but free-float reference data failed closed before scanner
analysis; it later expanded sharply and was suspended in Webull Desktop. MSGY likewise
continued into an extreme move and later displayed as suspended.

GS563 does not bypass any trading gate. It:
- promotes already-fetched top-five-minute-mover evidence into the existing
  presentation-only market-event lane using GS377's established 15% / $5 context;
- gives newly-current native market events a bounded LOOK NOW audio cue even when
  qualification/reference data prevents a normal candidate alert;
- keeps ordinary live operator consideration/audio behind Walter's existing
  time-of-day liquidity evidence, while exceptional native market events remain a
  separate attention-only lane;
- emits only a probabilistic CHECK TRADING STATUS cue when a current hot mover's
  analyzed source bar becomes stale; it never manufactures confirmed halt truth;
- preserves explicit halt/suspension fields if the official snapshot supplies them.

No new provider request, score, rank, float decision, qualification, readiness,
anti-chase, execution, or order authority is added.
"""

from __future__ import annotations

from datetime import datetime


_LIQUIDITY_REASON_OWNER = "_walter_gs563_operator_liquidity_reason_owner"
_LIQUIDITY_VISIBLE_OWNER = "_walter_gs563_operator_liquidity_visible_owner"


def _scan_time(record: dict) -> datetime | None:
    value = record.get("scan_time")
    if isinstance(value, datetime):
        return value
    if value:
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            pass
    return None


def operator_liquidity_diagnostics(record: dict) -> dict:
    """Use Walter's existing session thresholds to decide operator consideration."""
    from . import scanner_v2

    # Apply only to records that have completed Scanner V2's canonical
    # session-volume enrichment. Synthetic/UI-only records and pre-scanner
    # awareness rows must preserve their established visibility semantics.
    # This keeps GS564 at the operator boundary instead of silently redefining
    # historical test fixtures or GS466 extreme-awareness continuity.
    canonical_session = record.get("volume_session_diagnostics")
    if not isinstance(canonical_session, dict):
        return {"applicable": False, "passed": True, "reason": ""}

    session = scanner_v2.session_volume_diagnostics(record, _scan_time(record))
    pace = record.get("volume_pace_diagnostics")
    if not isinstance(pace, dict):
        pace = scanner_v2.volume_pace_diagnostics(record)

    def number(*keys):
        for key in keys:
            value = record.get(key)
            if value in (None, ""):
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return None

    volume = number("volume") or 0.0
    price = number("price") or 0.0
    dollar_volume = number("dollar_volume")
    if dollar_volume is None and volume > 0 and price > 0:
        dollar_volume = volume * price
    dollar_volume = dollar_volume or 0.0
    explicit_rvol = number("rvol_proxy", "relative_volume_10d")

    activity_passed = bool(
        session.get("volume_passed")
        or pace.get("passed")
        or (
            explicit_rvol is not None
            and explicit_rvol >= float(session["expected_minimum_rvol"])
        )
    )
    minimum_dollar = float(session["expected_minimum_dollar_volume"]) * 0.5
    dollar_passed = bool(dollar_volume >= minimum_dollar or pace.get("passed"))
    passed = bool(activity_passed and dollar_passed)
    reason = ""
    if not passed:
        rvol_text = (
            f"{explicit_rvol:.2f} vs {float(session['expected_minimum_rvol']):.2f}"
            if explicit_rvol is not None
            else "unavailable"
        )
        reason = (
            "operator liquidity below time-of-day consideration floor: "
            f"volume {volume:,.0f} vs {float(session['expected_minimum_volume']):,.0f}, "
            f"dollar volume {dollar_volume:,.0f} vs {minimum_dollar:,.0f}, "
            f"RVOL {rvol_text}"
        )
    return {
        "applicable": True,
        "passed": passed,
        "reason": reason,
        "session": session.get("current_session"),
        "actual_volume": volume,
        "expected_minimum_volume": session.get("expected_minimum_volume"),
        "actual_dollar_volume": dollar_volume,
        "expected_minimum_dollar_volume": minimum_dollar,
        "actual_rvol": explicit_rvol,
        "expected_minimum_rvol": session.get("expected_minimum_rvol"),
        "volume_pace_passed": bool(pace.get("passed")),
    }


def install_operator_liquidity_floor() -> None:
    """Keep thin names out of the live consideration/audio surface."""
    from . import gs373_operator_visibility_freshness as freshness

    current_reason = freshness.operator_visibility_reason
    if not getattr(current_reason, _LIQUIDITY_REASON_OWNER, False):
        original_reason = current_reason

        def operator_visibility_reason(record: dict) -> str:
            reason = original_reason(record)
            if reason:
                return reason
            diagnostic = operator_liquidity_diagnostics(record)
            if diagnostic.get("applicable") and not diagnostic.get("passed"):
                return str(diagnostic.get("reason") or "operator liquidity below floor")
            return ""

        for name, value in getattr(original_reason, "__dict__", {}).items():
            if name.startswith("_gs") and not hasattr(operator_visibility_reason, name):
                setattr(operator_visibility_reason, name, value)
        operator_visibility_reason._gs563_operator_liquidity_floor = True
        operator_visibility_reason._gs563_original = original_reason
        setattr(operator_visibility_reason, _LIQUIDITY_REASON_OWNER, True)
        freshness.operator_visibility_reason = operator_visibility_reason

    current_visible = freshness.operator_visible
    if not getattr(current_visible, _LIQUIDITY_VISIBLE_OWNER, False):
        def operator_visible(record: dict) -> bool:
            return not freshness.operator_visibility_reason(record)

        for name, value in getattr(current_visible, "__dict__", {}).items():
            if name.startswith("_gs") and not hasattr(operator_visible, name):
                setattr(operator_visible, name, value)
        operator_visible._gs563_operator_liquidity_floor = True
        operator_visible._gs563_original = current_visible
        setattr(operator_visible, _LIQUIDITY_VISIBLE_OWNER, True)
        freshness.operator_visible = operator_visible


def install() -> None:
    from .authorities import market_evidence, presentation_audio

    market_evidence.activate_native_fast_mover_attention()
    install_operator_liquidity_floor()
    presentation_audio.install_native_market_event_audio()


__all__ = ["install"]
