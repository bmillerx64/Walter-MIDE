from pathlib import Path

import mide.gs449_bound_startup_memory_profile as gs449
import mide.memory_profile as memory_profile


def test_repeated_startup_profile_runs_full_profiler_once(monkeypatch):
    gs449.reset_for_tests()
    calls = []

    def original(label, *, session_state=None, structures=None):
        calls.append((label, session_state, structures))
        return {"label": label, "rss_bytes": 123, "full": True}

    monkeypatch.setattr(memory_profile, "resident_memory_bytes", lambda: 456)
    state = {"growing_history": list(range(1000))}

    first = gs449.bounded_profile(
        original,
        memory_profile,
        "startup",
        session_state=state,
    )
    second = gs449.bounded_profile(
        original,
        memory_profile,
        "startup",
        session_state={"growing_history": list(range(5000))},
    )

    assert first == {"label": "startup", "rss_bytes": 123, "full": True}
    assert len(calls) == 1
    assert second["label"] == "startup"
    assert second["rss_bytes"] == 456
    assert second["gs449_mode"] == "lightweight_repeat_startup"
    assert second["full_profile_skipped"] is True
    assert second["trading_logic_changed"] is False


def test_non_startup_profiles_remain_full_and_repeatable():
    gs449.reset_for_tests()
    calls = []

    def original(label, *, session_state=None, structures=None):
        calls.append(label)
        return {"label": label, "full": True}

    assert gs449.bounded_profile(original, memory_profile, "scan 1")["full"] is True
    assert gs449.bounded_profile(original, memory_profile, "scan 2")["full"] is True
    assert calls == ["scan 1", "scan 2"]


def test_gs449_install_is_idempotent_and_patches_profile_binding():
    gs449.install()
    first = memory_profile.profile
    gs449.install()

    assert memory_profile.profile is first
    assert getattr(first, "_gs449_bound_startup_memory_profile", False)
    assert getattr(first, "_gs449_authority", "") == gs449.AUTHORITY


def test_gs449_activates_before_app_imports_profile_alias():
    startup = Path("mide/startup.py").read_text(encoding="utf-8")
    app = Path("app.py").read_text(encoding="utf-8")

    assert "from .gs449_bound_startup_memory_profile import install as install_gs449" in startup
    assert startup.index("install_gs449()") < startup.index("install_gs416()")
    assert app.index('log_startup("entering app.py")') < app.index(
        "from mide.memory_profile import compact_previous_record, profile as memory_profile"
    )
    assert app.index('memory_profile("startup", session_state=st.session_state)') < app.index(
        "should_scan = False"
    )


def test_gs449_targets_the_known_pre_dispatch_o_n_profiler_without_changing_it():
    source = Path("mide/memory_profile.py").read_text(encoding="utf-8")
    gs449_source = Path("mide/gs449_bound_startup_memory_profile.py").read_text(
        encoding="utf-8"
    )

    # The diagnosed legacy startup cost really does contain all of these process/session
    # size-dependent operations; GS449 avoids repeating them rather than weakening them.
    assert "tracemalloc.take_snapshot()" in source
    assert "snapshot.statistics(\"lineno\")" in source
    assert "gc.get_objects()" in source
    assert "deep_size(session_state or {})" in source
    assert "PROFILE_PATH.write_text" in source
    assert 'label == "startup" and _full_startup_profile_complete' in gs449_source


def test_gs449_scope_lock_is_observability_only():
    source = Path("mide/gs449_bound_startup_memory_profile.py").read_text(
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
