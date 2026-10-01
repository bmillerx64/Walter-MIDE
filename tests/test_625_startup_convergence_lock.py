import builtins
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import sleep

from mide import startup


def test_gs625_entering_app_startup_convergence_is_process_serialized(monkeypatch):
    builtins.__dict__.pop(startup._STARTUP_CONVERGENCE_LOCK_KEY, None)

    state_lock = Lock()
    active = 0
    max_active = 0
    sequence = []

    def enter(label):
        nonlocal active, max_active
        with state_lock:
            active += 1
            max_active = max(max_active, active)
            sequence.append((label, "enter"))
        sleep(0.03)

    def leave(label):
        nonlocal active
        with state_lock:
            sequence.append((label, "leave"))
            active -= 1

    def pre():
        enter("pre")
        leave("pre")

    def late():
        enter("late")
        leave("late")

    monkeypatch.setattr(startup, "ensure_pre_app_runtime_installers", pre)
    monkeypatch.setattr(startup, "ensure_late_runtime_installers", late)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(startup.log_startup, "entering app.py"),
            pool.submit(startup.log_startup, "entering app.py"),
        ]
        for future in futures:
            future.result(timeout=2)

    assert max_active == 1
    assert sequence == [
        ("pre", "enter"),
        ("pre", "leave"),
        ("late", "enter"),
        ("late", "leave"),
        ("pre", "enter"),
        ("pre", "leave"),
        ("late", "enter"),
        ("late", "leave"),
    ]


def test_gs625_lock_is_stable_across_helper_calls():
    builtins.__dict__.pop(startup._STARTUP_CONVERGENCE_LOCK_KEY, None)
    first = startup._startup_convergence_lock()
    second = startup._startup_convergence_lock()

    assert first is second


def test_gs625_startup_lock_does_not_touch_scan_or_trading_authority():
    source = open("mide/startup.py", encoding="utf-8").read()
    start = source.index("def _startup_convergence_lock")
    end = source.index("\n\ndef ensure_late_runtime_installers", start)
    block = source[start:end]

    forbidden = (
        "request_scan(",
        "qualified_for_entry",
        "place_order(",
        "submit_order(",
        "execute_order(",
        "participation_score",
        "expansion_score",
    )
    assert not any(token in block for token in forbidden)
