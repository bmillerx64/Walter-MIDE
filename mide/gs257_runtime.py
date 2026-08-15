"""GS257 runtime corrections for Live Webull discovery and catalyst news.

These corrections stay provider-pure: Webull owns market discovery/data, while
an already-configured FMP credential supplies timestamped catalyst articles until
Webull exposes a permitted raw article feed through OpenAPI.
"""
from __future__ import annotations

import os
from dataclasses import replace


def _streamlit_secret_value() -> str:
    """Resolve FMP from supported Streamlit layouts without logging the value."""
    top_names = (
        "FMP_API_KEY",
        "FINANCIAL_MODELING_PREP_API_KEY",
        "FMP_API",
        "FMP_KEY",
    )
    section_names = (
        "fmp",
        "FMP",
        "financial_modeling_prep",
        "FinancialModelingPrep",
    )
    key_names = ("api_key", "API_KEY", "key", "apikey", "token")

    for name in top_names:
        value = str(os.getenv(name, "") or "").strip()
        if value:
            return value

    try:
        import streamlit as st
        secrets = st.secrets
    except Exception:
        return ""

    for name in top_names:
        try:
            value = str(secrets.get(name, "") or "").strip()
        except Exception:
            value = ""
        if value:
            return value

    for section_name in section_names:
        try:
            section = secrets.get(section_name, {}) or {}
        except Exception:
            section = {}
        for key_name in key_names:
            try:
                value = str(section.get(key_name, "") or "").strip()
            except Exception:
                value = ""
            if value:
                return value
    return ""


def install() -> None:
    """Install credential-safe FMP resolution and deeper Webull radar pagination."""
    from . import news_provider
    from . import webull_native_radar as radar

    # Resolve at NewsService construction time, not package-import time. Streamlit
    # Secrets is fully available by then, including named-table layouts.
    news_provider._configured_fmp_api_key = _streamlit_secret_value

    original_fetch = radar.fetch_native_radar
    if getattr(original_fetch, "_gs257_expanded", False):
        return

    def expanded_fetch_native_radar(client):
        """Collect three pages from each native Webull attention ranking.

        Webull documents page_index/page_size on both native screener families.
        Three 20-row pages per feed keep Walter close to the same market-attention
        source while widening discovery from ~70 unique symbols toward a maximum
        of 240 pre-deduped observations. Twelve screener calls per scan remain far
        below Webull's documented 600 market-data requests/minute limit.
        """
        original_feeds = radar.RADAR_FEEDS
        screener = radar._resolve_screener(client)
        feeds = {}
        deduped = {}

        for feed in original_feeds:
            combined_rows = []
            failure = ""
            method = getattr(screener, feed.operation, None)
            if not callable(method):
                failure = f"SDK screener lacks {feed.operation}"
            else:
                rank_offset = 0
                for page_index in (1, 2, 3):
                    arguments = dict(feed.arguments)
                    arguments["page_index"] = page_index
                    arguments["page_size"] = 20
                    try:
                        raw = method(**arguments)
                        status_code = getattr(raw, "status_code", None)
                        if status_code is not None and int(status_code) >= 400:
                            raise RuntimeError(f"Webull screener HTTP {status_code}")
                        rows = radar._rows(raw)
                    except Exception as exc:
                        failure = f"page {page_index}: {type(exc).__name__}: {exc}"
                        break
                    # A short final page is a normal pagination boundary. Page 1
                    # must contain data because this is an attention-source feed.
                    if not rows:
                        if page_index == 1:
                            failure = (
                                f"Webull {feed.label} returned zero ranking rows; "
                                f"raw_type={type(raw).__name__}"
                            )
                        break
                    normalized = [
                        radar._normalize_row(row, rank=rank_offset + index, source=feed)
                        for index, row in enumerate(rows, start=1)
                    ]
                    normalized = [row for row in normalized if row["symbol"]]
                    combined_rows.extend(normalized)
                    rank_offset += len(normalized)
                    if len(rows) < 20:
                        break

            if failure:
                feeds[feed.key] = {
                    "label": feed.label,
                    "status": "FAIL",
                    "error": failure,
                    "rows": combined_rows,
                }
                continue

            feeds[feed.key] = {
                "label": feed.label,
                "status": "PASS",
                "error": "",
                "rows": combined_rows,
            }
            for row in combined_rows:
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
                for field in (
                    "name",
                    "price",
                    "change_ratio",
                    "volume",
                    "relative_volume_10d",
                ):
                    if entry.get(field) is None and row.get(field) is not None:
                        entry[field] = row[field]

        return {
            "feeds": feeds,
            "unique_symbols": len(deduped),
            "symbols": list(deduped.values()),
            "all_feeds_available": bool(feeds)
            and all(feed["status"] == "PASS" for feed in feeds.values()),
            "pages_requested_per_feed": 3,
        }

    expanded_fetch_native_radar._gs257_expanded = True
    radar.fetch_native_radar = expanded_fetch_native_radar
