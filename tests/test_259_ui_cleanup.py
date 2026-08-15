import importlib


def test_gs259_suppresses_only_obsolete_alpaca_feed_messages(monkeypatch):
    import streamlit as st
    cleanup = importlib.import_module("mide.gs259_ui_cleanup")

    seen = []

    def fake_success(body, *args, **kwargs):
        seen.append(("success", body))
        return "success"

    def fake_warning(body, *args, **kwargs):
        seen.append(("warning", body))
        return "warning"

    monkeypatch.setattr(st, "success", fake_success)
    monkeypatch.setattr(st, "warning", fake_warning)
    cleanup.install()

    assert st.success("SIP feed selected") is None
    assert st.warning("IEX feed selected. Set ALPACA_FEED='sip' for consolidated data.") is None
    assert st.success("Scan Complete") == "success"
    assert st.warning("Provider temporarily unavailable") == "warning"
    assert seen == [
        ("success", "Scan Complete"),
        ("warning", "Provider temporarily unavailable"),
    ]
