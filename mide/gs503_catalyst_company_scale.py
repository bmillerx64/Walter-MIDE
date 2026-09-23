"""GS503: historical compatibility facade for catalyst/company scale context.

Phase 20 assigns GS503's validated responsibilities to Walter Next authorities:

* Market Evidence owns native Webull market-value carry-through, prefilter carry-through,
  factual catalyst/company relative-scale context, and analyzed-record diagnostics.
* Presentation + Audio owns the Catalyst-section display of those scale facts.

GS503 remains at its historical startup/import point so existing tests, warm-runtime
wrapper ownership markers, and downstream record contracts continue to behave exactly
as before. No provider request, score, rank, qualification, readiness, alert,
execution, or order authority is added here. Historical scope-lock vocabulary remains
visible for compatibility: additional_provider_requests stays zero in Market Evidence,
and valuation_impact_inferred remains false in the company-scale context contract.
"""
from __future__ import annotations

from mide.authorities import market_evidence as _market
from mide.authorities import presentation_audio as _presentation


AUTHORITY = _market.CATALYST_SCALE_AUTHORITY
_SNAPSHOT_OWNER = _market._CATALYST_SCALE_SNAPSHOT_OWNER
_PREFILTER_OWNER = _market._CATALYST_SCALE_PREFILTER_OWNER
_ANALYZE_OWNER = _market._CATALYST_SCALE_ANALYZE_OWNER
_WHY_OWNER = "_walter_gs503_scale_why_owner"

_number = _market._scale_number
_money = _market._scale_money
_ratio_text = _market._scale_ratio_text
_scale_band = _market._relative_scale_band
_quantity_values = _market._scale_quantity_values
_market_cap_reference = _market.market_cap_reference
company_scale_context = _market.company_scale_context

_install_snapshot_reference = _market.install_catalyst_scale_snapshot_reference
_install_prefilter_reference = _market.install_catalyst_scale_prefilter_reference
_install_analyzed_context = _market.install_catalyst_scale_analyzed_context
_install_operator_presentation = (
    _presentation.install_catalyst_company_scale_presentation
)


def install() -> None:
    """Install GS503 through Market Evidence and Presentation + Audio ownership."""
    _market.install_catalyst_company_scale_evidence()
    _presentation.install_catalyst_company_scale_presentation()


def __getattr__(name: str):
    try:
        return getattr(_market, name)
    except AttributeError:
        try:
            return getattr(_presentation, name)
        except AttributeError:
            raise AttributeError(name) from None


__all__ = [
    "AUTHORITY",
    "company_scale_context",
    "install",
]
