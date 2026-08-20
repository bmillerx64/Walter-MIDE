"""Backward-compatible import surface for Walter's authoritative settings.

Runtime code should prefer ``mide.config``.  Legacy modules that still import
``config.Settings`` now receive the exact same class and mission contract instead
of maintaining a second, drifting copy.
"""

from mide.config import MISSION_MAX_PRICE, MISSION_MIN_PRICE, Settings

__all__ = ["Settings", "MISSION_MIN_PRICE", "MISSION_MAX_PRICE"]
