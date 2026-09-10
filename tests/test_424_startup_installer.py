from __future__ import annotations

from mide import startup
from mide.webull_live import LiveWebullProvider


def test_late_runtime_installers_activate_gs424_provider_cache():
    startup.ensure_late_runtime_installers()
    assert getattr(LiveWebullProvider.bars, "_gs424_warm_scan_history_cache", False) is True
