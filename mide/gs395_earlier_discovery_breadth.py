"""GS395: widen Webull discovery before 30-second tripwire analysis.

Live validation on 2026-09-08 showed SST was not discovered until roughly 48 minutes
after its useful intraday structure began. Walter's native radar was only reading the
first 20 rows from each Webull attention list. GS395 adds a bounded second page for
the two feeds closest to the operator's actual tape-reading process:

* 5-MINUTE MOVERS — abrupt price expansion before a symbol reaches top-20 day gainers.
* ABSOLUTE VOLUME — raw share-volume attention, matching the standard Webull screen.

Relative volume remains available as contextual/discovery evidence on its existing
first page, but GS395 does not make RVOL a new ignition authority.

Safety contract:
- first-page DAY_GAINERS / 5-MINUTE / ABSOLUTE_VOLUME / RELATIVE_VOLUME behavior is
  unchanged and remains required;
- page-2 failures are non-fatal and never hide a healthy first-page universe;
- at most 20 *new unique* symbols are admitted from supplemental pages, so Walter's
  discovery universe cannot exceed 100 symbols before downstream filtering;
- no price, float, catalyst, participation, expansion, ranking, readiness, alert,
  execution, or order threshold is changed.
"""
from __future__ import annotations

from functools import wraps
from typing import Any

SUPPLEMENTAL_FEED_KEYS = ("five_minute_movers", "absolute_volume")
SUPPLEMENTAL_PAGE_INDEX = 2
SUPPLEMENTAL_PAGE_SIZE = 20
SUPPLEMENTAL_UNIQUE_CAP = 20
DISCOVERY_CONTRACT_SUFFIX = "PLUS_PAGE2_5MIN_ABSOLUTE_MAX20_UNIQUE"


def _entry_from_row(row: dict[str, Any], key: str) -> dict[str, Any]:
    return {
        "symbol": row["symbol"],
        "name": row.get("name"),
        "price": row.get("price"),
        "change_ratio": row.get("change_ratio"),
        "volume": row.get("volume"),
        "relative_volume_10d": row.get("relative_volume_10d"),
        "sources": [key],
        "ranks": {key: row.get("rank")},
    }


def _merge_existing(entry: dict[str, Any], row: dict[str, Any], key: str) -> None:
    sources = entry.setdefault("sources", [])
    if key not in sources:
        sources.append(key)
    ranks = entry.setdefault("ranks", {})
    rank = row.get("rank")
    if rank is not None:
        prior_rank = ranks.get(key)
        ranks[key] = min(prior_rank, rank) if prior_rank is not None else rank
    for field in ("name", "price", "change_ratio", "volume", "relative_volume_10d"):
        if entry.get(field) is None and row.get(field) is not None:
            entry[field] = row[field]


