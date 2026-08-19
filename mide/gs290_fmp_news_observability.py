"""GS290 read-only FMP news observability helpers.

This module formats NewsService metrics already produced by the acquisition
pipeline. It does not fetch data and cannot gate, rank, score, suppress,
promote, alert, or execute candidates.
"""
from __future__ import annotations


def fmp_news_audit_rows(metrics: dict | None) -> list[dict]:
    """Return deterministic per-symbol rows from NewsService diagnostics."""
    metrics = metrics or {}
    trace = metrics.get("newest_articles_by_symbol") or {}
    rows: list[dict] = []
    for symbol in sorted(trace):
        item = trace.get(symbol) or {}
        returned = int(item.get("articles_returned") or 0)
        material_count = int(item.get("material_article_count") or 0)
        selected = item.get("selected_material_headline")
        if not returned:
            disposition = "NO ARTICLES RETURNED"
        elif selected:
            disposition = "MATERIAL CATALYST SELECTED"
        elif material_count:
            disposition = "MATERIAL ARTICLE OBSERVED"
        else:
            disposition = "NON-MATERIAL / NOT SELECTED"
        rows.append({
            "symbol": symbol,
            "articles_returned": returned,
            "newest_age_minutes": item.get("newest_article_age_minutes"),
            "newest_headline": item.get("newest_headline"),
            "source": item.get("newest_source"),
            "provider": item.get("newest_provider"),
            "catalyst_score": item.get("newest_catalyst_score"),
            "catalyst_flags": list(item.get("newest_catalyst_flags") or []),
            "material_article_count": material_count,
            "selected_material_headline": selected,
            "selected_material_score": item.get("selected_material_score"),
            "selected_material_flags": list(item.get("selected_material_flags") or []),
            "disposition": disposition,
        })
    return rows


def fmp_news_audit_summary(metrics: dict | None) -> dict:
    """Expose request provenance plus compact counts for operator diagnostics."""
    metrics = metrics or {}
    rows = fmp_news_audit_rows(metrics)
    return {
        "active_provider": metrics.get("active_provider") or "None",
        "requested_symbols": list(metrics.get("requested_symbols") or []),
        "query_since": metrics.get("query_since"),
        "effective_provider_since": metrics.get("effective_provider_since"),
        "provider_endpoints": list(metrics.get("provider_endpoints") or []),
        "requests_made": int(metrics.get("requests_made") or 0),
        "articles_received": int(metrics.get("articles_received") or 0),
        "symbols_with_articles": list(metrics.get("symbols_with_articles") or []),
        "symbols_without_articles": list(metrics.get("symbols_without_articles") or []),
        "symbols_audited": len(rows),
        "symbols_with_material": sum(bool(row["material_article_count"]) for row in rows),
        "symbols_with_selected_material": sum(bool(row["selected_material_headline"]) for row in rows),
        "rows": rows,
        "diagnostic_only": True,
    }
