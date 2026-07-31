"""Read-only, per-stage accounting for the live symbol pipeline."""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Mapping, Sequence


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
