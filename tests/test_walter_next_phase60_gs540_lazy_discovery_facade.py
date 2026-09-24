"""Phase 60: GS540 is a warm-deploy-safe lazy Discovery + News facade."""

from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from mide import gs540_news_corroborated_shadow_rvol as gs540
from mide.authorities import discovery_news


ROOT = Path(__file__).resolve().parents[1]


def test_phase60_constants_match_discovery_authority():
    assert gs540.AUTHORITY == discovery_news.SHADOW_RVOL_AUTHORITY
    assert gs540.SHADOW_LIMIT == discovery_news.SHADOW_RVOL_LIMIT
    assert gs540.MIN_SHADOW_RVOL == discovery_news.SHADOW_RVOL_MIN
    assert gs540.NEWS_LOOKBACK == discovery_news.SHADOW_RVOL_NEWS_LOOKBACK
    assert gs540.NEWS_LOOKBACK == timedelta(hours=6)
    assert gs540._OWNER == discovery_news._SHADOW_RVOL_OWNER


def test_phase60_current_runtime_preserves_exact_callable_identity():
    assert gs540._number is discovery_news._shadow_rvol_number
    assert gs540._now_utc is discovery_news.shadow_rvol_now_utc
    assert gs540.shadow_rvol_rows is discovery_news.shadow_rvol_rows
    assert gs540.eligible_shadow_rows is discovery_news.eligible_shadow_rvol_rows
    assert (
        gs540._fetch_targeted_articles
        is discovery_news.fetch_shadow_rvol_targeted_articles
    )
    assert (
        gs540.merge_news_corroborated_shadow_rvol
        is discovery_news.merge_news_corroborated_shadow_rvol
    )


def test_phase60_stale_discovery_generation_admits_nothing(monkeypatch):
    monkeypatch.setattr(gs540, "_news", lambda: SimpleNamespace())

    seeds = ["ABC"]
    reasons = {"ABC": ["existing"]}
    merged, merged_reasons, trace = gs540.merge_news_corroborated_shadow_rvol(
        object(),
        seeds,
        reasons,
    )

    assert merged == seeds
    assert merged_reasons == reasons
    assert trace["symbols_added"] == []
    assert trace["request_made"] is False
    assert trace["trading_authority_changed"] is False
    assert gs540.shadow_rvol_rows(object()) == []
    assert gs540.eligible_shadow_rows([{"symbol": "NEW"}]) == []
    assert gs540.install() is None


def test_phase60_facade_is_lazy_not_eager():
    source = (
        ROOT / "mide/gs540_news_corroborated_shadow_rvol.py"
    ).read_text(encoding="utf-8")

    assert "def _news(" in source
    assert "from mide.authorities import discovery_news as _news" not in source
    assert "DISCOVERY_IDENTITY_ONLY_NEWS_CORROBORATED_SHADOW_RVOL" in source


def test_phase60_scope_remains_discovery_identity_only():
    source = (
        ROOT / "mide/gs540_news_corroborated_shadow_rvol.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "participation_score =",
        "participation_surge_score =",
        "expansion_score =",
        "expansion_quality =",
        "mission_rank =",
        "place_order(",
        "submit_order(",
        "play_alert(",
    )
    assert not any(token in source for token in forbidden)
