from pathlib import Path

import mide.completed_scan as completed_scan


class _Provider:
    def __init__(self, label):
        self.label = label
        self.diagnostics = {}


def _reset_process_owner(monkeypatch):
    monkeypatch.setattr(completed_scan, "_PROCESS_LIVE_PROVIDER", None)
    monkeypatch.setattr(completed_scan, "_PROCESS_LIVE_PROVIDER_IDENTITY", None)
    monkeypatch.setattr(completed_scan, "_PROCESS_LIVE_PROVIDER_CLAIMS", 0)


def test_fresh_streamlit_session_reuses_existing_process_provider(monkeypatch):
    _reset_process_owner(monkeypatch)
    created = []

    def factory():
        provider = _Provider(f"provider-{len(created) + 1}")
        created.append(provider)
        return provider

    first, first_created = completed_scan.claim_process_live_provider(
        "WEBULL_OPENAPI_PRIMARY", None, factory
    )
    second, second_created = completed_scan.claim_process_live_provider(
        "WEBULL_OPENAPI_PRIMARY", None, factory
    )

    assert first_created is True
    assert second_created is False
    assert second is first
    assert len(created) == 1
    owner = first.diagnostics["runtime_provider_owner"]
    assert owner["authority"] == "PROCESS_WIDE_LIVE_PROVIDER_OWNER"
    assert owner["process_singleton"] is True
    assert owner["session_state_is_alias_only"] is True
    assert owner["claim_count"] == 2
    assert owner["trading_authority_changed"] is False


def test_retained_session_provider_can_seed_empty_process_owner(monkeypatch):
    _reset_process_owner(monkeypatch)
    retained = _Provider("retained")

    def must_not_build():
        raise AssertionError("a retained provider must be adopted, not replaced")

    provider, created = completed_scan.claim_process_live_provider(
        "WEBULL_OPENAPI_PRIMARY", retained, must_not_build
    )

    assert provider is retained
    assert created is False


def test_changed_provider_identity_creates_new_process_owner(monkeypatch):
    _reset_process_owner(monkeypatch)
    first, _ = completed_scan.claim_process_live_provider(
        "WEBULL_OPENAPI_PRIMARY", None, lambda: _Provider("first")
    )
    second, created = completed_scan.claim_process_live_provider(
        "OTHER_PROVIDER", first, lambda: _Provider("second")
    )

    assert created is True
    assert second is not first
    assert second.label == "second"


def test_app_rebinds_session_context_to_process_provider_owner():
    source = Path("app.py").read_text()

    assert "claim_process_live_provider(" in source
    assert '"WEBULL_OPENAPI_PRIMARY"' in source
    assert "context.provider_instance = client" in source
    assert "build_webull_process_provider" in source
