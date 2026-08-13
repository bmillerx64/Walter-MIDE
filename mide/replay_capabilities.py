"""Capability discovery for Walter's replay subsystem."""

from mide.replay_contract import replay_contract
from mide.replay_version import REPLAY_SUBSYSTEM_VERSION


def replay_capabilities() -> dict:
    return {
        "version": REPLAY_SUBSYSTEM_VERSION,
        "contract": replay_contract(),
        "supports_scan_id_lookup": True,
        "supports_latest_symbol_lookup": True,
        "supports_integrity_audit": True,
        "supports_portable_export": True,
    }
