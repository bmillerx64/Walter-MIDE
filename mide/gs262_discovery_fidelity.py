"""GS262: make Walter's live discovery universe match the intended Webull radar.

The live scan is seeded only from the current top-20 day gainers and top-20
absolute-volume leaders.  This is discovery-source fidelity only; downstream
prefilters, scoring, qualification, catalyst evidence, alerts and execution are
unchanged.
"""
from __future__ import annotations


def install() -> None:
    from . import webull_native_radar as radar

    current = radar.fetch_native_radar
    if getattr(current, "_gs262_discovery_fidelity", False):
        return

    wanted_keys = ("day_gainers", "absolute_volume")

    def fidelity_fetch_native_radar(client):
        screener = radar._resolve_screener(client)
        feed_by_key = {feed.key: feed for feed in radar.RADAR_FEEDS}
        feeds = {}
        deduped = {}

        for key in wanted_keys:
            feed = feed_by_key[key]
            method = getattr(screener, feed.operation, None)
            if not callable(method):
                feeds[key] = {"label": feed.label, "status": "FAIL",
                              "error": f"SDK screener lacks {feed.operation}", "rows": []}
                continue
            try:
                args = dict(feed.arguments)
                args["page_index"] = 1
                args["page_size"] = 20
                raw = method(**args)
                status_code = getattr(raw, "status_code", None)
                if status_code is not None and int(status_code) >= 400:
                    raise RuntimeError(f"Webull screener HTTP {status_code}")
                rows = [
                    radar._normalize_row(row, rank=index, source=feed)
                    for index, row in enumerate(radar._rows(raw), start=1)
                ]
                rows = [row for row in rows if row["symbol"]][:20]
                if not rows:
                    raise RuntimeError(f"Webull {feed.label} returned zero ranking rows")
                feeds[key] = {"label": feed.label, "status": "PASS", "error": "", "rows": rows}
                for row in rows:
                    symbol = row["symbol"]
                    entry = deduped.setdefault(symbol, {
                        "symbol": symbol, "name": row.get("name"), "price": row.get("price"),
                        "change_ratio": row.get("change_ratio"), "volume": row.get("volume"),
                        "relative_volume_10d": row.get("relative_volume_10d"),
                        "sources": [], "ranks": {},
                    })
                    if key not in entry["sources"]:
                        entry["sources"].append(key)
                    entry["ranks"][key] = row["rank"]
                    for field in ("name", "price", "change_ratio", "volume", "relative_volume_10d"):
                        if entry.get(field) is None and row.get(field) is not None:
                            entry[field] = row[field]
            except Exception as exc:
                feeds[key] = {"label": feed.label, "status": "FAIL",
                              "error": f"{type(exc).__name__}: {exc}", "rows": []}

        # Preserve explicit diagnostics for feeds deliberately excluded from the
        # scan so the UI/logs can explain why a symbol did or did not enter.
        for feed in radar.RADAR_FEEDS:
            if feed.key not in wanted_keys:
                feeds[feed.key] = {"label": feed.label, "status": "NOT_SCANNED",
                                   "error": "Excluded by GS262 discovery contract", "rows": []}

        symbols = list(deduped.values())
        return {
            "feeds": feeds,
            "unique_symbols": len(symbols),
            "symbols": symbols,
            "all_feeds_available": all(feeds[key]["status"] == "PASS" for key in wanted_keys),
            "discovery_contract": "WEBULL_TOP20_DAY_GAINERS_PLUS_TOP20_ABSOLUTE_VOLUME",
            "discovery_feed_keys": list(wanted_keys),
            "maximum_pre_dedupe_symbols": 40,
            "pages_requested_per_feed": 1,
        }

    fidelity_fetch_native_radar._gs262_discovery_fidelity = True
    radar.fetch_native_radar = fidelity_fetch_native_radar
