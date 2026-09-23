"""Phase 19: GS502 Benzinga breaking news is split by authoritative ownership."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from mide import gs502_benzinga_breaking_news as gs502
from mide.authorities import discovery_news, replay_validation


ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc


def test_gs502_transport_and_normalization_live_in_discovery_news():
    assert gs502.normalize_benzinga_article is discovery_news.normalize_benzinga_article
    assert gs502.fetch_benzinga_delta is discovery_news.fetch_benzinga_delta
    assert gs502._configured_benzinga_token is discovery_news.benzinga_configured_token
    assert gs502._ARTICLE_CACHE is discovery_news._BENZINGA_ARTICLE_CACHE


def test_gs502_poll_facade_preserves_legacy_scalar_state(monkeypatch):
    gs502._ARTICLE_CACHE.clear()
    gs502._LAST_SUCCESSFUL_POLL = None
    stamp = datetime(2026, 9, 18, 14, 40, tzinfo=UTC)

    monkeypatch.setattr(gs502, "fetch_benzinga_delta", lambda *args, **kwargs: [])

    rows, trace = gs502.poll_breaking_news(token="configured", now=stamp)

    assert rows == []
    assert trace["request_made"] is True
    assert gs502._LAST_SUCCESSFUL_POLL == stamp


def test_gs502_merge_facade_preserves_token_and_poller_override_seams(monkeypatch):
    class Client:
        provider_name = "Webull OpenAPI"
        diagnostics = {}

    monkeypatch.setattr(gs502, "_configured_benzinga_token", lambda: "")
    seeds, reasons = gs502.merge_breaking_news_discovery(
        Client(),
        ["NATIVE"],
        {"NATIVE": ["Webull native"]},
    )

    assert seeds == ["NATIVE"]
    assert reasons == {"NATIVE": ["Webull native"]}
    assert gs502._LATEST_TRACE["request_made"] is False


def test_replay_validation_owns_benzinga_trace_persistence(monkeypatch):
    captured = {}

    def baseline(_recorder, scan, records):
        captured["scan"] = scan
        return scan

    monkeypatch.setattr(gs502, "_LATEST_TRACE", {
        "authority": gs502.AUTHORITY,
        "configured": True,
        "request_made": True,
        "selected_symbols": ["SDST"],
        "trading_authority_changed": False,
    })

    wrapped = replay_validation.benzinga_breaking_news_recorder_wrapper(baseline)
    wrapped(object(), {"scan_id": "phase19"}, [])

    assert captured["scan"]["benzinga_breaking_news_trace"]["selected_symbols"] == ["SDST"]
    assert (
        captured["scan"]["benzinga_breaking_news_trace"]["trading_authority_changed"]
        is False
    )


def test_gs502_source_is_now_compatibility_facade_not_duplicate_implementation():
    source = (ROOT / "mide/gs502_benzinga_breaking_news.py").read_text(
        encoding="utf-8"
    )

    assert "from mide.authorities import discovery_news as _news" in source
    assert "from mide.authorities import replay_validation as _replay" in source
    assert "def normalize_benzinga_article(" not in source
    assert "def fetch_benzinga_delta(" not in source
    assert "def _recorder_wrapper(" not in source
    assert "updatedSince" in source
    assert "Authorization" in source


def test_phase19_authorities_keep_benzinga_out_of_trading_authority():
    for relative in (
        "mide/authorities/discovery_news.py",
        "mide/authorities/replay_validation.py",
        "mide/gs502_benzinga_breaking_news.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        for token in (
            "qualified_for_entry =",
            "qualified_for_alert =",
            "mission_rank =",
            "participation_score =",
            "expansion_score =",
            "place_order(",
            "submit_order(",
        ):
            assert token not in source
