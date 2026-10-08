"""GS655: persistent Fresh Catalyst Flash from Walter's live news cache.

This is an operator-awareness surface only. It consumes already-completed GS620
news-cache state and never performs provider I/O, changes discovery membership,
scores/ranking, readiness, entry authority, execution, or orders.

The sidebar is intentionally used as the persistent surface because Streamlit's
main trading pane can be scrolled far below the top while the sidebar remains in
view. A new, very fresh high-confidence catalyst also emits a one-time Streamlit
toast so the operator can notice it while focused elsewhere in Walter.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any, Iterable

UTC = timezone.utc
AUTHORITY = "NEWS_AWARENESS_ONLY"
VISIBLE_WINDOW = timedelta(minutes=30)
TOAST_WINDOW = timedelta(minutes=8)
MAX_VISIBLE = 3

_EVENT_LABELS = {
    "CONTRACT_ORDER": "CONTRACT / ORDER",
    "PARTNERSHIP_EXPANSION": "PARTNERSHIP",
    "M_AND_A_INVESTMENT": "M&A / INVESTMENT",
    "REGULATORY_CLINICAL": "REGULATORY / CLINICAL",
    "FINANCIAL_GROWTH": "FINANCIAL GROWTH",
    "IP_LICENSE": "IP / LICENSE",
    "NON_DILUTIVE_FUNDING": "NON-DILUTIVE FUNDING",
}

_EVENT_WEIGHT = {
    "CONTRACT_ORDER": 70,
    "REGULATORY_CLINICAL": 68,
    "M_AND_A_INVESTMENT": 66,
    "PARTNERSHIP_EXPANSION": 58,
    "FINANCIAL_GROWTH": 54,
    "IP_LICENSE": 50,
    "NON_DILUTIVE_FUNDING": 46,
}


def _utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        stamp = value
    else:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return stamp.astimezone(UTC)


def _now(value=None) -> datetime:
    current = value() if callable(value) else value
    current = current or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return current.astimezone(UTC)


def _quantity_bonus(context: dict) -> tuple[int, str]:
    """Reward stated deal/funding scale without inferring valuation or price."""
    best = 0.0
    label = ""
    for item in context.get("quantities") or []:
        if not isinstance(item, dict) or not item.get("currency"):
            continue
        role = str(item.get("role") or "")
        if role not in {
            "DEAL_OR_BACKLOG",
            "INVESTMENT_OR_FUNDING",
            "REVENUE",
        }:
            continue
        try:
            value = float(item.get("normalized_value") or 0)
        except (TypeError, ValueError):
            continue
        if value > best:
            best = value
            label = str(item.get("text") or "").strip()

    if best >= 100_000_000:
        return 28, label
    if best >= 25_000_000:
        return 22, label
    if best >= 5_000_000:
        return 16, label
    if best >= 1_000_000:
        return 10, label
    return 0, label


def _article_identity(article: Any, symbol: str) -> str:
    article_id = str(getattr(article, "id", "") or "").strip()
    if article_id:
        return f"{symbol}:{article_id}"
    stamp = _utc(getattr(article, "created_at", None))
    headline = str(getattr(article, "headline", "") or "").strip()
    return f"{symbol}:{stamp.isoformat() if stamp else 'unknown'}:{headline}"


def catalyst_flash_rows(
    articles: Iterable[Any],
    *,
    now=None,
    visible_window: timedelta = VISIBLE_WINDOW,
    limit: int = MAX_VISIBLE,
) -> list[dict]:
    """Return the freshest high-confidence material catalysts for operator awareness."""
    from mide.authorities.discovery_news import story_intelligence
    from mide.discovery import is_valid_us_symbol
    from mide.news import MATERIAL_CATALYST_SCORE, classify_headline, trusted_catalyst_source

    current = _now(now)
    cutoff = current - visible_window
    best_by_symbol: dict[str, dict] = {}

    for article in articles or []:
        created = _utc(getattr(article, "created_at", None))
        if created is None or created < cutoff or created > current + timedelta(minutes=2):
            continue

        headline = " ".join(str(getattr(article, "headline", "") or "").split())
        if not headline:
            continue
        source = str(getattr(article, "source", "") or "").strip()
        provider = str(getattr(article, "provider", "") or "").strip()
        if not trusted_catalyst_source(source):
            continue

        story_text = str(getattr(article, "_walter_story_text", "") or "")
        context = story_intelligence(headline, story_text)
        if context.get("risk_categories"):
            continue

        score, flags = classify_headline(headline)
        categories = [
            category
            for category in context.get("positive_attention_categories") or []
            if category in _EVENT_LABELS
        ]
        if not categories and float(score or 0) < MATERIAL_CATALYST_SCORE:
            continue
        # Roundups/attention-only stories are discovery aids, not News Flash events.
        if context.get("attention_only_categories") and not categories:
            continue

        primary_category = max(
            categories,
            key=lambda category: _EVENT_WEIGHT.get(category, 0),
            default="",
        )
        category_weight = _EVENT_WEIGHT.get(primary_category, 40)
        quantity_bonus, quantity_label = _quantity_bonus(context)
        age_seconds = max(0.0, (current - created).total_seconds())
        age_minutes = age_seconds / 60.0
        importance = (
            category_weight
            + quantity_bonus
            + min(20, max(0, int(float(score or 0))))
        )

        for raw_symbol in getattr(article, "symbols", []) or []:
            symbol = str(raw_symbol or "").strip().upper()
            if not is_valid_us_symbol(symbol):
                continue
            row = {
                "authority": AUTHORITY,
                "symbol": symbol,
                "headline": headline,
                "source": source,
                "provider": provider,
                "created_at": created,
                "age_seconds": round(age_seconds, 1),
                "age_minutes": round(age_minutes, 1),
                "event_category": primary_category or "MATERIAL_CATALYST",
                "event_label": _EVENT_LABELS.get(primary_category, "MATERIAL CATALYST"),
                "quantity_label": quantity_label,
                "catalyst_score": float(score or 0),
                "catalyst_flags": list(flags),
                "importance": importance,
                "signature": _article_identity(article, symbol),
                "trading_authority_changed": False,
            }
            previous = best_by_symbol.get(symbol)
            if previous is None:
                best_by_symbol[symbol] = row
                continue
            # Prefer the newer story unless the timestamps tie, then keep stronger.
            previous_created = previous["created_at"]
            if created > previous_created or (
                created == previous_created
                and importance > int(previous.get("importance") or 0)
            ):
                best_by_symbol[symbol] = row

    rows = list(best_by_symbol.values())
    # Freshness is the first job of this surface. Importance breaks near-time ties.
    rows.sort(
        key=lambda row: (
            row["created_at"],
            int(row.get("importance") or 0),
            row["symbol"],
        ),
        reverse=True,
    )
    return rows[: max(1, int(limit))]


def live_catalyst_flash_rows(*, now=None, limit: int = MAX_VISIBLE) -> tuple[list[dict], dict]:
    """Read only GS620's completed process cache; never schedule or wait on news I/O."""
    from mide import gs620_live_news_stream as gs620

    current = _now(now)
    articles, trace = gs620.cache_snapshot(now=current)
    rows = catalyst_flash_rows(articles, now=current, limit=limit)
    return rows, {
        "authority": AUTHORITY,
        "source_authority": trace.get("authority"),
        "cache_articles": int(trace.get("cache_articles") or 0),
        "newest_article_at": trace.get("newest_article_at"),
        "realtime_transport": trace.get("realtime_transport") or {},
        "flash_count": len(rows),
        "provider_requests": 0,
        "scan_blocked": False,
        "trading_authority_changed": False,
    }


