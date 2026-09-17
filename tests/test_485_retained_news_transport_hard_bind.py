from __future__ import annotations

from pathlib import Path

from mide import gs427_flight_recorder_latency_hard_bind as gs427
from mide import gs484_fmp_transport_truth as gs484
from mide import gs485_retained_news_transport_hard_bind as gs485


def _retained_function():
    globals_dict = {
        "__name__": "mide.gs481_live_evidence_hard_bind",
        "_news_truth": lambda: {"marketwide_count": 0},
    }
    exec(
        "def persist_replayable_scan(recorder, scan, records, *args, **kwargs):\n"
        "    return _news_truth()\n",
        globals_dict,
    )
    function = globals_dict["persist_replayable_scan"]
    function._gs481_live_evidence_hard_bind = True
    return globals_dict, function


def test_install_patches_exact_retained_gs481_function_globals(monkeypatch):
    retained_globals, retained = _retained_function()
    active = {"persist_replayable_scan": retained}
    provider = object()

    monkeypatch.setattr(gs427, "_active_recorder_globals", lambda: active)
    monkeypatch.setattr(gs427, "_active_provider", lambda: (provider, "retained-test"))
    monkeypatch.setattr(
        gs484,
        "transport_truth",
        lambda observed: {
            "authority": "OBSERVATIONAL_ONLY",
            "transport_disposition": "SUCCESS_EMPTY",
            "provider_matches": observed is provider,
        },
    )

    patched = gs485.install()
    truth = retained_globals["_news_truth"]()

    assert patched >= 1
    assert truth["transport"]["transport_disposition"] == "SUCCESS_EMPTY"
    assert truth["transport"]["provider_matches"] is True
    assert truth["transport"]["provider_source"] == "retained-test"
    assert truth["transport"]["retained_runtime_hard_bind"] is True
    assert truth["gs484_transport_truth"] is True
    assert truth["gs485_retained_transport_hard_bind"] is True


def test_install_is_idempotent_for_same_retained_globals(monkeypatch):
    retained_globals, retained = _retained_function()
    monkeypatch.setattr(
        gs427,
        "_active_recorder_globals",
        lambda: {"persist_replayable_scan": retained},
    )
    monkeypatch.setattr(gs427, "_active_provider", lambda: (None, "none"))
    monkeypatch.setattr(gs484, "transport_truth", lambda provider: {"x": 1})

    gs485.install()
    once = retained_globals["_news_truth"]
    gs485.install()
    twice = retained_globals["_news_truth"]

    assert once is twice


def test_retained_patch_does_not_invoke_provider_transport_until_trace_is_read(monkeypatch):
    retained_globals, retained = _retained_function()
    calls = []
    monkeypatch.setattr(
        gs427,
        "_active_recorder_globals",
        lambda: {"persist_replayable_scan": retained},
    )
    monkeypatch.setattr(gs427, "_active_provider", lambda: (None, "none"))
    monkeypatch.setattr(
        gs484,
        "transport_truth",
        lambda provider: calls.append(provider) or {"extra_provider_calls": 0},
    )

    gs485.install()
    assert calls == []
    retained_globals["_news_truth"]()
    assert calls == [None]


def test_app_entry_reasserts_gs485_after_gs484():
    source = Path("app.py").read_text()
    assert "_install_gs485_retained_news_transport()" in source
    assert source.index("_install_gs484_fmp_transport_truth()") < source.index(
        "_install_gs485_retained_news_transport()"
    )


def test_startup_orders_gs485_after_gs484_before_resource_containment():
    source = Path("mide/startup.py").read_text()
    body = source.split("def ensure_late_runtime_installers() -> None:", 1)[1]
    assert "gs485_retained_news_transport_hard_bind" in source
    assert body.index("install_gs484()") < body.index("install_gs485()") < body.index(
        "install_gs483()"
    )


def test_scope_lock_is_observability_only():
    source = Path("mide/gs485_retained_news_transport_hard_bind.py").read_text()
    assert "AUTHORITY = \"OBSERVATIONAL_ONLY\"" in source
    assert "requests.get(" not in source
    assert "requests.post(" not in source
    assert "qualified_for_entry" not in source
    assert "execute_order" not in source
