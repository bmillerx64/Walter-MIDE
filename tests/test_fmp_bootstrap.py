from __future__ import annotations

import os
import sys
from types import SimpleNamespace

from mide.fmp_bootstrap import activate_streamlit_fmp_secret


class Secrets(dict):
    pass


def _install_streamlit(monkeypatch, secrets):
    fake = SimpleNamespace(secrets=Secrets(secrets))
    monkeypatch.setitem(sys.modules, "streamlit", fake)


def test_activates_top_level_streamlit_fmp_secret(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    _install_streamlit(monkeypatch, {"FMP_API_KEY": "secret-value"})
    assert activate_streamlit_fmp_secret() is True
    assert os.environ["FMP_API_KEY"] == "secret-value"


def test_activates_nested_streamlit_fmp_secret(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    _install_streamlit(monkeypatch, {"fmp": {"api_key": "nested-secret"}})
    assert activate_streamlit_fmp_secret() is True
    assert os.environ["FMP_API_KEY"] == "nested-secret"


def test_missing_secret_returns_false_without_creating_env(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    _install_streamlit(monkeypatch, {})
    assert activate_streamlit_fmp_secret() is False
    assert "FMP_API_KEY" not in os.environ
