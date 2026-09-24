"""Phase 51: GS502/GS503 are warm-deploy-safe lazy authority facades."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs502_benzinga_breaking_news as gs502
from mide import gs503_catalyst_company_scale as gs503
from mide.authorities import discovery_news, market_evidence


ROOT = Path(__file__).resolve().parents[1]


def test_gs502_cache_resolves_authoritative_container():
    assert (
        gs502._ARTICLE_CACHE
        is discovery_news._BENZINGA_ARTICLE_CACHE
    )


def test_gs502_mutable_fetcher_seam_survives(monkeypatch):
    marker = object()
    monkeypatch.setattr(
        gs502,
        "fetch_benzinga_delta",
        lambda *args, **kwargs: marker,
    )

    assert gs502.fetch_benzinga_delta(
        "token",
        since=object(),
    ) is marker


def test_gs503_facade_delegates_company_scale(monkeypatch):
    expected = {
        "relative_scale_band": "MAJOR_RELATIVE_SCALE"
    }
    monkeypatch.setattr(
        market_evidence,
        "company_scale_context",
        lambda record, candidate=None: expected,
    )

    assert gs503.company_scale_context(
        {"symbol": "ABC"}
    ) is expected


def test_phase51_installers_tolerate_stale_authority_generations(monkeypatch):
    monkeypatch.setattr(
        gs502,
        "_news",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        gs502,
        "_replay",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        gs503,
        "_market",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        gs503,
        "_presentation",
        lambda: SimpleNamespace(),
    )

    assert gs502.install() is None
    assert gs503.install() is None


def test_phase51_facades_are_lazy_not_eager_authority_bindings():
    gs502_source = (
        ROOT / "mide/gs502_benzinga_breaking_news.py"
    ).read_text(encoding="utf-8")
    gs503_source = (
        ROOT / "mide/gs503_catalyst_company_scale.py"
    ).read_text(encoding="utf-8")

    assert "def _news(" in gs502_source
    assert "def _replay(" in gs502_source
    assert "from mide.authorities import discovery_news as _news" not in gs502_source
    assert "from mide.authorities import replay_validation as _replay" not in gs502_source

    assert "def _market(" in gs503_source
    assert "def _presentation(" in gs503_source
    assert "from mide.authorities import market_evidence as _market" not in gs503_source
    assert "from mide.authorities import presentation_audio as _presentation" not in gs503_source


def test_phase51_historical_scope_markers_remain_visible():
    gs502_source = (
        ROOT / "mide/gs502_benzinga_breaking_news.py"
    ).read_text(encoding="utf-8")
    gs503_source = (
        ROOT / "mide/gs503_catalyst_company_scale.py"
    ).read_text(encoding="utf-8")

    assert "updatedSince" in gs502_source
    assert "Authorization" in gs502_source
    assert "additional_provider_requests" in gs503_source
    assert "valuation_impact_inferred" in gs503_source
