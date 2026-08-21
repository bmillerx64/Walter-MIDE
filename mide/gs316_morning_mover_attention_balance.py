"""GS316: reserve bounded discovery capacity for fresh morning-mover roundups.

Fresh pre-market mover/watch-list stories are useful because they identify symbols
already attracting market attention, even when the article itself is neutral and
contains no company-specific catalyst. GS298/GS306 already recognize these stories
as attention-only discovery seeds; this layer prevents a busy material-news tape
from crowding all of them out of the bounded news-seed set.

Safety boundary: this changes only which news-derived symbol identities are allowed
into the normal discovery seed list. Morning-mover rows remain attention-only and
receive zero catalyst credit. Price, validity, float, participation, expansion,
ranking, readiness, trigger, and execution behavior are unchanged.
"""
from __future__ import annotations

from typing import Iterable

MORNING_MOVER_RESERVE = 8


def _seed_type(item: dict) -> str:
    return str(item.get("seed_type") or "")


def _age_minutes(item: dict) -> float:
    try:
        return float(item.get("age_minutes") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def balance_attention_seeds(selected: Iterable[dict], *, limit: int) -> list[dict]:
    """Return a bounded mix that preserves fresh morning-attention visibility.

    Material catalysts keep first claim on the list, but up to eight slots are
    reserved for the freshest morning-mover/watch-list attention seeds when they
    exist. The function never changes catalyst scores or converts attention into
    catalyst evidence.
    """
    cap = max(0, int(limit))
    if cap == 0:
        return []

    rows = [dict(item) for item in (selected or [])]
    material = [row for row in rows if _seed_type(row) == "material_catalyst"]
    attention = [row for row in rows if _seed_type(row) == "morning_mover_attention"]
    other = [
        row
        for row in rows
        if _seed_type(row) not in {"material_catalyst", "morning_mover_attention"}
    ]

    material.sort(
        key=lambda row: (
            float(row.get("catalyst_score") or 0.0),
            -_age_minutes(row),
            str(row.get("symbol") or ""),
        ),
        reverse=True,
    )
    attention.sort(
        key=lambda row: (
            -_age_minutes(row),
            str(row.get("symbol") or ""),
        ),
        reverse=True,
    )

    reserve = min(MORNING_MOVER_RESERVE, cap, len(attention))
    material_budget = max(0, cap - reserve)
    output = material[:material_budget]
    output.extend(attention[:reserve])

    used = {str(row.get("symbol") or "").upper() for row in output}
    remainder = material[material_budget:] + attention[reserve:] + other
    remainder.sort(
        key=lambda row: (
            _seed_type(row) == "material_catalyst",
            _seed_type(row) == "morning_mover_attention",
            float(row.get("catalyst_score") or 0.0),
            -_age_minutes(row),
            str(row.get("symbol") or ""),
        ),
        reverse=True,
    )
    for row in remainder:
        symbol = str(row.get("symbol") or "").upper()
        if symbol and symbol in used:
            continue
        output.append(row)
        if symbol:
            used.add(symbol)
        if len(output) >= cap:
            break

    for row in output:
        if _seed_type(row) == "morning_mover_attention":
            row["attention_priority"] = "HIGH" if _age_minutes(row) <= 180 else "NORMAL"
            row["attention_reason"] = "fresh morning mover/watch-list mention"
        else:
            row.setdefault("attention_priority", "NORMAL")
    return output[:cap]


def install() -> None:
    """Wrap the existing news selector without altering downstream gate semantics."""
    from . import gs298_news_seeded_discovery as seeded

    original = seeded.select_material_news_seeds
    if getattr(original, "_gs316_installed", False):
        return

    def select_material_news_seeds(articles, *, now=None, limit=seeded.NEWS_SEED_LIMIT):
        # Inspect the full entitled feed first so the normal bounded result can
        # reserve space for fresh morning-mover attention when the tape is busy.
        expanded_limit = max(int(limit), seeded.NEWS_FEED_LIMIT)
        selected = original(articles, now=now, limit=expanded_limit)
        return balance_attention_seeds(selected, limit=limit)

    select_material_news_seeds._gs316_installed = True
    select_material_news_seeds._gs316_original = original
    seeded.select_material_news_seeds = select_material_news_seeds
