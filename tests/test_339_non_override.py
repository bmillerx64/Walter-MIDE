from pathlib import Path


def test_gs339_source_preserves_stronger_language():
    source = Path("mide/gs339_preignition_vwap_reclaim.py").read_text()
    for token in ("MOMENTUM IGNITING", "LOOK NOW", "ENTRY", "CHASE", "RESET REQUIRED"):
        assert token in source
