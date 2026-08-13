from mide.replay_capabilities import replay_capabilities


def test_replay_capabilities_are_explicit():
    caps = replay_capabilities()
    assert caps["version"] == "1.0.0"
    assert caps["supports_scan_id_lookup"]
    assert caps["supports_latest_symbol_lookup"]
    assert caps["supports_integrity_audit"]
    assert caps["supports_portable_export"]