def _age_text(row: dict) -> str:
    try:
        age = float(row.get("age_minutes") or 0)
    except (TypeError, ValueError):
        age = 0.0
    if age < 1:
        return "<1m"
    return f"{int(round(age))}m"


def _display_headline(value: str, limit: int = 132) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def render_fresh_catalyst_sidebar(st, session_state, *, now=None) -> list[dict]:
    """Render the no-scroll News Flash surface and one-time fresh-event toast."""
    current = _now(now)
    try:
        rows, trace = live_catalyst_flash_rows(now=current)
    except Exception as exc:
        st.caption(f"⚡ News Flash unavailable · {type(exc).__name__}")
        return []

    if not rows:
        st.caption("⚡ News Flash · live catalyst cache armed")
        return []

    lead = rows[0]
    quantity = f" · {escape(str(lead.get('quantity_label') or ''))}" if lead.get("quantity_label") else ""
    st.markdown(
        (
            '<div style="margin-top:0.10rem;padding:0.58rem 0.68rem;'
            'border:2px solid #f5b700;border-radius:0.55rem;'
            'background:rgba(245,183,0,0.10);line-height:1.25;">'
            '<div style="font-weight:800;color:#ffd34e;letter-spacing:.02em;">'
            '⚡ FRESH CATALYST</div>'
            f'<div style="font-size:1.02rem;font-weight:800;margin-top:.25rem;">'
            f'{escape(str(lead["symbol"]))} · {escape(str(lead["event_label"]))}'
            f'{quantity} · {_age_text(lead)}</div>'
            f'<div style="font-size:.88rem;margin-top:.28rem;">'
            f'{escape(_display_headline(str(lead["headline"])))}</div>'
            f'<div style="font-size:.72rem;opacity:.72;margin-top:.25rem;">'
            f'{escape(str(lead.get("source") or lead.get("provider") or "live news"))}'
            ' · awareness only</div>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )

    if len(rows) > 1:
        also = " · ".join(
            f"{row['symbol']} {_age_text(row)}"
            for row in rows[1:MAX_VISIBLE]
        )
        st.caption(f"Also fresh: {also}")

    signature_key = "_walter_gs655_last_news_flash_toast"
    signature = str(lead.get("signature") or "")
    last_signature = str(session_state.get(signature_key) or "")
    try:
        age_seconds = float(lead.get("age_seconds") or 0)
    except (TypeError, ValueError):
        age_seconds = 0.0
    if (
        signature
        and signature != last_signature
        and age_seconds <= TOAST_WINDOW.total_seconds()
    ):
        if hasattr(st, "toast"):
            st.toast(
                f"{lead['symbol']} · {lead['event_label']} · {_display_headline(lead['headline'], 96)}",
                icon="⚡",
            )
        session_state[signature_key] = signature

    session_state["_walter_gs655_news_flash_trace"] = trace
    return rows


__all__ = [
    "AUTHORITY",
    "VISIBLE_WINDOW",
    "TOAST_WINDOW",
    "MAX_VISIBLE",
    "catalyst_flash_rows",
    "live_catalyst_flash_rows",
    "render_fresh_catalyst_sidebar",
]
