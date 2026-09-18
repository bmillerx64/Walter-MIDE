"""GS503: interpret catalyst economics relative to current company scale.

GS479/480 already extract stated dollars, duration, event categories and story facts.
GS502 improves how quickly a breaking article can reach Walter. The remaining semantic
gap is relative scale: a $100M contract means something very different for a $20M
company than for a $20B company.

Webull's already-fetched native radar rows expose a market_value/market_cap reference.
GS503 carries that existing field through the snapshot/prefilter path and compares it
with the already-extracted catalyst economics. No new provider request is made.

For multi-year contracts Walter reports both total stated value / current market cap
and a simple straight-line annualized value / market cap. That annualized figure is
context only; it is not revenue recognition, profit, valuation, closing probability,
or a price target.

The result is operator context only. It never changes catalyst_score, discovery
eligibility, market-data truth, participation, expansion, Mission Ranking, readiness,
anti-chase, alerts, execution or orders.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
from typing import Any


AUTHORITY = "CATALYST_RELATIVE_SCALE_CONTEXT_ONLY"
_SNAPSHOT_OWNER = "_walter_gs503_scale_snapshot_owner"
_PREFILTER_OWNER = "_walter_gs503_scale_prefilter_owner"
_ANALYZE_OWNER = "_walter_gs503_scale_analyze_owner"
_WHY_OWNER = "_walter_gs503_scale_why_owner"


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _money(value: float | None) -> str | None:
    if value is None:
        return None
    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.2g}T"
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2g}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.3g}M"
    if value >= 1_000:
        return f"${value / 1_000:.3g}K"
    return f"${value:,.0f}"


def _ratio_text(value: float | None) -> str | None:
    if value is None:
        return None
    if value >= 10:
        return f"{value:.0f}x"
    if value >= 1:
        return f"{value:.1f}x"
    return f"{value * 100:.0f}%"


def _scale_band(ratio: float | None) -> str:
    if ratio is None:
        return "NOT_EVALUATED_NO_MARKET_CAP"
    if ratio >= 1.0:
        return "COMPANY_SCALE_OR_LARGER"
    if ratio >= 0.25:
        return "MAJOR_RELATIVE_SCALE"
    if ratio >= 0.05:
        return "MATERIAL_RELATIVE_SCALE"
    return "LIMITED_RELATIVE_SCALE"


def _quantity_values(story: dict, role: str) -> list[float]:
    values = []
    for item in story.get("quantities") or []:
        if str(item.get("role") or "") != role:
            continue
        value = _number(item.get("normalized_value"))
        if value is not None:
            values.append(value)
    return values


def _market_cap_reference(record: dict, candidate: dict | None = None) -> tuple[float | None, str | None]:
    sources = [record, candidate or {}]
    for source in sources:
        for key in ("market_cap_reference", "market_cap", "market_value"):
            value = _number(source.get(key))
            if value is not None:
                label = (
                    source.get("market_cap_source")
                    or source.get("market_value_source")
                    or ("Webull native radar market_value" if key == "market_cap_reference" else key)
                )
                return value, str(label)
    return None, None


def company_scale_context(record: dict, candidate: dict | None = None) -> dict:
    """Return factual catalyst/company relative-scale context without trade authority."""
    story = deepcopy(record.get("catalyst_story") or {})
    magnitude = deepcopy(record.get("catalyst_magnitude") or {})

    if not magnitude and record.get("headline"):
        from .gs479_headline_catalyst_magnitude import headline_magnitude_context
        magnitude = headline_magnitude_context(str(record.get("headline") or ""))

    market_cap, market_cap_source = _market_cap_reference(record, candidate)

    deal_values = _quantity_values(story, "DEAL_OR_BACKLOG")
    revenue_values = _quantity_values(story, "REVENUE")
    investment_values = _quantity_values(story, "INVESTMENT_OR_FUNDING")
    dilution_values = _quantity_values(story, "DILUTION_OR_FINANCING")
    headline_amount = _number(magnitude.get("largest_stated_dollar_amount"))

    risk_categories = list(story.get("risk_categories") or [])
    positive_categories = list(story.get("positive_attention_categories") or [])
    risk_event = bool(risk_categories)

    amount = None
    amount_role = None
    if risk_event and dilution_values:
        amount, amount_role = max(dilution_values), "DILUTION_OR_FINANCING"
    elif deal_values:
        amount, amount_role = max(deal_values), "DEAL_OR_BACKLOG"
    elif investment_values:
        amount, amount_role = max(investment_values), "INVESTMENT_OR_FUNDING"
    elif revenue_values:
        amount, amount_role = max(revenue_values), "REVENUE"
    elif headline_amount is not None and (
        bool(magnitude.get("contractual_language")) or positive_categories
    ):
        amount, amount_role = headline_amount, "HEADLINE_STATED_AMOUNT"

    duration = _number(magnitude.get("stated_duration_years"))
    total_ratio = (
        amount / market_cap
        if amount is not None and market_cap is not None
        else None
    )

    annualized_amount = None
    annualized_ratio = None
    if (
        amount is not None
        and duration is not None
        and duration >= 1
        and amount_role in {"DEAL_OR_BACKLOG", "HEADLINE_STATED_AMOUNT"}
        and bool(magnitude.get("contractual_language"))
    ):
        annualized_amount = amount / duration
        if market_cap is not None:
            annualized_ratio = annualized_amount / market_cap

    comparison_ratio = annualized_ratio if annualized_ratio is not None else total_ratio
    band = _scale_band(comparison_ratio)

    if risk_event or amount_role == "DILUTION_OR_FINANCING":
        event_direction = "RISK_CONTEXT"
    elif positive_categories or amount_role:
        event_direction = "POSITIVE_ATTENTION_CONTEXT"
    else:
        event_direction = "UNCLASSIFIED_CONTEXT"

    summary_parts = []
    if amount is not None and market_cap is not None:
        prefix = "Risk scale" if event_direction == "RISK_CONTEXT" else "Company scale"
        total_text = _ratio_text(total_ratio)
        summary_parts.append(
            f"{prefix}: {_money(amount)} stated = {total_text} current {_money(market_cap)} market cap"
        )
        if annualized_amount is not None and annualized_ratio is not None:
            summary_parts.append(
                f"~{_money(annualized_amount)}/yr = {_ratio_text(annualized_ratio)} market cap over {duration:g}y"
            )

    return {
        "authority": AUTHORITY,
        "market_cap_reference": market_cap,
        "market_cap_source": market_cap_source,
        "market_cap_available": market_cap is not None,
        "event_amount": amount,
        "event_amount_role": amount_role,
        "stated_duration_years": duration,
        "total_value_to_market_cap_ratio": round(total_ratio, 4) if total_ratio is not None else None,
        "annualized_contract_value": annualized_amount,
        "annualized_value_to_market_cap_ratio": (
            round(annualized_ratio, 4) if annualized_ratio is not None else None
        ),
        "comparison_ratio_used": round(comparison_ratio, 4) if comparison_ratio is not None else None,
        "relative_scale_band": band,
        "event_direction": event_direction,
        "summary": " · ".join(summary_parts),
        "band_contract": {
            "limited_relative_scale": "<5% of market cap",
            "material_relative_scale": "5%-<25% of market cap",
            "major_relative_scale": "25%-<100% of market cap",
            "company_scale_or_larger": ">=100% of market cap",
            "multi_year_contract_basis": "straight-line annualized stated value when duration is disclosed",
        },
        "revenue_recognition_inferred": False,
        "profitability_inferred": False,
        "valuation_impact_inferred": False,
        "closing_probability_inferred": False,
        "price_target_inferred": False,
        "trading_authority_changed": False,
    }


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def _install_snapshot_reference() -> None:
    from .webull_live import LiveWebullProvider

    current = LiveWebullProvider.snapshots
    if getattr(current, _SNAPSHOT_OWNER, False):
        return

    @wraps(current)
    def snapshots_with_market_cap(self, symbols):
        snapshots = current(self, symbols)
        native = getattr(self, "_native_radar_prices", {}) or {}
        output = {}
        for symbol, snapshot in (snapshots or {}).items():
            row = dict(snapshot)
            radar = native.get(str(symbol).strip().upper()) or {}
            market_cap = _number(radar.get("market_value") or radar.get("market_cap"))
            if market_cap is not None:
                row["market_cap_reference"] = market_cap
                row["market_cap_source"] = "Webull native radar market_value"
            output[symbol] = row
        return output

    _inherit(snapshots_with_market_cap, current)
    setattr(snapshots_with_market_cap, _SNAPSHOT_OWNER, True)
    snapshots_with_market_cap._gs503_catalyst_company_scale = True
    snapshots_with_market_cap._gs503_original = current
    LiveWebullProvider.snapshots = snapshots_with_market_cap


def _install_prefilter_reference() -> None:
    from . import discovery

    current = discovery.prefilter_snapshots
    if getattr(current, _PREFILTER_OWNER, False):
        return

    @wraps(current)
    def prefilter_with_market_cap(snapshots, settings):
        selected = current(snapshots, settings)
        output = []
        for candidate in selected or []:
            row = dict(candidate)
            source = (snapshots or {}).get(str(row.get("symbol") or "").upper()) or {}
            market_cap = _number(
                source.get("market_cap_reference")
                or source.get("market_cap")
                or source.get("market_value")
            )
            if market_cap is not None:
                row["market_cap_reference"] = market_cap
                row["market_cap_source"] = str(
                    source.get("market_cap_source")
                    or "Webull native radar market_value"
                )
            output.append(row)
        return output

    _inherit(prefilter_with_market_cap, current)
    setattr(prefilter_with_market_cap, _PREFILTER_OWNER, True)
    prefilter_with_market_cap._gs503_catalyst_company_scale = True
    prefilter_with_market_cap._gs503_original = current
    discovery.prefilter_snapshots = prefilter_with_market_cap


def _install_analyzed_context() -> None:
    from . import discovery

    current = discovery.analyze_candidates
    if getattr(current, _ANALYZE_OWNER, False):
        return

    @wraps(current)
    def analyze_with_company_scale(client, candidates, news_index, discovery_reasons):
        records = current(client, candidates, news_index, discovery_reasons)
        by_symbol = {
            str(item.get("symbol") or "").strip().upper(): item
            for item in candidates or []
        }
        output = []
        for record in records or []:
            symbol = str(record.get("symbol") or "").strip().upper()
            candidate = by_symbol.get(symbol) or {}
            row = dict(record)
            market_cap, source = _market_cap_reference(row, candidate)
            if market_cap is not None:
                row["market_cap_reference"] = market_cap
                row["market_cap_source"] = source
            row["catalyst_company_scale"] = company_scale_context(row, candidate)
            output.append(row)

        diagnostics = getattr(client, "diagnostics", None)
        if isinstance(diagnostics, dict):
            contexts = [item.get("catalyst_company_scale") or {} for item in output]
            diagnostics["gs503_catalyst_company_scale"] = {
                "authority": AUTHORITY,
                "records_evaluated": len(output),
                "records_with_market_cap": sum(bool(item.get("market_cap_available")) for item in contexts),
                "records_with_economic_amount": sum(bool(item.get("event_amount")) for item in contexts),
                "company_scale_or_larger": sum(
                    item.get("relative_scale_band") == "COMPANY_SCALE_OR_LARGER"
                    for item in contexts
                ),
                "additional_provider_requests": 0,
                "ranking_changed": False,
                "trading_authority_changed": False,
            }
        return output

    _inherit(analyze_with_company_scale, current)
    setattr(analyze_with_company_scale, _ANALYZE_OWNER, True)
    analyze_with_company_scale._gs503_catalyst_company_scale = True
    analyze_with_company_scale._gs503_original = current
    discovery.analyze_candidates = analyze_with_company_scale


def _install_operator_presentation() -> None:
    from . import ui

    current = ui._why_sections
    if getattr(current, _WHY_OWNER, False):
        return

    @wraps(current)
    def why_sections_with_company_scale(record):
        sections = dict(current(record))
        detail = record.get("catalyst_company_scale") or {}
        summary = str(detail.get("summary") or "").strip()
        if summary:
            existing = str(sections.get("Catalyst") or "").strip()
            if summary not in existing:
                sections["Catalyst"] = f"{existing} · {summary}" if existing else summary
        return sections

    _inherit(why_sections_with_company_scale, current)
    setattr(why_sections_with_company_scale, _WHY_OWNER, True)
    why_sections_with_company_scale._gs503_catalyst_company_scale = True
    why_sections_with_company_scale._gs503_original = current
    ui._why_sections = why_sections_with_company_scale


def install() -> None:
    """Install company-relative catalyst context using already-fetched evidence only."""
    _install_snapshot_reference()
    _install_prefilter_reference()
    _install_analyzed_context()
    _install_operator_presentation()
