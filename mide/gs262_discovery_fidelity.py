"""GS262: make Walter's live discovery universe match the intended Webull radar.

The scan universe is seeded from feeds listed in
``webull_native_radar.DISCOVERY_FEED_KEYS``.  Downstream pre-filters, scoring,
qualification, catalyst evidence, alerts, and execution are unchanged.

Originally only day_gainers + absolute_volume were scanned (GS262 v1).  The
three-feed extension (+ relative_volume) was added to surface early-ignition
small-caps that rank on RVOL before appearing in the gainers list.
"""
from __future__ import annotations


def install() -> None:
    from . import webull_native_radar as radar

    current = radar.fetch_native_radar
    if getattr(current, "_gs262_discovery_fidelity", False):
        return

    # Read feed keys and contract from the canonical constants so this patch
    # stays in sync with webull_native_radar.py without duplicating logic.
    def fidelity_fetch_native_radar(client):
        wanted_keys = radar.DISCOVERY_FEED_KEYS
        screener = radar._resolve_screener(client)
        feed_by_key = {feed.key: feed for feed in radar.RADAR_FEEDS}
        feeds = {}
        deduped = {}
        rejected = []

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
                # Apply minimum gain filter for the relative-volume feed so flat
                # or declining names do not enter the candidate universe.
                # Zero rows after this filter is a normal dead-tape condition —
                # do not treat it as a feed failure.
                if key == "relative_volume":
                    admitted = []
                    for row in rows:
                        if radar._rvol_gain_filter(row):
                            admitted.append(row)
                        else:
                            rejected.append({
                                **row,
                                "entered_active_candidate_universe": False,
                                "discovery_rejection_reason": (
                                    f"relative_volume change_ratio {row['change_ratio']} below "
                                    f"{radar.RVOL_DISCOVERY_MIN_GAIN_PCT}% minimum"
                                ),
                            })
                    rows = admitted
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

        for feed in radar.RADAR_FEEDS:
            if feed.key not in wanted_keys:
                feeds[feed.key] = {"label": feed.label, "status": "NOT_SCANNED",
                                   "error": "Not included in current discovery contract", "rows": []}

        symbols = list(deduped.values())
        return {
            "feeds": feeds,
            "unique_symbols": len(symbols),
            "symbols": symbols,
            "rejected_symbols": rejected,
            "all_feeds_available": all(feeds[key]["status"] == "PASS" for key in wanted_keys),
            "discovery_contract": radar.DISCOVERY_CONTRACT,
            "discovery_feed_keys": list(wanted_keys),
            "maximum_pre_dedupe_symbols": len(wanted_keys) * 20,
            "pages_requested_per_feed": 1,
            "rvol_discovery_min_gain_pct": radar.RVOL_DISCOVERY_MIN_GAIN_PCT,
        }

    fidelity_fetch_native_radar._gs262_discovery_fidelity = True
    radar.fetch_native_radar = fidelity_fetch_native_radar
