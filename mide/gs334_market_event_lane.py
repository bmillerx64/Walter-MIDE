"""GS334: keep extraordinary live movers visible outside the trade funnel.

Walter's ranked candidate pipeline is intentionally selective.  A symbol can be an
important live market event and still fail Participation, Expansion, or another
trade gate.  That is correct for qualification but incomplete for the operator's
situational awareness: a +100% Webull Day Gainer should not disappear from the
Radar merely because it is not a trade candidate.

GS334 therefore creates a separate, presentation-only market-event lane from the
already-fetched Webull native Day Gainers data.  It does not add symbols to the
candidate ledger and does not change discovery membership, gates, scores,
thresholds, ranking, readiness, alerts, orders, or execution.
"""
from __future__ import annotations

from functools import wraps
import html
from typing import Iterable

EXTREME_MOVER_PCT = 75.0
MARKET_EVENT_LIMIT = 3

_LATEST_MARKET_EVENTS: list[dict] = []
_LATEST_ACTIONABLE_SYMBOLS: set[str] = set()


def _number(value, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def market_event_rows(
    native_rows: Iterable[dict] | None,
    *,
    threshold: float = EXTREME_MOVER_PCT,
    limit: int = MARKET_EVENT_LIMIT,
) -> list[dict]:
    """Return extraordinary Webull Day Gainers as attention-only event records."""
    events: list[dict] = []
    for source in native_rows or []:
        symbol = str(source.get("symbol") or "").strip().upper()
        sources = {str(value or "") for value in source.get("sources") or []}
        pct_change = _number(source.get("change_ratio"))
        if not symbol or "day_gainers" not in sources or pct_change is None:
            continue
        if pct_change < float(threshold):
            continue
        ranks = source.get("ranks") or {}
        rank = _number(ranks.get("day_gainers"), default=999.0) or 999.0
        events.append(
            {
                "symbol": symbol,
                "pct_change": round(pct_change, 2),
                "rank": int(rank),
                "price": _number(source.get("price")),
                "volume": _number(source.get("volume")),
                "sources": sorted(sources),
                "attention_only": True,
            }
        )
    events.sort(key=lambda row: (row["rank"], -row["pct_change"], row["symbol"]))
    return events[: max(0, int(limit))]


def visible_market_events(
    events: Iterable[dict] | None,
    actionable_symbols: Iterable[str] | None,
) -> list[dict]:
    """Suppress duplicates already represented by Walter's current trade records."""
    active = {str(symbol or "").strip().upper() for symbol in actionable_symbols or []}
    return [
        dict(event)
        for event in events or []
        if str(event.get("symbol") or "").strip().upper() not in active
    ]


def market_event_markup(
    events: Iterable[dict] | None,
    actionable_symbols: Iterable[str] | None = None,
) -> str:
    """Render one compact operator strip without implying trade qualification."""
    visible = visible_market_events(events, actionable_symbols)
    if not visible:
        return ""

    chips = "".join(
        (
            "<span style='display:inline-block;margin:3px 8px 3px 0;padding:5px 9px;"
            "border:1px solid #f59e0b;border-radius:8px;background:#111827;'>"
            f"<b>{html.escape(str(event['symbol']))}</b> "
            f"<span style='color:#fbbf24'>+{float(event['pct_change']):.1f}%</span> "
            f"<span style='color:#94a3b8'>#{int(event['rank'])} Webull</span></span>"
        )
        for event in visible
    )
    return (
        "<div style='margin:10px 0 14px 0;padding:10px 14px;border:1px solid #92400e;"
        "border-left:4px solid #f59e0b;border-radius:10px;background:#0b111b;'>"
        "<div style='font-weight:800;letter-spacing:.06em;color:#fbbf24'>"
        "⚡ LIVE MARKET EVENTS · ATTENTION ONLY</div>"
        f"<div style='margin-top:5px'>{chips}</div>"
        "<div style='margin-top:4px;color:#94a3b8;font-size:.86rem'>"
        "Extraordinary current movers outside Walter's trade-qualified results. "
        "Open the chart if useful; normal entry gates still apply.</div></div>"
    )


def _in_streamlit_run() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx(suppress_warning=True) is not None
    except Exception:
        return False


def install() -> None:
    """Attach the event lane at data-capture and header-presentation seams."""
    from . import ui
    from .webull_live import LiveWebullProvider

    global _LATEST_MARKET_EVENTS, _LATEST_ACTIONABLE_SYMBOLS

    current_assets = LiveWebullProvider.assets
    if not getattr(current_assets, "_gs334_market_event_capture", False):
        @wraps(current_assets)
        def assets_with_market_events(self):
            global _LATEST_MARKET_EVENTS
            _LATEST_MARKET_EVENTS = []
            assets = current_assets(self)
            native_rows = list((getattr(self, "_native_radar_prices", {}) or {}).values())
            events = market_event_rows(native_rows)
            _LATEST_MARKET_EVENTS = events
            diagnostics = getattr(self, "diagnostics", None)
            if isinstance(diagnostics, dict):
                diagnostics["market_event_lane"] = {
                    "source": "Webull native DAY_GAINERS",
                    "threshold_pct": EXTREME_MOVER_PCT,
                    "attention_only": True,
                    "events": [dict(event) for event in events],
                }
            return assets

        assets_with_market_events._gs334_market_event_capture = True
        assets_with_market_events._gs334_original = current_assets
        LiveWebullProvider.assets = assets_with_market_events

    current_mission = ui.walter_mission_control
    if not getattr(current_mission, "_gs334_market_event_symbols", False):
        @wraps(current_mission)
        def mission_with_current_symbols(records: list[dict]) -> dict:
            global _LATEST_ACTIONABLE_SYMBOLS
            _LATEST_ACTIONABLE_SYMBOLS = {
                str(record.get("symbol") or "").strip().upper()
                for record in records or []
                if str(record.get("symbol") or "").strip()
            }
            return current_mission(records)

        mission_with_current_symbols._gs334_market_event_symbols = True
        mission_with_current_symbols._gs334_original = current_mission
        ui.walter_mission_control = mission_with_current_symbols

    current_header = ui.mission_control_header_markup
    if not getattr(current_header, "_gs334_market_event_lane", False):
        @wraps(current_header)
        def header_with_market_events(*args, **kwargs):
            markup = current_header(*args, **kwargs)
            if not _in_streamlit_run():
                return markup
            return markup + market_event_markup(
                _LATEST_MARKET_EVENTS,
                _LATEST_ACTIONABLE_SYMBOLS,
            )

        header_with_market_events._gs334_market_event_lane = True
        header_with_market_events._gs334_original = current_header
        ui.mission_control_header_markup = header_with_market_events