def extend_report(client: Any, report: dict[str, Any]) -> dict[str, Any]:
    """Add bounded page-2 5m/raw-volume discovery to a healthy native radar report."""
    from . import webull_native_radar as native

    output = dict(report or {})
    base_symbols = [dict(item) for item in list(output.get("symbols") or [])]
    by_symbol = {
        str(item.get("symbol") or "").strip().upper(): item
        for item in base_symbols
        if str(item.get("symbol") or "").strip()
    }
    ordered = list(base_symbols)

    diagnostics: dict[str, dict[str, Any]] = {}
    admitted: list[dict[str, Any]] = []
    if not output.get("all_feeds_available"):
        output["supplemental_breadth"] = {
            "status": "SKIPPED",
            "reason": "Required first-page discovery feed unavailable",
            "feeds": diagnostics,
            "new_unique_symbols": 0,
            "symbols": [],
        }
        return output

    try:
        screener = native._resolve_screener(client)
    except Exception as exc:
        output["supplemental_breadth"] = {
            "status": "CAUTION",
            "reason": f"{type(exc).__name__}: {exc}",
            "feeds": diagnostics,
            "new_unique_symbols": 0,
            "symbols": [],
        }
        return output

    feed_by_key = {feed.key: feed for feed in native.RADAR_FEEDS}
    for key in SUPPLEMENTAL_FEED_KEYS:
        feed = feed_by_key[key]
        method = getattr(screener, feed.operation, None)
        if not callable(method):
            diagnostics[key] = {
                "status": "CAUTION",
                "page_index": SUPPLEMENTAL_PAGE_INDEX,
                "rows_returned": 0,
                "error": f"SDK screener lacks {feed.operation}",
            }
            continue

        arguments = dict(feed.arguments)
        arguments["page_index"] = SUPPLEMENTAL_PAGE_INDEX
        arguments["page_size"] = SUPPLEMENTAL_PAGE_SIZE
        try:
            raw = method(**arguments)
            status_code = getattr(raw, "status_code", None)
            if status_code is not None and int(status_code) >= 400:
                raise RuntimeError(f"Webull screener HTTP {status_code}")
            rows = [
                native._normalize_row(
                    row,
                    rank=SUPPLEMENTAL_PAGE_SIZE + index,
                    source=feed,
                )
                for index, row in enumerate(native._rows(raw), start=1)
            ]
            rows = [row for row in rows if row.get("symbol")][:SUPPLEMENTAL_PAGE_SIZE]
            diagnostics[key] = {
                "status": "PASS",
                "page_index": SUPPLEMENTAL_PAGE_INDEX,
                "rows_returned": len(rows),
                "error": "",
                "symbols": [row["symbol"] for row in rows],
            }

            # Keep provenance for symbols already in page 1, then admit no more than
            # 20 genuinely new names across both supplemental feeds combined.
            for row in rows:
                symbol = str(row.get("symbol") or "").strip().upper()
                if not symbol:
                    continue
                existing = by_symbol.get(symbol)
                if existing is not None:
                    _merge_existing(existing, row, key)
                    continue
                if len(admitted) >= SUPPLEMENTAL_UNIQUE_CAP:
                    continue
                entry = _entry_from_row(row, key)
                by_symbol[symbol] = entry
                ordered.append(entry)
                admitted.append(entry)
        except Exception as exc:
            diagnostics[key] = {
                "status": "CAUTION",
                "page_index": SUPPLEMENTAL_PAGE_INDEX,
                "rows_returned": 0,
                "error": f"{type(exc).__name__}: {exc}",
            }

    output["symbols"] = ordered
    output["unique_symbols"] = len(ordered)
    output["maximum_pre_dedupe_symbols"] = 100
    contract = str(output.get("discovery_contract") or "WEBULL_NATIVE_RADAR")
    if DISCOVERY_CONTRACT_SUFFIX not in contract:
        output["discovery_contract"] = f"{contract}_{DISCOVERY_CONTRACT_SUFFIX}"
    output["supplemental_breadth"] = {
        "status": (
            "PASS"
            if all(
                diagnostics.get(key, {}).get("status") == "PASS"
                for key in SUPPLEMENTAL_FEED_KEYS
            )
            else "CAUTION"
        ),
        "reason": "Bounded page-2 breadth; first-page universe remains authoritative",
        "feeds": diagnostics,
        "new_unique_symbols": len(admitted),
        "symbols": [item["symbol"] for item in admitted],
        "unique_cap": SUPPLEMENTAL_UNIQUE_CAP,
        "maximum_discovery_symbols": 100,
        "relative_volume_role": "context/discovery only; no new ignition authority",
    }
    return output


def install() -> None:
    """Patch the runtime Webull radar binding used by LiveWebullProvider.assets()."""
    from . import webull_connection, webull_native_radar

    current = webull_connection.fetch_native_radar
    if getattr(current, "_gs395_earlier_discovery_breadth", False):
        return

    @wraps(current)
    def fetch_with_breadth(client):
        return extend_report(client, current(client))

    fetch_with_breadth._gs395_earlier_discovery_breadth = True
    fetch_with_breadth._gs395_original = current

    # webull_connection imported the function directly, so update both bindings.
    webull_connection.fetch_native_radar = fetch_with_breadth
    webull_native_radar.fetch_native_radar = fetch_with_breadth
