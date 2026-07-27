import json

from mide.memory import MemoryStore


def test_memory_store_exports_original_file_and_filters_symbol_history(tmp_path):
    path = tmp_path / "candidate_history.jsonl"
    original = (
        json.dumps({"symbol": "DFNS", "status": "Watching"})
        + "\nnot-json\n"
        + json.dumps({"symbol": "OTHER", "status": "PASS"})
        + "\n"
        + json.dumps({"symbol": "DFNS", "status": "Strengthening"})
        + "\n"
    ).encode()
    path.write_bytes(original)
    store = MemoryStore(path)

    assert store.export_bytes() == original
    assert [item["status"] for item in store.history_for_symbol("dfns")] == [
        "Watching",
        "Strengthening",
    ]


def test_missing_memory_file_exports_empty_bytes(tmp_path):
    store = MemoryStore(tmp_path / "missing" / "history.jsonl")

    assert store.export_bytes() == b""
    assert store.history_for_symbol("DFNS") == []
