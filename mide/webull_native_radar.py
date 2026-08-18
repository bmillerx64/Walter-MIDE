"""Read-only Webull native market-attention discovery.

Universe seeding uses three complementary feeds:

* DAY_GAINERS  – top-20 by % change today; captures names that are already
  running and draws in breakout continuations.
* ABSOLUTE_VOLUME – top-20 by raw share volume; catches high-float names with
  institutional participation that may not lead on % change.
* RELATIVE_VOLUME – top-20 by 10-day RVOL; catches early-ignition small-caps
  whose absolute volume is still modest but whose relative surge is the first
  detectable signal of accumulation.  This is the primary pre-ignition feed.

Five-minute movers are retained in RADAR_FEEDS for diagnostics/history but
are NOT included in DISCOVERY_FEED_KEYS because they duplicate day-gainers
for already-running symbols and add noise without early-detection benefit.

The relative_volume feed requires a minimum +2 % gain filter enforced during
snapshot enrichment to prevent low-float names with unusual but directionless
activity from being promoted as candidates.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class RadarFeed:
    key: str
    label: str
    operation: str
    arguments: dict[str, Any]


RADAR_FEEDS = (
    RadarFeed("day_gainers", "DAY GAINERS", "get_gainers_losers",
              {"rank_type": "DAY_1", "category": "US_STOCK", "sort_by": "CHANGE_RATIO", "direction": "DESC", "page_index": 1, "page_size": 20}),
    RadarFeed("five_minute_movers", "5-MINUTE MOVERS", "get_gainers_losers",
              {"rank_type": "MIN_5", "category": "US_STOCK", "sort_by": "CHANGE_RATIO", "direction": "DESC", "page_index": 1, "page_size": 20}),
    RadarFeed("relative_volume", "RELATIVE VOLUME", "get_most_active",
              {"category": "US_STOCK", "rank_type": "RELATIVE_VOLUME_10D", "sort_by": "RELATIVE_VOLUME_10D", "direction": "DESC", "page_index": 1, "page_size": 20}),
    RadarFeed("absolute_volume", "ABSOLUTE VOLUME", "get_most_active",
              {"category": "US_STOCK", "rank_type": "VOLUME", "sort_by": "VOLUME", "direction": "DESC", "page_index": 1, "page_size": 20}),
)

# relative_volume is added as the third discovery feed to surface pre-ignition
# names before they reach the top of the day-gainers list.  All three feeds are
# de-duplicated in fetch_native_radar so a symbol appearing in multiple feeds
# counts once.
DISCOVERY_FEED_KEYS = ("day_gainers", "absolute_volume", "relative_volume")
DISCOVERY_CONTRACT = "WEBULL_TOP20_DAY_GAINERS_PLUS_TOP20_ABSOLUTE_VOLUME_PLUS_TOP20_RELATIVE_VOLUME"

# Minimum intraday gain a relative-volume discovery must show before it is
# treated as a directional candidate.  Prevents flat-tape names with unusual
# volume from being promoted unnecessarily.
RVOL_DISCOVERY_MIN_GAIN_PCT: float = 2.0


def _plain(value: Any) -> Any:
    if hasattr(value, "to_dict"): value = value.to_dict()
    if hasattr(value, "model_dump"): value = value.model_dump()
    json_method = getattr(value, "json", None)
    if callable(json_method):
        try: value = json_method()
        except Exception: pass
    if isinstance(value, bytes): return value.decode("utf-8", errors="replace")
    if isinstance(value, dict): return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [_plain(v) for v in value]
    return value


def _rows(value: Any) -> list[dict[str, Any]]:
    value = _plain(value)
    if isinstance(value, list): return [r for r in value if isinstance(r, dict)]
    if not isinstance(value, dict): return []
    for key in ("data", "result", "items", "list", "rows"):
        child = value.get(key)
        if isinstance(child, list): return [r for r in child if isinstance(r, dict)]
        if isinstance(child, dict):
            nested = _rows(child)
            if nested: return nested
    return []


def _number(value: Any) -> float | None:
    try: return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError): return None


def _resolve_screener(client: Any) -> Any:
    queue, seen = [client], set()
    attributes = ("_snapshot_client", "sdk", "sdk_client", "data", "market_data", "market_data_api", "screener")
    while queue:
        obj = queue.pop(0)
        if obj is None or id(obj) in seen: continue
        seen.add(id(obj))
        if callable(getattr(obj, "get_gainers_losers", None)) and callable(getattr(obj, "get_most_active", None)):
            return obj
        for name in attributes:
            nested = getattr(obj, name, None)
            if nested is not None and id(nested) not in seen: queue.append(nested)
    raise RuntimeError("Installed Webull SDK exposes no screener object with get_gainers_losers/get_most_active")


def _normalize_row(row: dict[str, Any], *, rank: int, source: RadarFeed) -> dict[str, Any]:
    return {"rank": rank, "symbol": str(row.get("symbol") or row.get("ticker") or row.get("ticker_symbol") or "").upper(),
            "name": row.get("name") or row.get("instrument_name") or row.get("display_name"),
            "price": _number(row.get("price") or row.get("close") or row.get("last_price")), "change": _number(row.get("change")),
            "change_ratio": _number(row.get("change_ratio") or row.get("pct_change")), "volume": _number(row.get("volume") or row.get("total_volume")),
            "relative_volume_10d": _number(row.get("relative_volume_10d") or row.get("relative_volume") or row.get("rvol")),
            "market_value": _number(row.get("market_value") or row.get("market_cap")), "turnover_rate": _number(row.get("turnover_rate")),
            "amplitude": _number(row.get("amplitude")), "instrument_id": row.get("instrument_id") or row.get("ticker_id"),
            "source_feed": source.key, "source_label": source.label}


def fetch_native_radar(client: Any) -> dict[str, Any]:
    screener = _resolve_screener(client)
    feed_by_key = {feed.key: feed for feed in RADAR_FEEDS}
    feeds, deduped = {}, {}
    for key in DISCOVERY_FEED_KEYS:
        feed = feed_by_key[key]
        method: Callable[..., Any] | None = getattr(screener, feed.operation, None)
        if not callable(method):
            feeds[key] = {"label": feed.label, "status": "FAIL", "error": f"SDK screener lacks {feed.operation}", "rows": []}
            continue
        try:
            raw = method(**feed.arguments)
            status_code = getattr(raw, "status_code", None)
            if status_code is not None and int(status_code) >= 400: raise RuntimeError(f"Webull screener HTTP {status_code}")
            normalized = [_normalize_row(row, rank=i, source=feed) for i, row in enumerate(_rows(raw), start=1)]
            normalized = [row for row in normalized if row["symbol"]][:20]
            # The relative-volume feed surfaces names with anomalous activity
            # regardless of direction.  Apply a minimum gain filter so that
            # flat or declining names do not enter the candidate universe.
            if key == "relative_volume":
                normalized = [
                    row for row in normalized
                    if (row.get("change_ratio") or 0) >= RVOL_DISCOVERY_MIN_GAIN_PCT
                    or (row.get("change_ratio") is None)  # keep if gain unavailable; Stage 2 will filter
                ]
            if not normalized: raise RuntimeError(f"Webull {feed.label} returned zero ranking rows; raw_type={type(raw).__name__}")
            feeds[key] = {"label": feed.label, "status": "PASS", "error": "", "rows": normalized}
            for row in normalized:
                symbol = row["symbol"]
                entry = deduped.setdefault(symbol, {"symbol": symbol, "name": row.get("name"), "price": row.get("price"), "change_ratio": row.get("change_ratio"), "volume": row.get("volume"), "relative_volume_10d": row.get("relative_volume_10d"), "sources": [], "ranks": {}})
                if key not in entry["sources"]: entry["sources"].append(key)
                entry["ranks"][key] = row["rank"]
                for field in ("name", "price", "change_ratio", "volume", "relative_volume_10d"):
                    if entry.get(field) is None and row.get(field) is not None: entry[field] = row[field]
        except Exception as exc:
            feeds[key] = {"label": feed.label, "status": "FAIL", "error": f"{type(exc).__name__}: {exc}", "rows": []}
    for feed in RADAR_FEEDS:
        if feed.key not in DISCOVERY_FEED_KEYS:
            feeds[feed.key] = {"label": feed.label, "status": "NOT_SCANNED", "error": "Not included in current discovery contract", "rows": []}
    symbols = list(deduped.values())
    return {"feeds": feeds, "unique_symbols": len(symbols), "symbols": symbols,
            "all_feeds_available": all(feeds[k]["status"] == "PASS" for k in DISCOVERY_FEED_KEYS),
            "discovery_contract": DISCOVERY_CONTRACT, "discovery_feed_keys": list(DISCOVERY_FEED_KEYS),
            "maximum_pre_dedupe_symbols": 60, "pages_requested_per_feed": 1,
            "rvol_discovery_min_gain_pct": RVOL_DISCOVERY_MIN_GAIN_PCT}


def radar_probe_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    for feed in RADAR_FEEDS:
        result = report.get("feeds", {}).get(feed.key, {})
        rows = result.get("rows", [])
        output.append({"Test": f"Native radar — {feed.label}", "Status": result.get("status", "FAIL"), "Provider": "Webull OpenAPI SDK",
                       "Endpoint / SDK operation": f"screener.{feed.operation}", "Request count": 1 if feed.key in DISCOVERY_FEED_KEYS else 0,
                       "Returned symbol count": len(rows), "First 10 returned symbols": ", ".join(row.get("symbol", "") for row in rows[:10]),
                       "Latency ms": None, "Actual exception / API error": result.get("error", "")})
    return output
