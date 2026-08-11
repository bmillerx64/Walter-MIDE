from __future__ import annotations
import re
from datetime import datetime, timedelta, timezone

from .flight_recorder import prefilter_decision

POSITIVE = {
    "fda": 18, "approval": 14, "positive": 8, "contract": 12,
    "purchase order": 12, "partnership": 9, "strategic": 6,
    "patent": 7, "earnings beat": 10, "raises guidance": 12,
    "acquisition": 7, "merger": 5, "clinical": 8, "trial results": 10,
    "agreement": 8, "award": 10, "selected": 7, "collaboration": 8,
    "milestone": 7, "authorization": 12, "clearance": 14, "license": 8,
}
NEGATIVE = {
    "offering": -25, "registered direct": -28, "public offering": -30,
    "atm": -18, "at-the-market": -18, "warrant inducement": -22,
    "reverse split": -20, "delisting": -28, "bankruptcy": -40,
    "going concern": -24, "shelf registration": -14,
}

MATERIAL_CATALYST_SCORE = 7


def classify_headline(headline: str):
    text = (headline or "").lower()
    score = 0
    flags = []
    for phrase, weight in POSITIVE.items():
        if phrase in text:
            score += weight
            flags.append(phrase)
    for phrase, weight in NEGATIVE.items():
        if phrase in text:
            score += weight
            flags.append(phrase)
    return max(-40, min(30, score)), flags


def _news_timestamp(item: dict) -> datetime | None:
    raw = item.get("created_at") or item.get("updated_at")
    if isinstance(raw, datetime):
        value = raw
    else:
        try:
            value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def index_news(news_items):
    """Choose the freshest material event per symbol, not merely the last headline.

    A neutral follow-up article should not hide a still-fresh contract, approval,
    award, trial result, or other material event.  When multiple material events
    exist, the newest one wins, so a later financing/offering headline can still
    supersede an earlier positive catalyst.  If no material event exists, Walter
    falls back to the newest headline exactly as before.
    """
    grouped: dict[str, list[dict]] = {}
    for item in news_items:
        dt = _news_timestamp(item) or datetime.now(timezone.utc)
        headline = item.get("headline", "")
        catalyst, flags = classify_headline(headline)
        for raw_symbol in item.get("symbols", []) or []:
            symbol = str(raw_symbol or "").strip().upper()
            if not symbol:
                continue
            grouped.setdefault(symbol, []).append({
                "headline": headline,
                "created_at": dt,
                "catalyst_score": catalyst,
                "flags": flags,
                "url": item.get("url", ""),
                "source": item.get("source") or item.get("author") or "",
                "provider": item.get("provider") or "",
            })

    index = {}
    for symbol, entries in grouped.items():
        material = [
            entry for entry in entries
            if abs(float(entry.get("catalyst_score") or 0)) >= MATERIAL_CATALYST_SCORE
        ]
        pool = material or entries
        index[symbol] = max(pool, key=lambda entry: entry["created_at"])
    return index


def recent_wire_news_log(
    news_items,
    *,
    snapshots,
    analyzed,
    records,
    settings,
    now: datetime | None = None,
    max_age_minutes: int = 90,
) -> list[dict]:
    """Build one auditable scanner outcome per symbol with fresh wire news.

    Alpaca can return several articles for a symbol. The newest qualifying Reuters
    or Benzinga article wins so the log remains a symbol log rather than an
    article feed. This is diagnostic-only and never changes scanner decisions.
    """
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = now - timedelta(minutes=max_age_minutes)
    newest = {}
    for item in news_items or []:
        source = str(item.get("source") or item.get("author") or "").strip()
        normalized_source = source.casefold()
        if "reuters" not in normalized_source and "benzinga" not in normalized_source:
            continue
        published = _news_timestamp(item)
        if published is None or not cutoff <= published <= now:
            continue
        canonical_source = "Reuters" if "reuters" in normalized_source else "Benzinga"
        score, _flags = classify_headline(item.get("headline", ""))
        for raw_symbol in item.get("symbols", []) or []:
            symbol = str(raw_symbol or "").strip().upper()
            if not symbol:
                continue
            candidate = {
                "source": canonical_source,
                "timestamp": published,
                "score": score,
            }
            if symbol not in newest or published > newest[symbol]["timestamp"]:
                newest[symbol] = candidate

    analyzed_by_symbol = {item.get("symbol"): item for item in analyzed or []}
    records_by_symbol = {item.get("symbol"): item for item in records or []}
    output = []
    for symbol, article in sorted(newest.items()):
        snapshot = (snapshots or {}).get(symbol)
        prefilter = (
            prefilter_decision(symbol, snapshot, settings)
            if snapshot is not None
            else {"passed": False, "reason": "snapshot unavailable"}
        )
        record = records_by_symbol.get(symbol)
        participation = (record or {}).get("participation_gate") or {}
        participation_passed = bool(participation.get("passed"))
        expansion = float((record or {}).get("expansion_quality", 0) or 0)
        expansion_passed = record is not None and expansion >= 58

        state = (record or {}).get("candidate_status") or (record or {}).get("status")
        if not prefilter["passed"] or record is None:
            final_state = "Ignored" if not prefilter["passed"] else "Candidate"
        elif state == "Entry Ready":
            final_state = "Entry Ready"
        elif state == "Strengthening":
            final_state = "Strengthening"
        elif state in {"Watching", "Emerging", "Watch List"}:
            final_state = "Watch"
        elif participation_passed:
            final_state = "Candidate"
        else:
            final_state = "Ignored"

        rejected = None
        if not prefilter["passed"]:
            rejected = prefilter["reason"]
        elif symbol not in analyzed_by_symbol:
            rejected = "Scanner analysis unavailable: insufficient or missing bar data"
        elif not participation_passed:
            rejected = "; ".join(participation.get("failed_reasons") or []) or (
                (record or {}).get("rejection_reason") or "Participation gate failed"
            )
        elif not expansion_passed:
            rejected = f"Expansion Quality {expansion:.0f}/100 (requires 58)"

        output.append(
            {
                "Ticker": symbol,
                "News source": article["source"],
                "News timestamp": article["timestamp"].isoformat(),
                "News score": article["score"],
                "Prefilter": "PASS" if prefilter["passed"] else "FAIL",
                "Participation": "PASS" if participation_passed else "FAIL",
                "Expansion": "PASS" if expansion_passed else "FAIL",
                "Final state": final_state,
                "Reason if rejected": rejected,
            }
        )
    return output
