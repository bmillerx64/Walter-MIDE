"""GS480: historical compatibility facade for catalyst-story intelligence.

Phase 18 moves GS480 responsibilities into Walter Next's authoritative components:

* Discovery + News owns story parsing, explicit ticker extraction, FMP article
  transport, marketwide/targeted handoff, news-seed enrichment, and candidate news
  enrichment.
* Presentation + Audio owns catalyst-story display facts.
* Replay / Validation owns Flight Recorder story/news trace persistence.

GS480 intentionally remains importable because GS502, GS481, regressions, and later
company-scale/live-evidence layers still consume its historical contracts. Mutable
trace/cache containers are shared with Discovery + News and are mutated in place so
existing readers retain object identity across warm Streamlit reruns.
"""
from __future__ import annotations

from mide.authorities import discovery_news as _news
from mide.authorities import presentation_audio as _presentation
from mide.authorities import replay_validation as _replay


# Public historical constants.
UTC = _news.UTC
AUTHORITY = _news.AUTHORITY
STORY_TEXT_LIMIT = _news.STORY_TEXT_LIMIT
STORY_SEED_TYPE = _news.STORY_SEED_TYPE
STORY_SEED_REASON = _news.STORY_SEED_REASON
STORY_FRESHNESS = _news.STORY_FRESHNESS

# Historical owner markers remain readable for regressions/introspection.
_NORMALIZE_OWNER = _news._NORMALIZE_OWNER
_AS_DICT_OWNER = _news._AS_DICT_OWNER
_CACHED_OWNER = _news._CACHED_OWNER
_SERVICE_FETCH_OWNER = _news._SERVICE_FETCH_OWNER
_SELECT_OWNER = _news._SELECT_OWNER
_MERGE_OWNER = _news._MERGE_OWNER
_BUILD_OWNER = _news._BUILD_OWNER
_INDEX_OWNER = _news._INDEX_OWNER
_ANALYZE_OWNER = _news._ANALYZE_OWNER
_WHY_OWNER = "_walter_gs480_story_why_owner"
_RECORDER_OWNER = "_walter_gs480_story_recorder_owner"

# Compatibility views over authoritative mutable containers. These objects must not be
# replaced by the authority; Discovery + News mutates them in place.
_MARKETWIDE_BY_SYMBOL = _news._MARKETWIDE_BY_SYMBOL
_LAST_SELECTED = _news._LAST_SELECTED
_LATEST_MARKETWIDE_TRACE = _news._LATEST_MARKETWIDE_TRACE
_LATEST_TARGETED_TRACE = _news._LATEST_TARGETED_TRACE

# Story/news compatibility API.
explicit_ticker_mentions = _news.explicit_ticker_mentions
story_intelligence = _news.story_intelligence
_utc = _news._utc
_story_text = _news._story_text
_event_categories = _news._event_categories
_number_role = _news._number_role
_quantities = _news._quantities
_article_context = _news._article_context
_remember_marketwide = _news._remember_marketwide
_safe_selected = _news._safe_selected
_inherit = _news._inherit

_install_article_transport = _news._install_article_transport
_install_marketwide_selection = _news._install_marketwide_selection
_install_discovery_diagnostics = _news._install_discovery_diagnostics
_install_targeted_handoff = _news._install_targeted_handoff
_install_index_and_records = _news._install_index_and_records

# Presentation and replay compatibility API.
_install_presentation = _presentation.install_catalyst_story_presentation
_recorder_wrapper = _replay.catalyst_story_recorder_wrapper
_install_recorder_truth = _replay.install_catalyst_story_trace


def install() -> None:
    """Install GS480 semantics through the authoritative Walter Next components."""
    _news.install_catalyst_story_news()
    _presentation.install_catalyst_story_presentation()
    _replay.install_catalyst_story_trace()


def __getattr__(name: str):
    """Delegate obscure legacy discovery/news internals to the authoritative owner."""
    try:
        return getattr(_news, name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "AUTHORITY",
    "STORY_FRESHNESS",
    "STORY_SEED_REASON",
    "STORY_SEED_TYPE",
    "STORY_TEXT_LIMIT",
    "explicit_ticker_mentions",
    "story_intelligence",
    "install",
]
