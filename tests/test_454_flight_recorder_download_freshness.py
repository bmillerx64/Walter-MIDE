from pathlib import Path

from mide import gs454_flight_recorder_download_freshness as gs454


def _deferred(path: Path):
    def payload():
        return path.read_bytes()

    payload._gs448_deferred_flight_recorder = True
    return payload


def test_version_token_is_stable_until_recorder_changes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = Path("data/flight_recorder.jsonl")
    path.parent.mkdir(parents=True)
    path.write_bytes(b'{"scan":"one"}\n')

    first = gs454.recorder_version_token(path)
    unchanged = gs454.recorder_version_token(path)
    path.open("ab").write(b'{"scan":"two"}\n')
    second = gs454.recorder_version_token(path)

    assert unchanged == first
    assert second != first


def test_versioned_widget_identity_prevents_reused_deferred_snapshot(tmp_path, monkeypatch):
    import streamlit as st

    monkeypatch.chdir(tmp_path)
    path = Path("data/flight_recorder.jsonl")
    path.parent.mkdir(parents=True)
    first_bytes = b'{"scan":"one"}\n'
    path.write_bytes(first_bytes)
    deferred = _deferred(path)

    media_cache = {}
    observed_keys = []
    original = st.download_button

    def fake_download_button(*args, **kwargs):
        key = kwargs.get("key")
        observed_keys.append(key)
        data = kwargs.get("data")
        if data is None and len(args) > 1:
            data = args[1]
        if key not in media_cache:
            media_cache[key] = data() if callable(data) else data
        return media_cache[key]

    try:
        monkeypatch.setattr(st, "download_button", fake_download_button)
        gs454.install()
        downloaded_first = st.download_button(
            "Download Flight Recorder",
            data=deferred,
            file_name="flight_recorder.jsonl.gz",
            mime="application/gzip",
        )

        second_line = b'{"scan":"two"}\n'
        with path.open("ab") as handle:
            handle.write(second_line)

        downloaded_second = st.download_button(
            "Download Flight Recorder",
            data=deferred,
            file_name="flight_recorder.jsonl.gz",
            mime="application/gzip",
        )

        assert downloaded_first == first_bytes
        assert downloaded_second == first_bytes + second_line
        assert observed_keys[0]
        assert observed_keys[1]
        assert observed_keys[1] != observed_keys[0]
    finally:
        monkeypatch.setattr(st, "download_button", original)


def test_explicit_download_key_is_preserved(monkeypatch):
    import streamlit as st

    captured = {}
    original = st.download_button

    def fake_download_button(*args, **kwargs):
        captured.update(kwargs)
        return "ok"

    deferred = _deferred(Path("unused.jsonl"))
    try:
        monkeypatch.setattr(st, "download_button", fake_download_button)
        gs454.install()
        result = st.download_button(
            "Download Flight Recorder",
            data=deferred,
            key="operator-specified",
        )
        assert result == "ok"
        assert captured["key"] == "operator-specified"
    finally:
        monkeypatch.setattr(st, "download_button", original)


def test_unrelated_download_is_untouched(monkeypatch):
    import streamlit as st

    captured = {}
    original = st.download_button

    def fake_download_button(*args, **kwargs):
        captured.update(kwargs)
        return "ok"

    try:
        monkeypatch.setattr(st, "download_button", fake_download_button)
        gs454.install()
        result = st.download_button(
            "Download Candidate History",
            data=b"history",
            file_name="candidate_history.jsonl",
        )
        assert result == "ok"
        assert "key" not in captured
    finally:
        monkeypatch.setattr(st, "download_button", original)


def test_gs448_chains_gs454_after_deferred_export_install():
    source = Path("mide/gs448_deferred_flight_recorder_download.py").read_text(
        encoding="utf-8"
    )
    assert (
        "from .gs454_flight_recorder_download_freshness import install as install_gs454"
        in source
    )
    assert source.index("_install_download_metadata()") < source.index("install_gs454()")


def test_gs454_scope_lock_is_export_freshness_only():
    source = Path("mide/gs454_flight_recorder_download_freshness.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "participation_score =",
        "expansion_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "alignment_score =",
        "candidate_status =",
        "request_scan(",
        "play_alert(",
        "place_order(",
    )
    assert not any(token in source for token in forbidden)
    assert 'AUTHORITY = "EXPORT_FRESHNESS_ONLY"' in source
    assert "_gs454_trading_logic_changed = False" in source
