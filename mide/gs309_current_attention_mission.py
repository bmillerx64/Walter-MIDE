"""GS309: require current-scan attention evidence for Mission targets.

Walter's broader candidate ledger may retain useful names for continued observation,
but the Primary/Secondary Mission cards should represent what deserves attention
*now*.  This layer keeps the broader discovery/ranking pipeline intact while
requiring one current reason before a ranked record can occupy a Mission slot:

* current Webull DAY_GAINERS membership;
* a fresh FMP material or morning-attention news seed;
* a fresh second-wave / volume-regime re-ignition; or
* a current halt/suspension state.

Absolute-volume and relative-volume feeds remain valid discovery inputs, but by
themselves they no longer justify a Primary/Secondary Mission slot.  They are
still available elsewhere in Walter for observation and can earn a Mission slot
as soon as one of the current-attention conditions above appears.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from copy import deepcopy

DAY_GAINERS_REASON = "Webull native: day_gainers"
ABSOLUTE_VOLUME_REASON = "Webull native: absolute_volume"
RELATIVE_VOLUME_REASON = "Webull native: relative_volume"
FRESH_NEWS_REASON_TOKENS = (
    "FMP material news seed",
    "FMP morning mover attention seed",
)


def annotate_native_attention_reasons(client, seeds, reasons):
    """Attach current Webull feed provenance without another provider request."""
    output = {str(symbol): list(items) for symbol, items in (reasons or {}).items()}
    native = getattr(client, "_native_radar_prices", {}) or {}
    seed_set = {str(symbol or "").strip().upper() for symbol in seeds or []}

    for symbol in seed_set:
        item = native.get(symbol) or {}
        for source in item.get("sources") or []:
            source = str(source or "").strip()
            if not source:
                continue
            reason = f"Webull native: {source}"
            bucket = output.setdefault(symbol, [])
            if reason not in bucket:
                bucket.append(reason)
    return output


def _reason_text(record: dict) -> str:
    return " | ".join(str(value or "") for value in record.get("discovery_reasons") or [])


def current_attention_provenance(record: dict) -> tuple[str, ...]:
    """Return explicit current-scan reasons that justify a Mission slot."""
    evidence: list[str] = []
    reasons = _reason_text(record)

    if DAY_GAINERS_REASON in reasons:
        evidence.append("WEBULL_TOP_MOVER")
    if any(token in reasons for token in FRESH_NEWS_REASON_TOKENS):
        evidence.append("FRESH_NEWS_SEED")

    # Reuse the established attention evaluators rather than inventing another
    # score or threshold family.  Only fresh change-of-behavior states qualify;
    # the broad 'major mover' fallback alone does not keep a stale Mission slot.
    try:
        from .gs305_second_wave_attention import attention_evaluation

        attention = attention_evaluation(record)
        if attention.get("halted"):
            evidence.append("HALTED_OR_SUSPENDED")
        if attention.get("second_wave"):
            evidence.append("FRESH_REIGNITION")
    except Exception:
        pass

    try:
        from .gs307_volume_regime_urgency import volume_regime_urgency

        if volume_regime_urgency(record).get("promoted"):
            evidence.append("FRESH_VOLUME_REGIME")
    except Exception:
        pass

    return tuple(dict.fromkeys(evidence))


def mission_attention_eligible(record: dict) -> bool:
    return bool(current_attention_provenance(record))


def current_attention_records(records: Iterable[dict]) -> list[dict]:
    """Return eligible source records without mutating them."""
    return [record for record in records or [] if mission_attention_eligible(record)]


def install() -> None:
    """Install current provenance at discovery and Mission presentation seams."""
    from . import discovery, ui

    current_build = discovery.build_seed_symbols
    if not getattr(current_build, "_gs309_current_attention", False):
        original_build = current_build

        def build_seed_symbols(client, settings, news_items, *, universe_verification=None):
            if universe_verification is None:
                seeds, reasons = original_build(client, settings, news_items)
            else:
                seeds, reasons = original_build(
                    client,
                    settings,
                    news_items,
                    universe_verification=universe_verification,
                )
            return seeds, annotate_native_attention_reasons(client, seeds, reasons)

        build_seed_symbols._gs309_current_attention = True
        build_seed_symbols._gs309_original = original_build
        discovery.build_seed_symbols = build_seed_symbols

    current_mission = ui.walter_mission_control
    if not getattr(current_mission, "_gs309_current_attention", False):
        original_mission: Callable[[list[dict]], dict] = current_mission

        def walter_mission_control(records: list[dict]) -> dict:
            eligible = current_attention_records(records)
            result = deepcopy(original_mission(eligible))
            for key in ("primary", "secondary"):
                item = result.get(key)
                if isinstance(item, dict) and isinstance(item.get("record"), dict):
                    item["current_attention_provenance"] = list(
                        current_attention_provenance(item["record"])
                    )
            result["current_attention_eligible_count"] = len(eligible)
            return result

        walter_mission_control._gs309_current_attention = True
        walter_mission_control._gs309_original = original_mission
        ui.walter_mission_control = walter_mission_control
