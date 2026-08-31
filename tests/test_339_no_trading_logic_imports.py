from pathlib import Path


def test_gs339_does_not_import_execution_or_scanner_modules():
    source = Path("mide/gs339_preignition_vwap_reclaim.py").read_text().lower()
    forbidden = ("alpaca", "execution", "orders", "scanner import", "architecture import")
    for token in forbidden:
        assert token not in source
