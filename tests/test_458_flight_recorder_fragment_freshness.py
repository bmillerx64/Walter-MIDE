from pathlib import Path

import streamlit as st

from mide import gs350_download_export_reliability as gs350
from mide import gs454_flight_recorder_download_freshness as gs454
from mide import gs458_flight_recorder_fragment_freshness as gs458


def _copy_gs_markers(wrapper, wrapped):
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs"):
            setattr(wrapper, name, value)


def _deferred(path: Path):
    def payload():
        return path.read_bytes()

    payload._gs448_deferred_flight_recorder = True
    return payload


def test_fragment_only_rerun_recomputes_freshness_key_and_payload(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = Path("data/flight_recorder.jsonl")
    path.parent.mkdir(parents=True)
    first = b'{"scan":"one"}\n'
    second = b'{"scan":"two"}\n'
    path.write_bytes(first)

    media_cache = {}
    leaf_calls = []
    fragment_functions = []

    def leaf_download(*args, **kwargs):
        key = kwargs.get("key")
        data = kwargs.get("data")
        if data is None and len(args) > 1:
            data = args[1]
        if key not in media_cache:
            media_cache[key] = data() if callable(data) else data
        leaf_calls.append((key, kwargs.get("on_click"), media_cache[key]))
        return media_cache[key]

    def fake_fragment(func):
        fragment_functions.append(func)
        return func

    monkeypatch.setattr(st, "download_button", leaf_download)
    monkeypatch.setattr(st, "fragment", fake_fragment)

    # Reproduce the production topology: GS350 first creates the fragment boundary,
    # GS454 later lives outside it, then GS458 rebinds GS350 outermost.
    gs350.install()
    inner_gs350 = st.download_button

    def freshness(*args, **kwargs):
        label = args[0] if args else kwargs.get("label")
        data = kwargs.get("data")
        if data is None and len(args) > 1:
            data = args[1]
        if (
            label == gs454.FLIGHT_RECORDER_LABEL
            and callable(data)
            and getattr(data, "_gs448_deferred_flight_recorder", False)
            and "key" not in kwargs
        ):
            kwargs = dict(kwargs)
            kwargs["key"] = "walter-flight-recorder-" + gs454.recorder_version_token(path)
        return inner_gs350(*args, **kwargs)

    _copy_gs_markers(freshness, inner_gs350)
    freshness._gs454_flight_recorder_download_freshness = True
    monkeypatch.setattr(st, "download_button", freshness)

    gs458.install()
    outer = st.download_button
    assert getattr(outer, "_gs458_flight_recorder_fragment_freshness", False)

    deferred = _deferred(path)
    downloaded_first = outer(
        "Download Flight Recorder",
        data=deferred,
        file_name="flight_recorder.jsonl.gz",
        mime="application/gzip",
    )
    assert downloaded_first == first
    assert len(fragment_functions) == 1
    first_key = leaf_calls[-1][0]
    assert first_key
    assert leaf_calls[-1][1] == "rerun"

    # Simulate scans appending while only the Flight Recorder fragment is later rerun.
    with path.open("ab") as handle:
        handle.write(second)
    downloaded_second = fragment_functions[0]()
    second_key = leaf_calls[-1][0]

    assert downloaded_second == first + second
    assert second_key
    assert second_key != first_key
    assert len(fragment_functions) == 1  # no nested GS350 fragment


def test_late_rebind_preserves_explicit_operator_key(monkeypatch):
    calls = []
    fragments = []

    def leaf_download(*args, **kwargs):
        calls.append((args, kwargs))
        return "ok"

    def fake_fragment(func):
        fragments.append(func)
        return func

    monkeypatch.setattr(st, "download_button", leaf_download)
    monkeypatch.setattr(st, "fragment", fake_fragment)
    gs350.install()
    inner = st.download_button

    def later_wrapper(*args, **kwargs):
        return inner(*args, **kwargs)

    _copy_gs_markers(later_wrapper, inner)
    monkeypatch.setattr(st, "download_button", later_wrapper)
    gs458.install()

    st.download_button(
        "Download Flight Recorder",
        data=lambda: b"fresh",
        key="operator-specified",
        on_click="ignore",
    )
    assert len(fragments) == 1
    assert calls[-1][1]["key"] == "operator-specified"
    assert calls[-1][1]["on_click"] == "ignore"


def test_gs458_rebind_is_idempotent(monkeypatch):
    def leaf_download(*args, **kwargs):
        return None

    monkeypatch.setattr(st, "download_button", leaf_download)
    gs350.install()

    # A later wrapper without GS350's non-inherited owner sentinel simulates the
    # production GS454 boundary.
    inner = st.download_button

    def later_wrapper(*args, **kwargs):
        return inner(*args, **kwargs)

    _copy_gs_markers(later_wrapper, inner)
    monkeypatch.setattr(st, "download_button", later_wrapper)

    gs458.install()
    installed = st.download_button
    gs458.install()
    assert st.download_button is installed


def test_gs458_installs_after_gs454_at_gs448_boundary():
    source = Path("mide/gs448_deferred_flight_recorder_download.py").read_text(
        encoding="utf-8"
    )
    assert "gs458_flight_recorder_fragment_freshness" in source
    assert source.index("install_gs454()") < source.index("install_gs458()")


def test_gs458_scope_lock_is_export_lifecycle_only():
    source = Path("mide/gs458_flight_recorder_fragment_freshness.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "request_scan(",
        "record_scan(",
        "participation_score =",
        "vwap_distance_pct =",
        "place_order(",
        "submit_order(",
    )
    for token in forbidden:
        assert token not in source
    assert 'AUTHORITY = "FLIGHT_RECORDER_FRAGMENT_FRESHNESS_ONLY"' in source
    assert "gs350.install()" in source
