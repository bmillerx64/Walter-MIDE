"""GS550: shadow-news I/O never blocks Walter's live scan."""

from pathlib import Path
import threading
import time

from mide import gs550_nonblocking_shadow_news as gs550


ROOT = Path(__file__).resolve().parents[1]


class Client:
    def __init__(self):
        self.diagnostics = {}


def _wait_for(predicate, timeout=1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_gs550_returns_while_shadow_worker_is_still_blocked():
    client = Client()
    started = threading.Event()
    release = threading.Event()

    def observer(_client, symbols, news):
        started.set()
        release.wait(1.0)
        return {
            "authority": "NEWS_COVERAGE_OBSERVATION_ONLY",
            "request_made": True,
            "found_symbols": list(symbols),
            "trading_authority_changed": False,
        }

    runtime = gs550.schedule_observation(
        client,
        client,
        observer,
        ["TEST"],
        [],
        facade_used=True,
    )

    assert started.wait(0.5)
    assert runtime["status"] == "running"
    assert runtime["scan_blocked"] is False

    second = gs550.schedule_observation(
        client,
        client,
        observer,
        ["TEST"],
        [],
        facade_used=True,
    )
    assert second["worker_reused"] is True

    release.set()
    assert _wait_for(
        lambda: client.diagnostics.get("gs550_shadow_news_runtime", {}).get("status")
        == "completed"
    )
    trace = client.diagnostics["gs544_alpaca_news_shadow"]
    assert trace["request_made"] is True
    assert trace["found_symbols"] == ["TEST"]
    assert trace["warm_deploy_news_facade_used"] is True
    assert trace["nonblocking_scan_authority"] == gs550.AUTHORITY
    assert trace["scan_blocked"] is False


def test_gs550_failure_is_diagnostic_only_and_does_not_escape_worker():
    client = Client()

    def broken(*_args, **_kwargs):
        raise RuntimeError("synthetic shadow outage")

    runtime = gs550.schedule_observation(
        client,
        client,
        broken,
        ["TEST"],
        [],
    )

    assert runtime["scan_blocked"] is False
    assert _wait_for(
        lambda: client.diagnostics.get("gs550_shadow_news_runtime", {}).get("status")
        == "failed"
    )
    trace = client.diagnostics["gs544_alpaca_news_shadow"]
    assert "synthetic shadow outage" in trace["reason"]
    assert trace["request_made"] is False
    assert trace["trading_authority_changed"] is False


def test_gs550_app_schedules_shadow_observation_instead_of_waiting_for_it():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = source.index("# GS544: observe only")
    end = source.index("        decisions = {}", start)
    block = source[start:end]

    assert "mide.gs550_nonblocking_shadow_news" in block
    assert "schedule_observation(" in block
    assert "observe_shadow," in block
    assert "shadow_trace = observe_shadow(" not in block
    assert "news_items.extend" not in block
    assert "news_items.append" not in block
    assert "indexed.update" not in block


def test_gs550_scope_is_observation_only():
    source = (
        ROOT / "mide/gs550_nonblocking_shadow_news.py"
    ).read_text(encoding="utf-8")

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "expansion_score =",
        "opportunity_state =",
        "place_order(",
        "submit_order(",
    )
    assert not any(token in source for token in forbidden)
