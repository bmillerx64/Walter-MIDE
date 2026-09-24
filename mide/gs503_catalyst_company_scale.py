"""Compatibility facade for catalyst/company-scale context.

Market Evidence owns native Webull market-value carry-through, prefilter carry-through,
factual catalyst/company relative-scale context and analyzed-record diagnostics.
Presentation + Audio owns the Catalyst-section display of those scale facts.

The two authorities are resolved lazily at call/install time for warm Streamlit safety.
Historical private installer seams remain callable because GS503 regression coverage
patches the live snapshot, prefilter, analyze and operator-presentation boundaries.

Historical scope-lock markers retained:
additional_provider_requests
valuation_impact_inferred

No provider request, score, rank, qualification, readiness, alert, execution or order
authority is added here.
"""
from __future__ import annotations


def _market():
    from mide.authorities import market_evidence

    return market_evidence


def _presentation():
    from mide.authorities import presentation_audio

    return presentation_audio


def _number(value):
    current = getattr(_market(), "_scale_number", None)
    return current(value) if callable(current) else None


def _money(value) -> str:
    current = getattr(_market(), "_scale_money", None)
    return str(current(value)) if callable(current) else ""


def _ratio_text(value) -> str:
    current = getattr(_market(), "_scale_ratio_text", None)
    return str(current(value)) if callable(current) else ""


def _scale_band(*args, **kwargs):
    current = getattr(_market(), "_relative_scale_band", None)
    return (
        current(*args, **kwargs)
        if callable(current)
        else "NOT_EVALUATED_NO_COMPARABLE_RATIO"
    )


def _quantity_values(*args, **kwargs):
    current = getattr(_market(), "_scale_quantity_values", None)
    return list(current(*args, **kwargs) or []) if callable(current) else []


def _market_cap_reference(*args, **kwargs):
    current = getattr(_market(), "market_cap_reference", None)
    return current(*args, **kwargs) if callable(current) else (None, None)


def company_scale_context(
    record: dict,
    candidate: dict | None = None,
) -> dict:
    current = getattr(_market(), "company_scale_context", None)
    if callable(current):
        return current(record, candidate)
    return {
        "authority": "CATALYST_COMPANY_SCALE_CONTEXT_ONLY",
        "market_cap_available": False,
        "relative_scale_band": "NOT_EVALUATED_NO_MARKET_CAP",
        "summary": "",
        "valuation_impact_inferred": False,
        "trading_authority_changed": False,
    }


def _install_snapshot_reference() -> None:
    current = getattr(
        _market(),
        "install_catalyst_scale_snapshot_reference",
        None,
    )
    if callable(current):
        current()


def _install_prefilter_reference() -> None:
    current = getattr(
        _market(),
        "install_catalyst_scale_prefilter_reference",
        None,
    )
    if callable(current):
        current()


def _install_analyzed_context() -> None:
    current = getattr(
        _market(),
        "install_catalyst_scale_analyzed_context",
        None,
    )
    if callable(current):
        current()


def _install_operator_presentation() -> None:
    current = getattr(
        _presentation(),
        "install_catalyst_company_scale_presentation",
        None,
    )
    if callable(current):
        current()


def install() -> None:
    """Install GS503 through lazy Market Evidence and Presentation + Audio."""
    current = getattr(
        _market(),
        "install_catalyst_company_scale_evidence",
        None,
    )
    if callable(current):
        current()
    _install_operator_presentation()


def __getattr__(name: str):
    try:
        return getattr(_market(), name)
    except AttributeError:
        try:
            return getattr(_presentation(), name)
        except AttributeError:
            raise AttributeError(name) from None


__all__ = [
    "company_scale_context",
    "install",
]
