from pathlib import Path

from mide import gs408_preserve_completed_scan_during_rerun as gs408


class FakeSlot:
    def __init__(self):
        self.entered = 0
        self.exited = 0
        self.calls = []

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, exc_type, exc, tb):
        self.exited += 1
        return False

    def markdown(self, *args, **kwargs):
        self.calls.append((args, kwargs))


class FakeStreamlit:
    def __init__(self):
        self.empty_calls = 0
        self.slots = []

    def empty(self):
        self.empty_calls += 1
        slot = FakeSlot()
        self.slots.append(slot)
        return slot


def test_exact_app_dashboard_assignments_are_deferred_targets():
    for name in gs408.DASHBOARD_SLOT_NAMES:
        assert gs408.dashboard_slot_name("/mount/src/walter-mide/app.py", f"{name} = st.empty()") == name


def test_non_dashboard_or_non_app_empty_calls_are_not_targets():
    assert gs408.dashboard_slot_name("/mount/src/walter-mide/app.py", "other_slot = st.empty()") is None
    assert gs408.dashboard_slot_name("/tmp/test_app.py", "mission_header_slot = st.empty()") is None
    assert gs408.dashboard_slot_name("/mount/src/walter-mide/app.py", "mission_header_slot = st.container()") is None


def test_target_placeholder_emits_nothing_until_new_view_is_rendered(monkeypatch):
    st = FakeStreamlit()
    monkeypatch.setattr(gs408, "_dashboard_slot_name_from_callsite", lambda: "mission_header_slot")
    gs408.install(st)

    slot = st.empty()
    assert isinstance(slot, gs408.LazyEmptySlot)
    assert not slot.resolved
    assert st.empty_calls == 0

    with slot as realized:
        realized.markdown("new completed scan")

    assert slot.resolved
    assert st.empty_calls == 1
    assert st.slots[0].entered == 1
    assert st.slots[0].exited == 1
    assert st.slots[0].calls[0][0] == ("new completed scan",)


def test_direct_method_use_also_resolves_exactly_once(monkeypatch):
    st = FakeStreamlit()
    monkeypatch.setattr(gs408, "_dashboard_slot_name_from_callsite", lambda: "scan_trust_slot")
    gs408.install(st)

    slot = st.empty()
    slot.markdown("first")
    slot.markdown("second")

    assert st.empty_calls == 1
    assert [call[0] for call in st.slots[0].calls] == [("first",), ("second",)]


def test_unrelated_empty_preserves_native_behavior(monkeypatch):
    st = FakeStreamlit()
    monkeypatch.setattr(gs408, "_dashboard_slot_name_from_callsite", lambda: None)
    gs408.install(st)

    slot = st.empty()
    assert isinstance(slot, FakeSlot)
    assert st.empty_calls == 1


def test_install_is_idempotent():
    st = FakeStreamlit()
    gs408.install(st)
    first = st.empty
    gs408.install(st)
    assert st.empty is first
    assert getattr(st.empty, "_gs408_preserve_completed_scan", False)


def test_gs408_installs_after_gs407_and_does_not_change_app_trading_logic():
    source = Path("mide/gs392_operator_order_audio.py").read_text()
    assert source.index("install_gs407()") < source.index("install_gs408()")

    module_source = Path("mide/gs408_preserve_completed_scan_during_rerun.py").read_text()
    forbidden = (
        "participation_score =",
        "qualified_for_entry =",
        "qualified_for_alert =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "candidate_status =",
    )
    assert not any(token in module_source for token in forbidden)
