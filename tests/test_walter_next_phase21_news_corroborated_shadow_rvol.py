"""Phase 21: GS540 shadow-RVOL news corroboration belongs to Discovery + News."""

from pathlib import Path

from mide import gs540_news_corroborated_shadow_rvol as gs540
from mide.authorities import discovery_news


ROOT = Path(__file__).resolve().parents[1]


def test_gs540_public_and_private_compatibility_seams_delegate_to_discovery_news():
    assert gs540.shadow_rvol_rows is discovery_news.shadow_rvol_rows
    assert gs540.eligible_shadow_rows is discovery_news.eligible_shadow_rvol_rows
    assert (
        gs540.merge_news_corroborated_shadow_rvol
        is discovery_news.merge_news_corroborated_shadow_rvol
    )
    assert (
        gs540._fetch_targeted_articles
        is discovery_news.fetch_shadow_rvol_targeted_articles
    )
    assert gs540.AUTHORITY == discovery_news.SHADOW_RVOL_AUTHORITY
    assert gs540.SHADOW_LIMIT == discovery_news.SHADOW_RVOL_LIMIT
    assert gs540.MIN_SHADOW_RVOL == discovery_news.SHADOW_RVOL_MIN


def test_gs540_install_is_authoritative_discovery_news_install(monkeypatch):
    called = {"count": 0}

    def install():
        called["count"] += 1

    monkeypatch.setattr(discovery_news, "install_news_corroborated_shadow_rvol", install)
    gs540.install()

    assert called["count"] == 1


def test_gs540_source_is_compatibility_facade_not_duplicate_implementation():
    source = (ROOT / "mide/gs540_news_corroborated_shadow_rvol.py").read_text(
        encoding="utf-8"
    )

    assert "def _news(" in source
    assert "from mide.authorities import discovery_news as _news" not in source
    assert "DISCOVERY_IDENTITY_ONLY_NEWS_CORROBORATED_SHADOW_RVOL" in source
    assert "def shadow_rvol_rows(" not in source
    assert "def eligible_shadow_rows(" not in source
    assert "def merge_news_corroborated_shadow_rvol(" not in source


def test_phase21_scope_remains_discovery_identity_only():
    source = (ROOT / "mide/gs540_news_corroborated_shadow_rvol.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
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
