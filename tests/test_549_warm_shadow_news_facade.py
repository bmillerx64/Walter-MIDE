"""GS549: retained pre-GS544 providers get a shadow-only Alpaca news facade."""

from pathlib import Path

from mide import gs549_warm_shadow_news_facade as gs549


ROOT = Path(__file__).resolve().parents[1]


class CurrentNewsClient:
    def news(self, *_args, **_kwargs):
        return []


class LegacyUniverseOnly:
    def assets(self):
        return []


class LiveClient:
    def __init__(self, universe_client):
        self._universe_client = universe_client
        self.diagnostics = {}


def test_gs549_current_news_capable_client_passes_through_without_factory():
    client = LiveClient(CurrentNewsClient())

    def forbidden_factory():
        raise AssertionError("factory must stay lazy for current providers")

    observer, used = gs549.observer_client(client, forbidden_factory)

    assert observer is client
    assert used is False


def test_gs549_warm_legacy_universe_gets_detached_shadow_only_facade():
    legacy = LegacyUniverseOnly()
    client = LiveClient(legacy)
    calls = []
    news_client = CurrentNewsClient()

    def factory():
        calls.append("built")
        return news_client

    observer, used = gs549.observer_client(client, factory)
    observer_again, used_again = gs549.observer_client(client, factory)

    assert used is True
    assert used_again is True
    assert observer is not client
    assert observer_again is not client
    assert observer._universe_client is news_client
    assert observer_again._universe_client is news_client
    assert observer.diagnostics is client.diagnostics
    assert client._universe_client is legacy
    assert calls == ["built"]


def test_gs549_rejects_factory_without_news_capability():
    client = LiveClient(LegacyUniverseOnly())

    try:
        gs549.observer_client(client, LegacyUniverseOnly)
    except RuntimeError as exc:
        assert "without news()" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_gs549_app_uses_facade_only_inside_gs544_shadow_observer_block():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = source.index("# GS544: observe only")
    end = source.index("        decisions = {}", start)
    block = source[start:end]

    assert "mide.gs549_warm_shadow_news_facade" in block
    assert "observer_client(" in block
    assert "observe_shadow," in block
    assert "shadow_trace = observe_shadow(" not in block
    assert "shadow_client" in block
    assert "client._universe_client =" not in block
    assert "news_items.extend" not in block
    assert "news_items.append" not in block
    assert "indexed.update" not in block
    assert "indexed[" not in block


def test_gs549_module_scope_is_observation_only():
    source = (
        ROOT / "mide/gs549_warm_shadow_news_facade.py"
    ).read_text(encoding="utf-8")

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "expansion_score =",
        "opportunity_state =",
        "place_order(",
        "submit_order(",
    )
    assert not any(token in source for token in forbidden)
