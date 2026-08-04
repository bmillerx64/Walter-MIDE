"""Read-only, per-stage accounting for the live symbol pipeline."""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Mapping, MutableMapping, Sequence


RUNTIME_COLLECTION_COUNTS_KEY = "runtime_collection_counts"


def observe_runtime_collection_count(
    diagnostics: MutableMapping[str, object],
    stage: str,
    collection: Sequence[object],
    *,
    statement: str,
) -> int:
    """Append one behavior-neutral runtime length observation.

    ``statement`` names the assignment or expression between this observation
    and the preceding one.  This makes a count change attributable without
    retaining, copying, or comparing candidate objects.
    """
    observations = diagnostics.setdefault(RUNTIME_COLLECTION_COUNTS_KEY, [])
    # Streamlit can render the same completed scan repeatedly. Re-observing a
    # stage replaces it and later render observations instead of growing the
    # single-scan trace on every widget rerun.
    repeated_at = next((
        index for index, item in enumerate(observations)
        if item["stage"] == stage
    ), None)
    if repeated_at is not None:
        del observations[repeated_at:]
    count = len(collection)
    previous = observations[-1]["count"] if observations else None
    observations.append({
        "stage": stage,
        "count": count,
        "change": None if previous is None else count - previous,
        "statement": statement,
    })
    return count


def stage_diagnostic(
    stage: str,
    inputs: Sequence[Mapping[str, object]],
    outputs: Sequence[Mapping[str, object]],
    *,
    rejection_reasons: Iterable[str] = (),
    fields: Iterable[str] = (),
) -> dict[str, object]:
    """Describe a stage without influencing membership or stage decisions."""
    input_rows = list(inputs)
    output_rows = list(outputs)
    missing = Counter()
    symbols_with_missing = 0
    requested_fields = tuple(fields)
    for record in input_rows:
        absent = [field for field in requested_fields if record.get(field) is None]
        if absent:
            symbols_with_missing += 1
            missing.update(absent)
    reasons = Counter(str(reason or "Unspecified rejection") for reason in rejection_reasons)
    input_count, output_count = len(input_rows), len(output_rows)
    rejection_count = max(0, input_count - output_count)
    return {
        "stage": stage,
        "input_count": input_count,
        "output_count": output_count,
        "rejection_count": rejection_count,
        "top_10_rejection_reasons": [
            {"reason": reason, "count": count}
            for reason, count in reasons.most_common(10)
        ],
        "missing_fields_encountered": [
            {"field": field, "count": count}
            for field, count in missing.most_common()
        ],
        "symbols_with_missing_values": symbols_with_missing,
        "missing_values_pct": round(
            symbols_with_missing / input_count * 100, 2
        ) if input_count else 0.0,
    }


def diagnostics_table(stages: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    """Return compact rows that make the first count collapse immediately visible."""
    rows = []
    for item in stages:
        reasons = item.get("top_10_rejection_reasons") or []
        missing = item.get("missing_fields_encountered") or []
        rows.append({
            "Stage": item.get("stage"),
            "Input": item.get("input_count", 0),
            "Output": item.get("output_count", 0),
            "Rejected": item.get("rejection_count", 0),
            "Top rejection reasons": "; ".join(
                f"{row['reason']} ({row['count']})" for row in reasons
            ) or "None",
            "Missing fields": "; ".join(
                f"{row['field']} ({row['count']})" for row in missing
            ) or "None",
            "Symbols missing values": f"{float(item.get('missing_values_pct', 0)):.2f}%",
        })
    return rows


def pre_expansion_candidate_diagnostics(
    records: Iterable[dict], decisions: Mapping[str, object], limit: int = 20
) -> list[dict]:
    """Show the strongest Expansion inputs and their exact gate outcomes.

    The view is diagnostic-only: it observes the unfiltered Expansion input and
    the decisions already made by that stage without changing membership.
    """

    def number(record: Mapping[str, object], *keys: str) -> float | None:
        for key in keys:
            value = record.get(key)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return None

    def mission_score(record: Mapping[str, object]) -> float:
        return number(
            record, "mission_score", "scanner_v2_score", "opportunity_score",
            "conviction_score",
        ) or 0.0

    ordered = sorted(
        records,
        key=lambda record: (
            -mission_score(record), str(record.get("symbol") or "")
        ),
    )[:max(0, int(limit))]
    rows = []
    for rank, record in enumerate(ordered, 1):
        symbol = str(record.get("symbol") or "").upper()
        decision = decisions.get(symbol)
        passed = bool(getattr(decision, "passed", False))
        updates = getattr(decision, "updates", {})
        updates = updates if isinstance(updates, Mapping) else {}
        expansion_score = number(updates, "expansion_score", "confluence_score")
        if expansion_score is None:
            expansion_score = number(
                record, "expansion_score", "confluence_score",
                "momentum_quality_score",
            )
        rejection = None
        if not passed:
            rejection = (
                f"expansion_score = {expansion_score:g}; required = 65"
                if expansion_score is not None
                else str(getattr(decision, "reason", "Expansion rejected"))
            )
        rows.append({
            "Rank before Expansion": rank,
            "Symbol": symbol,
            "Price": number(record, "price", "last_price"),
            "Volume": number(record, "volume"),
            "Float": number(record, "free_float", "float_shares", "shares_float"),
            "RVOL": number(record, "rvol", "rvol_proxy", "relative_volume"),
            "Spread %": number(record, "spread_pct"),
            "Participation score": number(
                record, "participation_surge_score", "participation_score"
            ),
            "Expansion score": expansion_score,
            "Mission score": mission_score(record),
            "Expansion result": "PASSED" if passed else "REJECTED",
            "Rejected because": rejection,
        })
    return rows
