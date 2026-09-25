"""GS557: observational hotspot timing inside analyze_candidates.

GS556 finally persisted GS554's Participation split and proved the dominant latency is
inside analyze_candidates itself: roughly 28.5s per scan after only ~1.7s of Stage-6
provider history I/O. GS557 measures inclusive wall-clock time spent in the existing
major analyzer functions so the next optimization can target evidence rather than
guessing.

The wrapper is deliberately observational:
- no provider calls are added
- inputs, outputs, call order, thresholds, and exceptions are preserved
- patched callables are restored in a finally block
- timings are inclusive and may overlap; they are not summed as exclusive CPU time
"""
from __future__ import annotations

from functools import wraps
from time import perf_counter
from typing import Any


AUTHORITY = "OBSERVATIONAL_ONLY"
DIAGNOSTIC_KEY = "gs557_analyze_candidates_hotspots"
_OWNER = "_walter_gs557_analyze_candidates_hotspots"

# These are existing local-computation seams reached by Stage 6. Timing them gives
# attribution without changing their formulas or introducing a profiler on the hot path.
_TARGETS = (
    ("mide.discovery", "_timeframe_confirmation", "base.timeframe_confirmation"),
    ("mide.discovery", "alignment_summary", "base.alignment_summary"),
    ("mide.discovery", "volume_pace_metrics", "base.volume_pace_metrics"),
    (
        "mide.discovery",
        "intraday_participation_metrics",
        "base.intraday_participation_metrics",
    ),
    ("mide.discovery", "apply_attention_ranking", "base.apply_attention_ranking"),
    ("mide.discovery", "supertrend", "base.supertrend"),
    ("mide.discovery", "session_vwap", "base.session_vwap"),
    ("mide.discovery", "resample_ohlcv", "base.resample_ohlcv"),
    ("mide.discovery", "ema", "base.ema"),
    ("mide.discovery", "score", "base.score"),
    (
        "mide.gs378_live_vwap_st_crossover",
        "apply_live_vwap_truth",
        "gs378.apply_live_vwap_truth",
    ),
    (
        "mide.authorities.market_evidence",
        "build_efficient_maturation_evidence",
        "gs423.build_efficient_maturation_evidence",
    ),
    (
        "mide.relative_strength",
        "relative_strength_metrics",
        "base.relative_strength_metrics",
    ),
)


def _record(stats: dict[str, dict[str, float | int]], key: str, elapsed_ms: float) -> None:
    row = stats.setdefault(
        key,
        {"calls": 0, "total_ms": 0.0, "max_ms": 0.0},
    )
    row["calls"] = int(row["calls"]) + 1
    row["total_ms"] = float(row["total_ms"]) + float(elapsed_ms)
    row["max_ms"] = max(float(row["max_ms"]), float(elapsed_ms))


def _timed(function, key: str, stats: dict[str, dict[str, float | int]]):
    @wraps(function)
    def measured(*args, **kwargs):
        started = perf_counter()
        try:
            return function(*args, **kwargs)
        finally:
            _record(stats, key, (perf_counter() - started) * 1000.0)

    measured._gs557_timing_wrapper = True
    measured._gs557_original = function
    return measured


def install() -> bool:
    """Wrap the current analyzer and measure existing major local-compute seams."""
    import importlib

    from mide import discovery

    current = discovery.analyze_candidates
    if getattr(current, _OWNER, False):
        return False

    @wraps(current)
    def analyze_with_hotspot_timing(client, candidates, news_index, discovery_reasons):
        stats: dict[str, dict[str, float | int]] = {}
        restores: list[tuple[Any, str, Any]] = []

        for module_name, attribute, key in _TARGETS:
            try:
                module = importlib.import_module(module_name)
                function = getattr(module, attribute)
            except (ImportError, AttributeError):
                continue
            if not callable(function):
                continue
            setattr(module, attribute, _timed(function, key, stats))
            restores.append((module, attribute, function))

        started = perf_counter()
        try:
            return current(client, candidates, news_index, discovery_reasons)
        finally:
            outer_ms = (perf_counter() - started) * 1000.0
            for module, attribute, function in reversed(restores):
                try:
                    setattr(module, attribute, function)
                except Exception:
                    pass

            rows = []
            for key, values in stats.items():
                rows.append(
                    {
                        "function": key,
                        "calls": int(values["calls"]),
                        "total_ms": round(float(values["total_ms"]), 3),
                        "max_ms": round(float(values["max_ms"]), 3),
                    }
                )
            rows.sort(key=lambda item: item["total_ms"], reverse=True)
            diagnostics = getattr(client, "diagnostics", None)
            if isinstance(diagnostics, dict):
                diagnostics[DIAGNOSTIC_KEY] = {
                    "authority": AUTHORITY,
                    "purpose": (
                        "attribute analyze_candidates latency before optimization"
                    ),
                    "outer_total_ms": round(outer_ms, 3),
                    "timings_are_inclusive_and_may_overlap": True,
                    "functions": rows,
                    "extra_provider_calls": 0,
                    "market_data_values_changed": False,
                    "trading_logic_changed": False,
                }

    setattr(analyze_with_hotspot_timing, _OWNER, True)
    analyze_with_hotspot_timing._gs557_original = current
    discovery.analyze_candidates = analyze_with_hotspot_timing
    return True


__all__ = ["AUTHORITY", "DIAGNOSTIC_KEY", "install"]
