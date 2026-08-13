"""Compact replay subsystem status payload for future Diagnostics UI."""

from mide.replay_capabilities import replay_capabilities


def replay_status() -> dict:
    caps = replay_capabilities()
    return {
        "available": True,
        "version": caps["version"],
        "mode": "read-only",
        "integrity": "sha256",
        "production_wiring": False,
    }
