import json

import mide.memory_profile as memory_profile


def test_profile_reports_requested_categories_and_five_bounded_scans(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_profile, "PROFILE_PATH", tmp_path / "profile.json")
    memory_profile._scan_rss.clear()
    readings = iter((100, 101, 102, 103, 104))
    monkeypatch.setattr(memory_profile, "resident_memory_bytes", lambda: next(readings) * 1024 * 1024)

    state = {"records": [{"symbol": "WALT", "score": 90}], "cache_result": {"x": 1}}
    for number in range(5):
        report = memory_profile.profile(
            f"scan {number + 1}", session_state=state, structures={"records": state["records"]}
        )

    assert report["five_scan_stable"] is True
    assert len(report["cache_sizes"]["scan_rss_bytes"]) == 5
    assert len(report["top_20_memory_consumers"]) <= 20
    assert report["object_counts"]
    assert report["largest_data_structures"][0]["bytes"] > 0
    assert report["session_state"]["bytes"] > 0
    assert json.loads(memory_profile.PROFILE_PATH.read_text())["scan 5"]["five_scan_stable"]


def test_compact_previous_record_drops_unconsumed_bulk_data():
    compact = memory_profile.compact_previous_record({
        "symbol": "WALT", "conviction_score": 81, "minute_bars": [object()] * 1000
    })
    assert compact == {"symbol": "WALT", "conviction_score": 81}


def test_release_temporaries_clears_growing_scan_containers():
    global_like_list = [{"scan": number} for number in range(100)]
    global_like_map = {str(number): object() for number in range(100)}
    memory_profile.release_temporaries(global_like_list, global_like_map)
    assert global_like_list == []
    assert global_like_map == {}
