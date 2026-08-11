"""Provider-boundary cleanup for live Webull scans.

Keeps unsupported security suffixes and unsupported 30-second historical calls
out of the live scan path. These are data-capability guards, not trading rules.
"""
from __future__ import annotations

import re

from . import webull_live

_ORIGINAL_BARS = webull_live.WebullOpenAPIClient.bars

# Webull's US_STOCK snapshot endpoint rejects the preferred/share-class forms
# observed in validation (AGM.A, AHL.PRD, WFC.PRL, WFC.PRY, WSO.B). Walter's
# squeeze universe does not need these non-common-stock forms.
_UNSUPPORTED_SNAPSHOT = re.compile(r"[.]|(?:-|[.])WI$", re.IGNORECASE)


def _supported_common_stock_symbol(symbol: object) -> bool:
    value = str(symbol or "").strip().upper()
    return bool(value) and not _UNSUPPORTED_SNAPSHOT.search(value)


def _bars_without_unsupported_30s(self, symbols, **kwargs):
    timeframe = str(kwargs.get("timeframe", "1Min")).strip().lower()
    if timeframe in {"30sec", "30s", "s30"}:
        # Discovery treats an empty 30s frame as unavailable supporting context.
        # Returning cleanly avoids a guaranteed exception/warning from Webull.
        return {}
    return _ORIGINAL_BARS(self, symbols, **kwargs)


webull_live.webull_snapshot_symbol_supported = _supported_common_stock_symbol
webull_live.WebullOpenAPIClient.bars = _bars_without_unsupported_30s
