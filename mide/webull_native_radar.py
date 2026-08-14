"""Read-only Webull native market-attention probe.

GS252 validates the replacement discovery path before Walter uses it for live
candidate selection. It calls Webull's official screener operations only and
never changes discovery, filtering, ranking, scoring, readiness, alerts, or
execution behavior.
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
    RadarFeed(
        "day_gainers",
        "DAY GAINERS",
        "get_gainers_losers",
        {
            "rank_type": "DAY_1",
            "category": "US_STOCK",
            "sort_by": "CHANGE_RATIO",
            "direction": "DESC",
            "page_index": 1,
            "page_size": 20,
        },
    ),
    RadarFeed(
        "five_minute_movers",
        "5-MINUTE MOVERS",
        "get_gainers_losers",
        {
            "rank_type": "MIN_5",
            "category": "US_STOCK",
            "sort_by": "CHANGE_RATIO",
            "direction": "DESC",
            "page_index": 1,
            "page_size": 20,
        },
    ),
    RadarFeed(
        "relative_volume",
        "RELATIVE VOLUME",
        "get_most_active",
        {
            "category": "US_STOCK",
            "rank_type": "RELATIVE_VOLUME_10D",
            "sort_by": "RELATIVE_VOLUME_10D",
            "direction": "DESC",
            "page_index": 1,
            "page_size": 20,
        },
    ),
    RadarFeed(
        "absolute_volume",
        "ABSOLUTE VOLUME",
        "get_most_active",
        {
            "category": "US_STOCK",
            "rank_type": "VOLUME",
            "sort_by": "VOLUME",
            "direction": "DESC",
            "page_index": 1,
            "page_size": 20,
        },
    ),
)


def _plain(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _rows(value: Any) -> list[dict[str, Any]]:
    value = _plain(value)
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if not isinstance(value, dict):
        return []
    for key in ("data", "result", "items", "list", "rows"):
        child = value.get(key)
        if isinstance(child, list):
            return [row for row in child if isinstance(row, dict)]
        if isinstance(child, dict):
            nested = _rows(child)
            if nested:
                return nested
    return []


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _resolve_screener(client: Any) -> Any:
    """Resolve the official SDK screener object from Walter or raw SDK clients."""
    objects = [client]
    snapshot_client = getattr(client, "_snapshot_client", None)
    if snapshot_client is not None:
        objects.append(snapshot_client)
    for obj in tuple(objects):
        sdk = getattr(obj, "sdk", None)
        if sdk is not None:
            objects.append(sdk)
    for obj in tuple(objects):
        raw = getattr(obj, "sdk_client", None)
        if raw is not None:
            objects.append(raw)

    for obj in objects:
        for candidate in (
            getattr(obj, "screener", None),
            getattr(getattr(obj, "data", None), "screener", None),
            getattr(getattr(obj, "market_data", None), "screener", None),
        ):
            if candidate is not None:
                return candidate
        if callable(getattr(obj, "get_gainers_losers", None)) and callable(
            getattr(obj, "get_most_active", None)
        ):
            return obj
    raise RuntimeError(
        "Installed Webull SDK exposes no screener object with "
        "get_gainers_losers/get_most_active"
    )


def _normalize_row(row: dict[str, Any], *, rank: int, source: RadarFeed) -> dict[str, Any]:
    return {
        "rank": rank,
        "symbol": str(
            row.get("symbol")
            or row.get("ticker")
            or row.get("ticker_symbol")
            or ""
        ).upper(),
        "name": row.get("name") or row.get("instrument_name") or row.get("display_name"),
        "price": _number(row.get("price") or row.get("close") or row.get("last_price")),
        "change": _number(row.get("change")),
        "change_ratio": _number(row.get("change_ratio") or row.get("pct_change")),
        "volume": _number(row.get("volume") or row.get("total_volume")),
        "relative_volume_10d": _number(
            row.get("relative_volume_10d") or row.get("relative_volume") or row.get("rvol")
        ),
        "market_value": _number(row.get("market_value") or row.get("market_cap")),
        "turnover_rate": _number(row.get("turnover_rate")),
        "amplitude": _number(row.get("amplitude")),
        "instrument_id": row.get("instrument_id") or row.get("ticker_id"),
        "source_feed": source.key,
        "source_label": source.label,
    }


def fetch_native_radar(client: Any) -> dict[str, Any]:
    """Fetch four official Webull market-attention lists without mutating Walter."""
    screener = _resolve_screener(client)
    feeds: dict[str, dict[str, Any]] = {}
    deduped: dict[str, dict[str, Any]] = {}

    for feed in RADAR_FEEDS:
        method: Callable[..., Any] | None = getattr(screener, feed.operation, None)
        if not callable(method):
            feeds[feed.key] = {
                "label": feed.label,
                "status": "FAIL",
                "error": f"SDK screener lacks {feed.operation}",
                "rows": [],
            }
            continue
        try:
            raw = method(**feed.arguments)
            normalized = [
                _normalize_row(row, rank=index, source=feed)
                for index, row in enumerate(_rows(raw), start=1)
            ]
            normalized = [row for row in normalized if row["symbol"]]
            feeds[feed.key] = {
                "label": feed.label,
                "status": "PASS",
                "error": "",
                "rows": normalized,
            }
            for row in normalized:
                symbol = row["symbol"]
                entry = deduped.setdefault(
                    symbol,
                    {
                        "symbol": symbol,
                        "name": row.get("name"),
                        "price": row.get("price"),
                        "change_ratio": row.get("change_ratio"),
                        "volume": row.get("volume"),
                        "relative_volume_10d": row.get("relative_volume_10d"),
                        "sources": [],
                        "ranks": {},
                    },
                )
                if feed.key not in entry["sources"]:
                    entry["sources"].append(feed.key)
                entry["ranks"][feed.key] = row["rank"]
                for field in ("name", "price", "change_ratio", "volume", "relative_volume_10d"):
                    if entry.get(field) is None and row.get(field) is not None:
                        entry[field] = row[field]
        except Exception as exc:
            feeds[feed.key] = {
                "label": feed.label,
                "status": "FAIL",
                "error": f"{type(exc).__name__}: {exc}",
                "rows": [],
            }

    return {
        "feeds": feeds,
        "unique_symbols": len(deduped),
        "symbols": list(deduped.values()),
        "all_feeds_available": bool(feeds) and all(
            feed["status"] == "PASS" for feed in feeds.values()
        ),
    }


def radar_probe_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Compact connection-test rows suitable for Walter's existing diagnostics table."""
    output = []
    for feed in RADAR_FEEDS:
        result = report.get("feeds", {}).get(feed.key, {})
        rows = result.get("rows", [])
        output.append(
            {
                "Test": f"Native radar — {feed.label}",
                "Status": result.get("status", "FAIL"),
                "Provider": "Webull OpenAPI SDK",
                "Endpoint / SDK operation": f"screener.{feed.operation}",
                "Request count": 1,
                "Returned symbol count": len(rows),
                "First 10 returned symbols": ", ".join(
                    row.get("symbol", "") for row in rows[:10]
                ),
                "Latency ms": None,
                "Actual exception / API error": result.get("error", ""),
            }
        )
    return output
