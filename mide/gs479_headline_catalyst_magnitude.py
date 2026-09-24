"""GS479: historical compatibility facade for headline catalyst magnitude.

Phase 26 assigns deterministic headline-scale extraction and record/news enrichment to
Discovery + News, while Presentation + Audio owns the Catalyst-section display.

GS479 remains at its historical startup/import point because GS503 and regression tests
consume `headline_magnitude_context` and the private installer entry points. The
contract is unchanged: disclosed headline facts only, with no company-scale inference,
catalyst-score change, qualification, ranking, readiness, execution, or order authority.
"""
from __future__ import annotations

from mide.authorities import discovery_news as _news
from mide.authorities import presentation_audio as _presentation


AUTHORITY = _news.HEADLINE_MAGNITUDE_AUTHORITY
_OWNER_ANALYZE = _news._HEADLINE_MAGNITUDE_ANALYZE_OWNER
_OWNER_CLASSIFY = _news._HEADLINE_MAGNITUDE_CLASSIFY_OWNER
_OWNER_WHY = _presentation._HEADLINE_MAGNITUDE_WHY_OWNER

_MONEY_RE = _news._HEADLINE_MONEY_RE
_WORD_MONEY_RE = _news._HEADLINE_WORD_MONEY_RE
_DURATION_RE = _news._HEADLINE_DURATION_RE
_CONTRACT_TERMS = _news._HEADLINE_CONTRACT_TERMS
_UNIT_MULTIPLIER = _news._HEADLINE_UNIT_MULTIPLIER

_money_value = _news._headline_money_value
_dollar_amounts = _news._headline_dollar_amounts
_duration_years = _news._headline_duration_years
_scale_band = _news._headline_scale_band
_format_money = _news._headline_format_money
headline_magnitude_context = _news.headline_magnitude_context

_install_gs315_metadata = _news.install_headline_magnitude_metadata
_install_analyzed_records = _news.install_headline_magnitude_records
_install_operator_presentation = (
    _presentation.install_headline_catalyst_magnitude_presentation
)


def install() -> None:
    """Install GS479 through authoritative Discovery + News and Presentation + Audio."""
    _news.install_headline_catalyst_magnitude_news()
    _presentation.install_headline_catalyst_magnitude_presentation()


def __getattr__(name: str):
    try:
        return getattr(_news, name)
    except AttributeError:
        try:
            return getattr(_presentation, name)
        except AttributeError:
            raise AttributeError(name) from None


__all__ = [
    "AUTHORITY",
    "headline_magnitude_context",
    "install",
]
