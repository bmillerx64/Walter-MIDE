from pathlib import Path

import mide.gs450_release_startup_tracemalloc as gs450


class FakeTracer:
    def __init__(self, tracing=False):
        self.tracing = tracing
        self.stop_calls = 0

    def is_tracing(self):
        return self.tracing

    def start(self, *_args, **_kwargs):
        self.tracing = True

    def stop(self):
        self.stop_calls += 1
        self.tracing = False


class FakeMemoryProfileModule:
    def __init__(self, tracer):
        self.tracemalloc = tracer


def test_startup_profile_releases_tracing_it_started():
    tracer = FakeTracer(False)
    module = FakeMemoryProfileModule(tracer)

    def current(label, *, session_state=None, structures=None):
        assert label == "startup"
        tracer.start(1)
        return {"label": label, "full": True}

    report = gs450.profile_and_release(current, module, "startup")

    assert report == {"label": "startup", "full": True}
    assert tracer.stop_calls == 1
    assert tracer.is_tracing() is False


def test_preexisting_external_tracing_is_preserved():
    tracer = FakeTracer(True)
    module = FakeMemoryProfileModule(tracer)

    def current(label, *, session_state=None, structures=None):
        return {"label": label}

    gs450.profile_and_release(current, module, "startup")

    assert tracer.stop_calls == 0
    assert tracer.is_tracing() is True


def test_non_startup_profile_does_not_override_historical_trace_lifecycle():
    tracer = FakeTracer(False)
    module = FakeMemoryProfileModule(tracer)

    def current(label, *, session_state=None, structures=None):
        tracer.start(1)
        return {"label": label}

    gs450.profile_and_release(current, module, "scan 1")

    # GS450 deliberately does nothing for scan labels; the historical profiler owns
    # their start/stop lifecycle. This fake current omits its normal stop to prove
    # GS450 does not broaden its authority.
    assert tracer.stop_calls == 0
    assert tracer.is_tracing() is True


def test_gs450_installs_immediately_after_gs449():
    startup = Path("mide/startup.py").read_text(encoding="utf-8")

    assert "from .gs450_release_startup_tracemalloc import install as install_gs450" in startup
    assert startup.index("install_gs449()") < startup.index("install_gs450()")
    assert startup.index("install_gs450()") < startup.index("install_gs416()")


def test_legacy_startup_profiler_really_leaves_tracing_active_without_gs450():
    source = Path("mide/memory_profile.py").read_text(encoding="utf-8")

    assert "tracemalloc.start(1)" in source
    assert 'if label.startswith("scan"):' in source
    assert "tracemalloc.stop()" in source
    # There is no corresponding startup-label stop in the legacy implementation.
    assert 'if label.startswith("startup")' not in source


def test_gs450_scope_lock_is_observability_only():
    source = Path("mide/gs450_release_startup_tracemalloc.py").read_text(
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
        "begin_scheduled_scan(",
        "finish_scan(",
        "place_order(",
    )
    assert not any(token in source for token in forbidden)
    assert 'AUTHORITY = "OBSERVABILITY_COST_CONTAINMENT_ONLY"' in source
