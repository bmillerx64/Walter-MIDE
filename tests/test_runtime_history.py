from mide.runtime_history import read_runtime_history


def test_read_runtime_history_returns_existing_jsonl_unchanged(tmp_path):
    history = tmp_path / "candidate_history.jsonl"
    contents = b'{"symbol":"TEST"}\n{"symbol":"NEXT"}\n'
    history.write_bytes(contents)

    assert read_runtime_history(history) == contents


def test_read_runtime_history_returns_none_when_file_is_absent(tmp_path):
    assert read_runtime_history(tmp_path / "flight_recorder.jsonl") is None
