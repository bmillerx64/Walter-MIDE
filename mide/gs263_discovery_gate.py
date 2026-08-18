"""GS263: accept only the active GS262 discovery feeds at the live-universe gate.

GS262 deliberately marks five-minute movers and relative-volume as NOT_SCANNED.
The older live-universe adapter still treated every non-PASS feed as a provider
failure, making the GS262 contract impossible to satisfy in production.
"""
from __future__ import annotations


def install() -> None:
    from . import webull_connection as connection
    from .webull_live import LiveWebullProvider

    current = LiveWebullProvider.assets
    if getattr(current, "_gs263_discovery_gate", False):
        return

    def gs263_webull_native_assets(self: LiveWebullProvider) -> list[dict]:
        report = connection.fetch_native_radar(self)
        feeds = report.get("feeds", {})
        active_keys = tuple(report.get("discovery_feed_keys") or ())
        if not active_keys:
            active_keys = ("day_gainers", "absolute_volume")

        failed = [
            f"{name}: {(feeds.get(name) or {}).get('error') or 'unavailable'}"
            for name in active_keys
            if (feeds.get(name) or {}).get("status") != "PASS"
        ]
        if failed:
            raise RuntimeError("Webull native discovery unavailable — " + "; ".join(failed))

        assets = []
        for item in report.get("symbols", []):
            symbol = str(item.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            assets.append({
                "symbol": symbol,
                "name": item.get("name") or "",
                "tradable": True,
                "status": "active",
                "exchange": item.get("exchange") or "",
                "otc": False,
                "webull_native_sources": list(item.get("sources") or []),
                "webull_native_ranks": dict(item.get("ranks") or {}),
            })
        if not assets:
            raise RuntimeError("Webull native discovery returned zero symbols after deduplication")

        # Cache radar prices for initialize_quotes fallback when REST snapshot
        # returns no usable data (e.g. API format mismatch or transient failure).
        self._native_radar_prices = {
            str(item.get("symbol") or "").strip().upper(): item
            for item in report.get("symbols", [])
            if str(item.get("symbol") or "").strip() and item.get("price") is not None
        }
        diagnostics = self.diagnostics.setdefault("webull_native_discovery", {})
        diagnostics.update({
            "provider": "Webull OpenAPI SDK",
            "mode": "native_market_attention",
            "alpaca_universe_used": False,
            "feed_count": len(active_keys),
            "unique_symbols": len(assets),
            "discovery_feed_keys": list(active_keys),
            "feed_status": {
                name: {
                    "status": feed.get("status"),
                    "returned": len(feed.get("rows") or []),
                    "error": feed.get("error") or "",
                }
                for name, feed in feeds.items()
            },
        })
        self.diagnostics["broad_source"] = "Webull native market attention"
        self.diagnostics.setdefault("market_data_sources", {})["universe_provider"] = (
            "Webull OpenAPI SDK native radar"
        )
        self._walter_native_universe_active = True
        return assets

    gs263_webull_native_assets._walter_webull_native_discovery = True
    gs263_webull_native_assets._gs263_discovery_gate = True
    connection._webull_native_assets = gs263_webull_native_assets
    LiveWebullProvider.assets = gs263_webull_native_assets
