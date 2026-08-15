"""GS258: hard-cut Walter's live UI and provider state to Webull only.

This overlay removes Live Alpaca from selectable modes and severs the obsolete
universe-client reference inside LiveWebullProvider. Webull native radar remains
the discovery source installed by webull_connection; FMP remains catalyst-only.
"""
from __future__ import annotations


def install() -> None:
    from . import webull_live

    def webull_only_modes(*, alpaca_configured: bool, webull_configured: bool):
        # Keep the legacy keyword in the signature so existing callers do not
        # change, but it cannot expose or select Alpaca anymore.
        del alpaca_configured
        modes = ["Live Webull", "Demo"]
        return (modes, 0) if webull_configured else (modes, 1)

    webull_only_modes._gs258_webull_only = True
    webull_live.live_data_modes = webull_only_modes

    cls = webull_live.LiveWebullProvider
    original_init = cls.__init__
    if getattr(original_init, "_gs258_webull_only", False):
        return

    def webull_only_init(self, *args, **kwargs):
        # app.py may still pass a legacy Alpaca symbol-master object while the
        # old constructor seam is being retired. Explicitly discard it so the
        # Live Webull provider cannot retain, call, or report that source.
        kwargs["universe_client"] = None
        original_init(self, *args, **kwargs)
        self._universe_client = None
        sources = self.diagnostics.setdefault("market_data_sources", {})
        sources["universe_provider"] = "Webull OpenAPI SDK native radar"
        sources["quote_provider"] = "Webull OpenAPI SDK"
        sources["bars_provider"] = "Webull OpenAPI SDK"
        sources["streaming_provider"] = "Webull OpenAPI SDK"
        self.diagnostics["alpaca_runtime_enabled"] = False
        self.diagnostics["alpaca_universe_used"] = False

    webull_only_init._gs258_webull_only = True
    cls.__init__ = webull_only_init
