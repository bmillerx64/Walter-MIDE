from __future__ import annotations

import streamlit as st

from mide.gs350_download_export_reliability import install


def test_download_buttons_default_to_ignore_without_overriding_explicit_behavior(monkeypatch):
    calls = []

    def fake_download_button(*args, **kwargs):
        calls.append((args, kwargs))
        return "ok"

    monkeypatch.setattr(st, "download_button", fake_download_button)
    install()

    assert st.download_button("Download Candidate History", data=b"candidate") == "ok"
    assert calls[-1][1]["on_click"] == "ignore"

    assert st.download_button(
        "Explicit behavior",
        data=b"x",
        on_click="rerun",
    ) == "ok"
    assert calls[-1][1]["on_click"] == "rerun"


def test_install_is_idempotent(monkeypatch):
    def fake_download_button(*args, **kwargs):
        return None

    monkeypatch.setattr(st, "download_button", fake_download_button)
    install()
    first = st.download_button
    install()
    assert st.download_button is first
    assert getattr(st.download_button, "_gs350_download_export_reliability", False)
