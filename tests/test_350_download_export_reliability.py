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


def test_flight_recorder_download_uses_native_rerun_and_preserves_direct_payload(monkeypatch):
    calls = []

    def fake_download_button(*args, **kwargs):
        calls.append((args, kwargs))
        return "ok"

    monkeypatch.setattr(st, "download_button", fake_download_button)
    install()

    payload = b"large-flight-recorder"
    assert st.download_button("Download Flight Recorder", data=payload) == "ok"

    _, kwargs = calls[-1]
    assert kwargs["on_click"] == "rerun"
    assert kwargs["data"] is payload
    assert "key" not in kwargs


def test_flight_recorder_preserves_explicit_key_callable_and_click_behavior(monkeypatch):
    calls = []

    def fake_download_button(*args, **kwargs):
        calls.append((args, kwargs))
        return "ok"

    monkeypatch.setattr(st, "download_button", fake_download_button)
    install()

    def payload_factory():
        return b"fresh"

    st.download_button(
        "Download Flight Recorder",
        data=payload_factory,
        key="explicit-key",
        on_click="ignore",
    )

    _, kwargs = calls[-1]
    assert kwargs["key"] == "explicit-key"
    assert kwargs["data"] is payload_factory
    assert kwargs["on_click"] == "ignore"


def test_flight_recorder_positional_payload_is_preserved_without_forced_key(monkeypatch):
    calls = []

    def fake_download_button(*args, **kwargs):
        calls.append((args, kwargs))
        return "ok"

    monkeypatch.setattr(st, "download_button", fake_download_button)
    install()

    payload = b"positional"
    st.download_button("Download Flight Recorder", payload)

    args, kwargs = calls[-1]
    assert args[1] is payload
    assert kwargs["on_click"] == "rerun"
    assert "key" not in kwargs


def test_install_is_idempotent(monkeypatch):
    def fake_download_button(*args, **kwargs):
        return None

    monkeypatch.setattr(st, "download_button", fake_download_button)
    install()
    first = st.download_button
    install()
    assert st.download_button is first
    assert getattr(st.download_button, "_gs350_download_export_reliability", False)
