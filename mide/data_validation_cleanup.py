"""Provider-boundary cleanup for live Webull scans.

Keep only the last-mile when-issued symbol guard here. Historical timeframe
capability remains owned by WebullOpenAPIClient so callers receive its explicit
unsupported-timeframe error rather than a silent empty result.
"""
from __future__ import annotations

import re

from . import webull_live

_UNSUPPORTED_SNAPSHOT = re.compile(r"(?:\.|-)WI$", re.IGNORECASE)


def _supported_common_stock_symbol(symbol: object) -> bool:
    value = str(symbol or "").strip().upper()
    return bool(value) and not _UNSUPPORTED_SNAPSHOT.search(value)


webull_live.webull_snapshot_symbol_supported = _supported_common_stock_symbol
