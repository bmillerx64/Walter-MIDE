"""Low-overhead resident-memory checkpoints for Walter startup diagnostics."""

from __future__ import annotations

import logging
import os


_LOGGER = logging.getLogger("walter.startup")
_last_rss_bytes: int | None = None
_largest_jump: tuple[str, int] | None = None
DRAMATIC_JUMP_BYTES = int(os.getenv("WALTER_MEMORY_JUMP_MIB", "20")) * 1024 * 1024


def resident_memory_bytes() -> int:
    """Return current process RSS without importing a monitoring dependency."""
    try:
        with open("/proc/self/status", encoding="ascii") as status:
            for line in status:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return 0


def checkpoint(step: str, *, object_name: str | None = None) -> dict[str, int | str | bool]:
    """Log RSS and its change since the preceding startup checkpoint."""
    global _last_rss_bytes, _largest_jump
    rss = resident_memory_bytes()
    delta = 0 if _last_rss_bytes is None else rss - _last_rss_bytes
    _last_rss_bytes = rss
    if _largest_jump is None or delta > _largest_jump[1]:
        _largest_jump = (step, delta)
    dramatic = delta >= DRAMATIC_JUMP_BYTES
    owner = f" object={object_name}" if object_name else ""
    _LOGGER.warning(
        "startup_memory step=%s rss_mib=%.1f delta_mib=%+.1f dramatic=%s%s",
        step,
        rss / 1024 / 1024,
        delta / 1024 / 1024,
        dramatic,
        owner,
    )
    return {"step": step, "rss_bytes": rss, "delta_bytes": delta, "dramatic": dramatic}


def largest_jump() -> tuple[str, int] | None:
    """Expose the largest observed jump for diagnostics and tests."""
    return _largest_jump
