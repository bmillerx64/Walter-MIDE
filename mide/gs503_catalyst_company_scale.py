"""Compatibility facade for catalyst/company-scale context.

Market Evidence owns native Webull market-value carry-through, prefilter carry-through,
factual catalyst/company relative-scale context and analyzed-record diagnostics.
Presentation + Audio owns the Catalyst-section display of those scale facts.

Authority-owned compatibility callables resolve lazily through module __getattr__, so
GS503 preserves exact function identity without eager authority imports. The historical
private installer names remain available because regression coverage patches the live
snapshot, prefilter, analyze and operator-presentation boundaries.

Historical scope-lock markers retained:
additional_provider_requests
valuation_impact_inferred

No provider request, score, rank, qualification, readiness, alert, execution or order
authority is added here.
"""
from __future__ import annotations


_MARKET_EXPORTS = {
    "AUTHORITY": "CATALYST_SCALE_AUTHORITY",
    "_SNAPSHOT_OWNER": "_CATALYST_SCALE_SNAPSHOT_OWNER",
    "_PREFILTER_OWNER": "_CATALYST_SCALE_PREFILTER_OWNER",
    "_ANALYZE_OWNER": "_CATALYST_SCALE_ANALYZE_OWNER",
    "_number": "_scale_number",
    "_money": "_scale_money",
    "_ratio_text": "_scale_ratio_text",
    "_scale_band": "_relative_scale_band",
    "_quantity_values": "_scale_quantity_values",
    "_market_cap_reference": "market_cap_reference",
    "company_scale_context": "company_scale_context",
    "_install_snapshot_reference": "install_catalyst_scale_snapshot_reference",
    "_install_prefilter_reference": "install_catalyst_scale_prefilter_reference",
    "_install_analyzed_context": "install_catalyst_scale_analyzed_context",
}
_PRESENTATION_EXPORTS = {
    "_WHY_OWNER": "_CATALYST_SCALE_WHY_OWNER",
    "_install_operator_presentation": "install_catalyst_company_scale_presentation",
}


def _market():
    from mide.authorities import market_evidence

    return market_evidence


def _presentation():
    from mide.authorities import presentation_audio

    return presentation_audio


def install() -> None:
    """Install GS503 through lazy Market Evidence and Presentation + Audio."""
    evidence_install = getattr(
        _market(),
        "install_catalyst_company_scale_evidence",
        None,
    )
    if callable(evidence_install):
        evidence_install()

    presentation_install = getattr(
        _presentation(),
        "install_catalyst_company_scale_presentation",
        None,
    )
    if callable(presentation_install):
        presentation_install()


def __getattr__(name: str):
    target = _MARKET_EXPORTS.get(name)
    if target is not None:
        try:
            return getattr(_market(), target)
        except AttributeError:
            raise AttributeError(name) from None

    target = _PRESENTATION_EXPORTS.get(name)
    if target is not None:
        try:
            return getattr(_presentation(), target)
        except AttributeError:
            raise AttributeError(name) from None

    try:
        return getattr(_market(), name)
    except AttributeError:
        try:
            return getattr(_presentation(), name)
        except AttributeError:
            raise AttributeError(name) from None


__all__ = [
    "AUTHORITY",
    "company_scale_context",
    "install",
]
