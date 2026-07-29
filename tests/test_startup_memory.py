import logging

from mide import startup_memory


def test_checkpoint_reports_rss_delta_and_owner(monkeypatch, caplog):
    readings = iter((10 * 1024 * 1024, 35 * 1024 * 1024))
    monkeypatch.setattr(startup_memory, "_last_rss_bytes", None)
    monkeypatch.setattr(startup_memory, "_largest_jump", None)
    monkeypatch.setattr(startup_memory, "resident_memory_bytes", lambda: next(readings))

    startup_memory.checkpoint("baseline")
    with caplog.at_level(logging.WARNING, logger="walter.startup"):
        result = startup_memory.checkpoint("provider", object_name="pandas")

    assert result == {
        "step": "provider",
        "rss_bytes": 35 * 1024 * 1024,
        "delta_bytes": 25 * 1024 * 1024,
        "dramatic": True,
    }
    assert startup_memory.largest_jump() == ("provider", 25 * 1024 * 1024)
    assert "object=pandas" in caplog.text
