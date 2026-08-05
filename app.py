from __future__ import annotations

from mide.startup import instrument_startup, log_startup, startup_step

log_startup("entering app.py")

from mide.startup_memory import checkpoint as memory_checkpoint

memory_checkpoint("app.py bootstrap")

from datetime import datetime, timezone, timedelta
import html
import importlib
import inspect
import json
import logging
import math
import platform
from pathlib import Path
import re
import sys
from time import perf_counter
memory_checkpoint("app.py standard-library imports")

import streamlit as st
memory_checkpoint("streamlit import", object_name="streamlit module graph")

from mide.arrow_diagnostics import (
    inspect_session_state_dataframes,
    instrument_streamlit_tables,
)

instrument_streamlit_tables(st)


def price_gate_savings_metrics(
    universe_count: int,
    survivor_count: int,
    batch_size: int,
    price_elapsed_ms: float,
    snapshot_elapsed_ms: float,
) -> dict[str, int | float | None]:
    """Quantify the exact request reduction and an observed-time estimate.

    Alpaca accepts symbol batches for both endpoints, so elapsed snapshot time is
    extrapolated by batch count rather than by symbol.  The estimate is omitted
    when no survivor snapshot batch exists from which to derive a duration.
    """
    batch_size = max(1, int(batch_size))
    universe_count = max(0, int(universe_count))
    survivor_count = max(0, min(int(survivor_count), universe_count))
    baseline_batches = math.ceil(universe_count / batch_size)
    actual_batches = math.ceil(survivor_count / batch_size)
    avoided_batches = baseline_batches - actual_batches
    avoided_symbols = universe_count - survivor_count
    estimated_gross_ms = None
    estimated_net_ms = None
    if actual_batches and avoided_batches:
        per_batch_ms = float(snapshot_elapsed_ms) / actual_batches
        estimated_gross_ms = round(per_batch_ms * avoided_batches, 3)
        estimated_net_ms = round(estimated_gross_ms - float(price_elapsed_ms), 3)
    elif avoided_batches == 0:
        estimated_gross_ms = 0.0
        estimated_net_ms = round(-float(price_elapsed_ms), 3)
    return {
        "price_gate_input_symbols": universe_count,
        "snapshot_symbols_requested": survivor_count,
        "snapshot_symbols_avoided": avoided_symbols,
        "snapshot_symbol_reduction_pct": round(
            avoided_symbols / universe_count * 100, 2
        ) if universe_count else 0.0,
        "baseline_snapshot_batches": baseline_batches,
        "actual_snapshot_batches": actual_batches,
        "snapshot_batches_avoided": avoided_batches,
        "price_endpoint_elapsed_ms": round(float(price_elapsed_ms), 3),
        "observed_survivor_snapshot_elapsed_ms": round(float(snapshot_elapsed_ms), 3),
        "estimated_gross_snapshot_time_avoided_ms": estimated_gross_ms,
        "estimated_net_time_saved_ms": estimated_net_ms,
    }


SCAN_RUNTIME_STAGES = (
    "Universe discovered",
    "Symbols loaded",
    "Prefiltered",
    "Candidates",
    "Analyzed",
    "Ranked",
    "Published",
    "Dashboard",
)


def runtime_stage_observation(records) -> dict[str, object]:
    """Observe a collection's size and first symbols without changing it."""
    symbols = []
    for record in records:
        symbol = record if isinstance(record, str) else record.get("symbol", "")
        symbols.append(str(symbol).upper())
        if len(symbols) == 5:
            break
    return {"count": len(records), "symbols": symbols}


def print_scan_stage_counts(stages: dict[str, dict[str, object]]) -> None:
    """Print the requested runtime funnel and ticker samples for one scan."""
    for label in SCAN_RUNTIME_STAGES:
        observation = stages.get(label, {})
        symbols = ",".join(observation.get("symbols", []))
        print(f"{label}\t{int(observation.get('count', 0))}\t{symbols}", flush=True)


def repair_mide_module_links() -> None:
    """Restore package attributes that a hot reload may have detached.

    Streamlit can rerun this module while Python still has MIDE submodules in
    ``sys.modules``.  Reattaching those modules to their parents avoids mixing a
    newly imported package with orphaned, stale submodule references.
    """
    importlib.invalidate_caches()
    package = sys.modules.get("mide")
    if package is None:
        package = importlib.import_module("mide")
    for name, module in tuple(sys.modules.items()):
        if not name.startswith("mide.") or module is None:
            continue
        parent_name, _, child_name = name.rpartition(".")
        parent = sys.modules.get(parent_name)
        if parent is not None and getattr(parent, child_name, None) is not module:
            setattr(parent, child_name, module)


repair_mide_module_links()
memory_checkpoint("mide package repair")

from mide.config import Settings
from mide.credentials import WEBULL_CREDENTIAL_NAMES, credential_diagnostics, load_credentials
from mide.market_data import MarketDataProvider
import logging
import mide.webull_live as wl

logging.info("WEBULL FILE=%s", wl.__file__)
logging.info("HAS live_data_modes=%s", hasattr(wl, "live_data_modes"))
from mide.webull_live import LiveWebullProvider, live_data_modes
from mide.webull_connection import run_connection_test
from mide.session_controls import (
    AUTO_SCAN_KEY,
    DATA_MODE_KEY,
    PROVIDER_KEY,
    SCAN_REQUESTED_KEY,
    STOP_REQUESTED_KEY,
    begin_scheduled_scan,
    finish_scan,
    initialize_session_controls,
    request_scan,
    request_stop,
    select_data_mode,
    update_auto_scan,
)
from mide.completed_scan import (
    CompletedScan,
    completed_scan_for_view,
    publish_scan_result,
    scan_context,
    store_completed_scan,
)
memory_checkpoint("providers import", object_name="mide.webull_live")
from mide.news import index_news
