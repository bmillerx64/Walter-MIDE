"""Phase 18: GS480 catalyst-story intelligence is split by authoritative ownership."""

from __future__ import annotations

from pathlib import Path

from mide import gs480_catalyst_story_intelligence as gs480
from mide.authorities import discovery_news, presentation_audio, replay_validation


ROOT = Path(__file__).resolve().parents[1]


def test_gs480_is_a_compatibility_facade_over_discovery_news():
    assert gs480.story_intelligence is discovery_news.story_intelligence
    assert gs480.explicit_ticker_mentions is discovery_news.explicit_ticker_mentions
    assert gs480._install_article_transport is discovery_news._install_article_transport
    assert gs480._install_marketwide_selection is discovery_news._install_marketwide_selection
    assert gs480._install_targeted_handoff is discovery_news._install_targeted_handoff
    assert gs480._install_index_and_records is discovery_news._install_index_and_records


def test_gs480_trace_and_cache_containers_keep_authoritative_identity():
    assert gs480._MARKETWIDE_BY_SYMBOL is discovery_news._MARKETWIDE_BY_SYMBOL
    assert gs480._LAST_SELECTED is discovery_news._LAST_SELECTED
    assert gs480._LATEST_MARKETWIDE_TRACE is discovery_news._LATEST_MARKETWIDE_TRACE
    assert gs480._LATEST_TARGETED_TRACE is discovery_news._LATEST_TARGETED_TRACE

    marketwide_id = id(discovery_news._LATEST_MARKETWIDE_TRACE)
    targeted_id = id(discovery_news._LATEST_TARGETED_TRACE)
    discovery_news._LATEST_MARKETWIDE_TRACE.clear()
    discovery_news._LATEST_MARKETWIDE_TRACE.extend([{"symbol": "PAAI"}])
    discovery_news._LATEST_TARGETED_TRACE.clear()
    discovery_news._LATEST_TARGETED_TRACE.update({"PAAI": {"article_found": True}})

    assert id(discovery_news._LATEST_MARKETWIDE_TRACE) == marketwide_id
    assert id(discovery_news._LATEST_TARGETED_TRACE) == targeted_id
    assert gs480._LATEST_MARKETWIDE_TRACE == [{"symbol": "PAAI"}]
    assert gs480._LATEST_TARGETED_TRACE["PAAI"]["article_found"] is True

    discovery_news._LATEST_MARKETWIDE_TRACE.clear()
    discovery_news._LATEST_TARGETED_TRACE.clear()


def test_presentation_authority_owns_story_display_facts(monkeypatch):
    from mide import ui

    def baseline(_record):
        return {"Catalyst": "Headline catalyst"}

    monkeypatch.setattr(ui, "_why_sections", baseline)
    presentation_audio.install_catalyst_story_presentation()

    sections = ui._why_sections({
        "catalyst_story": {
            "categories": ["CONTRACT_ORDER", "FINANCIAL_GROWTH"],
            "quantities": [
                {"text": "$1 billion", "role": "DEAL_OR_BACKLOG"},
                {"text": "$100 million", "role": "REVENUE"},
            ],
        }
    })

    assert "Headline catalyst" in sections["Catalyst"]
    assert "Story: Contract Order · Financial Growth" in sections["Catalyst"]
    assert "$1 billion deal or backlog" in sections["Catalyst"]
    assert getattr(ui._why_sections, "_walter_gs480_story_why_owner") is True


def test_replay_authority_reads_gs480_compatibility_trace(monkeypatch):
    captured = {}

    def baseline(_self, scan, records):
        captured["scan"] = scan
        captured["records"] = records
        return scan

    monkeypatch.setattr(gs480, "_LATEST_MARKETWIDE_TRACE", [{
        "symbol": "PAAI",
        "headline": "10-year agreement",
    }])
    monkeypatch.setattr(gs480, "_LATEST_TARGETED_TRACE", {
        "PAAI": {
            "symbol": "PAAI",
            "article_found": True,
            "headline": "10-year agreement",
            "created_at": "2026-09-17T15:00:00+00:00",
            "age_seconds_at_scan": 120.0,
            "source": "GlobeNewswire",
            "provider": "Financial Modeling Prep",
            "catalyst_score": 8,
            "explicit_symbols": ["PAAI"],
            "story_context": {"categories": ["CONTRACT_ORDER"]},
            "marketwide_handoff": True,
        }
    })

    wrapped = replay_validation.catalyst_story_recorder_wrapper(baseline)
    wrapped(object(), {"symbols": [{"symbol": "PAAI", "evidence": {}}]}, [])

    scan = captured["scan"]
    assert scan["symbols"][0]["evidence"]["news_headline"] == "10-year agreement"
    assert scan["symbols"][0]["evidence"]["catalyst_story"]["categories"] == ["CONTRACT_ORDER"]
    assert scan["news_trace"]["marketwide_selected"][0]["symbol"] == "PAAI"
    assert scan["news_trace"]["additional_provider_requests"] == 0


def test_gs480_source_no_longer_duplicates_authoritative_implementations():
    source = (ROOT / "mide/gs480_catalyst_story_intelligence.py").read_text(
        encoding="utf-8"
    )
    assert "from mide.authorities import discovery_news as _news" in source
    assert "from mide.authorities import presentation_audio as _presentation" in source
    assert "from mide.authorities import replay_validation as _replay" in source
    assert "def story_intelligence(" not in source
    assert "def _install_presentation(" not in source
    assert "def _install_recorder_truth(" not in source


def test_phase18_scope_preserves_trading_authority_boundaries():
    for relative in (
        "mide/authorities/discovery_news.py",
        "mide/authorities/presentation_audio.py",
        "mide/authorities/replay_validation.py",
        "mide/gs480_catalyst_story_intelligence.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        for token in (
            "qualified_for_entry =",
            "qualified_for_alert =",
            "opportunity_score =",
            "conviction_score =",
            "execute_order",
            "place_order",
        ):
            assert token not in source
