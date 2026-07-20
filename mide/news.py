from __future__ import annotations
import re
from datetime import datetime, timezone

POSITIVE = {
    "fda": 18, "approval": 14, "positive": 8, "contract": 12,
    "purchase order": 12, "partnership": 9, "strategic": 6,
    "patent": 7, "earnings beat": 10, "raises guidance": 12,
    "acquisition": 7, "merger": 5, "clinical": 8, "trial results": 10,
}
NEGATIVE = {
    "offering": -25, "registered direct": -28, "public offering": -30,
    "atm": -18, "at-the-market": -18, "warrant inducement": -22,
    "reverse split": -20, "delisting": -28, "bankruptcy": -40,
    "going concern": -24, "shelf registration": -14,
}

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

def index_news(news_items):
    index = {}
    for item in news_items:
        created = item.get("created_at") or item.get("updated_at")
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except Exception:
            dt = datetime.now(timezone.utc)
        headline = item.get("headline", "")
        catalyst, flags = classify_headline(headline)
        for symbol in item.get("symbols", []) or []:
            entry = {
                "headline": headline,
                "created_at": dt,
                "catalyst_score": catalyst,
                "flags": flags,
                "url": item.get("url", ""),
            }
            if symbol not in index or dt > index[symbol]["created_at"]:
                index[symbol] = entry
    return index
