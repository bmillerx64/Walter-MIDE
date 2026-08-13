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
from mide.news_provider import (
    MarketDataNewsProvider,
    NewsService,
    UnavailableNewsProvider,
    symbol_news_evidence,
    ticker_inspection,
)
from mide.resilience import record_provider_failure
from mide.discovery import (
    analyze_candidates,
    build_seed_symbols,
    is_valid_us_symbol,
    prefilter_snapshots,
    snapshot_identity_records,
)
from mide.flight_recorder import prefilter_decision
from mide.pipeline_diagnostics import (
    diagnostics_table,
    observe_runtime_collection_count,
    pre_expansion_candidate_diagnostics,
    stage_diagnostic,
)
from mide.universe_diagnostics import UniverseVerification
memory_checkpoint("discovery import", object_name="mide.discovery")
from mide.scanner_v2 import (
    apply_scanner_v2,
    participation_gate_rejection_diagnostics,
    strengthening_diagnostics,
)
memory_checkpoint("scanner import", object_name="mide.scanner_v2")
from mide.memory import MemoryStore
from mide.flight_recorder import FlightRecorder
from mide.decision_engine import expansion_candidate_diagnostic
memory_checkpoint("cache stores import", object_name="MemoryStore, FlightRecorder")
from mide.memory_profile import compact_previous_record, profile as memory_profile, release_temporaries
from mide.timeframe_alignment import alignment_voice
memory_checkpoint("runtime evidence imports")
from mide.demo import demo_records
from mide.escalation import (
    escalation_alert_phrase,
    escalation_snapshot,
    escalation_state_changes,
)
from mide.data_integrity import scan_integrity_report
from mide.ui import (
    inject_css,
    radar_table,
    opportunity_card,
    play_alert,
    scanner_v2_display_sections,
    scanner_v2_dashboard_counts,
    actionable_candidate_records,
    rejected_candidates_table,
    rejection_diagnostics,
    trader_priority_sort_key,
    render_walter_mission_control,
    render_early_setups,
    render_live_opportunity_feed,
    render_escalation_engine,
    mission_control_header_markup,
    data_integrity_markup,
    decision_funnel_markup,
    market_session_quality_markup,
    walter_mission_control,
    render_calibration_dashboard,
)
memory_checkpoint("UI import", object_name="mide.ui")
from mide.live_opportunity_feed import update_opportunity_feed
from mide.early_setup import newly_entered_symbols
from mide.time_service import format_eastern_time, market_clock, market_phase_at
from mide.watchdog import ScanAlreadyRunning
from mide.decision_engine import (
    evaluate as evaluate_decision_funnel,
    behavioral_decision,
)
from mide.architecture import (
    ArchitecturePolicy,
    Decision,
    STAGES as WALTER_STAGES,
    WalterCandidateLedger,
    WalterArchitectureV1,
    scanner_implementation,
)
from mide.architecture_verification import candidate_trace
from mide.mission_outcomes import MissionOutcomeStore
memory_checkpoint("decision engine import", object_name="mide.decision_engine")
from mide.free_float_inspector import inspect_free_float
from mide.free_float import (
    FreeFloatClient,
    YahooFinanceFloatProvider,
    cache_diagnostics_or_default,
    enrich_snapshots_with_free_float,
)
from mide.version import BUILD
memory_checkpoint("remaining providers and application imports")


def free_float_decision(
    snapshot: dict[str, object], max_free_float: int
) -> Decision:
    """Apply the production float ceiling without treating missing data as a veto."""
    updates = dict(snapshot)
    raw_value = next((updates.get(key) for key in (
        "free_float", "float_shares", "shares_float"
    ) if updates.get(key) is not None), None)
    try:
        value = float(raw_value)
        if math.isnan(value):
            raise ValueError("free float is NaN")
    except (TypeError, ValueError):
        updates.update(
            free_float_verified=False,
            free_float_verification_status="unavailable",
        )
        return Decision(
            True,
            "Free Float",
            "Free float unavailable; configured limit unverified",
            updates,
        )

    updates.update(
        free_float_verified=True,
        free_float_verification_status="verified",
    )
    passed = value <= max_free_float
    reason = (
        "Free float within configured limit"
        if passed
        else "Free float exceeds configured limit"
    )
    return Decision(passed, "Free Float", reason, updates)


SYSTEM_DEFAULT_VOICE_ID = "__system_default__"
DEFAULT_VOICE = "System Default"
SAMANTHA_VOICE = "Samantha"
DAVID_VOICE = "David"
VOICE_OPTIONS = [DEFAULT_VOICE, SAMANTHA_VOICE]
ALERT_VOICE_SESSION_KEY = "alert_voice_name"
ALERT_VOICE_QUERY_KEY = "alert_voice"
ALERT_VOICE_WIDGET_KEY = "alert_voice_selector"
VOICE_CONFIRMATION_SESSION_KEY = "alert_voice_confirmation"
DAVID_AVAILABLE_SESSION_KEY = "alert_david_available"
ACTIVE_VOICE_SESSION_KEY = "alert_active_voice_identifier"
VOICE_WARNING_SESSION_KEY = "alert_voice_warning"


def system_voice_option() -> dict:
    """Return Walter's non-persistent system default voice option."""
    return {"name": DEFAULT_VOICE, "identifier": SYSTEM_DEFAULT_VOICE_ID}


def named_voice_option(name: str) -> dict:
    """Return a stable browser speech voice option by display name."""
    return {"name": name, "identifier": name}


def stable_voice_options(david_available: bool = False) -> list[dict]:
    """Return Walter's stable alert voice choices without unavailable entries."""
    options = [system_voice_option(), named_voice_option(SAMANTHA_VOICE)]
    if david_available:
        options.append(named_voice_option(DAVID_VOICE))
    return options


def voice_label(voice: dict) -> str:
    """Return the stable voice label shown in the selector."""
    return voice["name"]


def voice_ids(options: list[dict]) -> list[str]:
    return [voice["identifier"] for voice in options]


def voice_by_identifier(options: list[dict], identifier: str) -> dict | None:
    return next((voice for voice in options if voice["identifier"] == identifier), None)


def normalize_alert_voice(voice_identifier: str) -> str:
    """Return the speech-synthesis voice identifier used by every alert path."""
    return (
        ""
        if voice_identifier in {DEFAULT_VOICE, SYSTEM_DEFAULT_VOICE_ID, ""}
        else voice_identifier
    )


def canonical_voice_identifier(voice_identifier: str) -> str:
    """Normalize legacy and empty voice values to the System Default identifier."""
    return (
        SYSTEM_DEFAULT_VOICE_ID
        if voice_identifier in {"", "System", DEFAULT_VOICE}
        else voice_identifier
    )


def selected_alert_voice(session_state=None) -> str:
    """Read the current voice identifier from session state without mutating widgets."""
    state = st.session_state if session_state is None else session_state
    return canonical_voice_identifier(
        state.get(ALERT_VOICE_SESSION_KEY, SYSTEM_DEFAULT_VOICE_ID)
    )


def persisted_alert_voice(query_params=None, session_state=None) -> str:
    """Resolve voice choice from URL state, preserving unavailable saved preferences."""
    state = st.session_state if session_state is None else session_state
    params = st.query_params if query_params is None else query_params
    raw = params.get(ALERT_VOICE_QUERY_KEY, "") if params is not None else ""
    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    if raw:
        state[ALERT_VOICE_SESSION_KEY] = canonical_voice_identifier(raw)
        return state[ALERT_VOICE_SESSION_KEY]
    return selected_alert_voice(state)


def david_available_from_query(query_params=None, session_state=None) -> bool:
    """Read whether the browser can actually select David."""
    state = st.session_state if session_state is None else session_state
    params = st.query_params if query_params is None else query_params
    raw = params.get("walter_david_available", "") if params is not None else ""
    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    if raw in {"0", "1"}:
        state[DAVID_AVAILABLE_SESSION_KEY] = raw == "1"
    return bool(state.get(DAVID_AVAILABLE_SESSION_KEY, False))


def active_voice_identifier(
    selected: str, options: list[dict], session_state=None
) -> str:
    """Keep the requested voice active and warn when Walter cannot verify it."""
    state = st.session_state if session_state is None else session_state
    selected = canonical_voice_identifier(selected)
    state[ACTIVE_VOICE_SESSION_KEY] = selected
    if selected == SYSTEM_DEFAULT_VOICE_ID or voice_by_identifier(options, selected):
        state[VOICE_WARNING_SESSION_KEY] = ""
    else:
        state[VOICE_WARNING_SESSION_KEY] = (
            "The selected voice is not available on this system. Walter kept your preference "
            "and will not fall back to System Default."
        )
    return selected


def alert_voice_for_session(session_state=None) -> str:
    """Resolve the active voice for alerts while preserving unavailable preferences."""
    state = st.session_state if session_state is None else session_state
    return normalize_alert_voice(
        state.get(ACTIVE_VOICE_SESSION_KEY, selected_alert_voice(state))
    )


def persist_selected_alert_voice() -> None:
    """Persist the selected widget voice and queue its audible confirmation."""
    selected = canonical_voice_identifier(
        st.session_state.get(ALERT_VOICE_WIDGET_KEY, SYSTEM_DEFAULT_VOICE_ID)
    )
    st.session_state[ALERT_VOICE_SESSION_KEY] = selected
    st.query_params[ALERT_VOICE_QUERY_KEY] = selected
    st.session_state[VOICE_CONFIRMATION_SESSION_KEY] = selected


def market_phase(now: datetime | None = None) -> str:
    """Return the U.S. equity market phase from the shared Eastern clock."""
    return market_phase_at(now)


def scan_alert_phrase(records: list[dict]) -> str:
    """Build the per-scan audible alert, prioritizing actionable Entry Ready symbols."""
    actionable_records = actionable_candidate_records(records)
    promoted = [
        record
        for record in actionable_records
        if record.get("advanced_state") or record.get("entered_watchlist")
    ]
    if promoted:
        record = promoted[0]
        symbol = str(record.get("symbol") or "Symbol").upper()
        workflow = str(
            record.get("workflow_label")
            or record.get("candidate_status")
            or record.get("status")
        )
        reasons = record.get("promotion_reasons") or record.get("reasons") or []
        blockers = record.get("entry_blockers_explained") or []
        detail = "; ".join(str(item) for item in reasons[:3])
        phrase = f"{symbol} promoted to {workflow}."
        if detail:
            phrase += f" Reason: {detail}."
        if workflow != "Entry Ready" and blockers:
            phrase += f" Not yet Entry Ready: {blockers[0]}."
        if record.get("quality_score") is not None:
            phrase += (
                f" Grade {record.get('quality_grade', 'Watch Only')}."
                f" Score {int(record['quality_score'])}."
            )
        alignment = alignment_voice(record)
        if alignment:
            phrase += f" {alignment}"
        return phrase
    entry_symbols = [
        r.get("symbol")
        for r in actionable_records
        if (
            r.get("qualified_for_alert", r.get("qualified_for_ranking", True))
            # TODO Walter 2.0 Phase 2: remove qualified_for_ranking fallback
            # after callers that construct legacy alert records are migrated.
            and (
                r.get("candidate_status") == "Entry Ready"
                or r.get("status") == "Entry Ready"
            )
        )
    ]
    entry_symbols = [str(s).upper() for s in entry_symbols if s]
    if entry_symbols:
        entry_records = [
            r
            for r in actionable_records
            if str(r.get("symbol") or "").upper() in entry_symbols
        ]
        if len(entry_records) == 1 and entry_records[0].get("quality_score") is not None:
            record = entry_records[0]
            phrase = (
                f"{entry_symbols[0]}. Grade {record.get('quality_grade', 'Watch Only')}. "
                f"Score {int(record['quality_score'])}."
            )
            alignment = alignment_voice(record)
            return f"{phrase} {alignment}" if alignment else phrase
        if len(entry_symbols) == 1:
            symbol_text = entry_symbols[0]
        else:
            symbol_text = f"{', '.join(entry_symbols[:-1])} and {entry_symbols[-1]}"
        return f"Entry Ready: {symbol_text}."

    dashboard_counts = scanner_v2_dashboard_counts(actionable_records)
    if dashboard_counts["strengthening"]:
        return f"Watching {dashboard_counts['strengthening']}."
    return ""


with startup_step("rendering Streamlit UI"):
    st.set_page_config(page_title="Walter • MIDE Radar", page_icon="🛰", layout="wide")
    inject_css()
memory_checkpoint("Streamlit page initialization", object_name="page config and CSS")


def log(message: str) -> None:
    stamp = datetime.now().astimezone().strftime("%H:%M:%S")
    print(f"[WALTER {stamp}] {message}", flush=True)


@st.cache_resource
def get_store() -> MemoryStore:
    store = MemoryStore()
    memory_checkpoint("candidate cache initialization", object_name="MemoryStore")
    return store


@st.cache_resource
def get_flight_recorder() -> FlightRecorder:
    # Resolve the class at call time so a Streamlit hot reload never keeps the
    # pre-deployment FlightRecorder class captured by this app module.
    repair_mide_module_links()
    recorder_class = importlib.import_module("mide.flight_recorder").FlightRecorder
    recorder = recorder_class()
    memory_checkpoint("flight recorder cache initialization", object_name="FlightRecorder")
    return recorder


def get_trade_outcome_store(recorder=None):
    """Return the outcome store, including for a cached pre-feature recorder.

    Streamlit can retain a ``FlightRecorder`` resource created before Trade
    Outcomes added the public ``outcomes`` attribute.  Keep that deployment
    transition out of the UI: an old or only partially initialized recorder
    gets the same empty-on-first-use store beside its flight log.
    """
    recorder = recorder or get_flight_recorder()
    outcome_store = getattr(recorder, "outcomes", None)
    if outcome_store is not None:
        return outcome_store

    recorder_path = getattr(recorder, "path", None)
    outcomes_path = (
        recorder_path.parent / "trade_outcomes.json"
        if recorder_path is not None
        else "data/trade_outcomes.json"
    )
    outcome_store = importlib.import_module("mide.trade_outcomes").TradeOutcomeStore(outcomes_path)
    # Repair a cached legacy instance for every subsequent UI access. Some
    # unusual proxy objects may reject assignment; returning the store is still
    # enough to keep this render safe.
    try:
        recorder.outcomes = outcome_store
    except (AttributeError, TypeError):
        pass
    return outcome_store


def _recorder_file_state(path: Path | None) -> dict:
    """Return metadata only (never contents) for the recorder diagnostics."""
    if path is None:
        return {"exists": False, "size_bytes": None}
    try:
        stat = path.stat()
    except FileNotFoundError:
        return {"exists": False, "size_bytes": None}
    except OSError:
        return {"exists": path.exists(), "size_bytes": None}
    return {"exists": True, "size_bytes": stat.st_size}


def _sanitized_recorder_error(exc: Exception) -> str:
    """Keep useful recorder errors while refusing potentially sensitive text."""
    message = " ".join(str(exc).split())
    if re.search(
        r"(?i)authorization|bearer|credential|password|secret|token|api[-_ ]?key|headers?",
        message,
    ):
        return "[redacted: potentially sensitive exception message]"
    return message[:300]


def record_scan_safely(
    recorder, *, recent_news_log=None, runtime_diagnostics=None, **scan_data
):
    """Write an optional flight trace without affecting the live dashboard."""
    diagnostics = runtime_diagnostics if runtime_diagnostics is not None else {}
    recorder_path = getattr(recorder, "path", None)
    resolved_path = Path(recorder_path).expanduser().resolve() if recorder_path else None
    diagnostics.update({
        "invoked": True,
        "recorder_path": str(resolved_path) if resolved_path else None,
        "before": _recorder_file_state(resolved_path),
        "record_scan_succeeded": False,
        "exception": None,
    })
    try:
        try:
            result = recorder.record_scan(
                **scan_data, recent_news_log=recent_news_log
            )
        except TypeError as exc:
            # Rolling/hot deployments can briefly retain the pre-news recorder
            # instance.  It is safe to omit only this optional field for that
            # known interface mismatch.
            if "unexpected keyword argument 'recent_news_log'" not in str(exc):
                raise
            logging.getLogger(__name__).warning(
                "Flight Recorder is using the legacy interface; news log omitted"
            )
            result = recorder.record_scan(**scan_data)
        diagnostics["record_scan_succeeded"] = True
        return result
    except Exception as exc:
        sanitized_message = _sanitized_recorder_error(exc)
        diagnostics["exception"] = {
            "class": type(exc).__name__,
            "message": sanitized_message,
        }
        logging.getLogger(__name__).error(
            "Flight Recorder write failed (%s): %s",
            type(exc).__name__,
            sanitized_message,
        )
        log(
            "Flight Recorder write failed; dashboard updated: "
            f"{type(exc).__name__}: {sanitized_message}"
        )
        return None
    finally:
        diagnostics["after"] = _recorder_file_state(resolved_path)


def flight_recorder_download_bytes(recorder) -> bytes:
    """Read the recorder at render time rather than caching a pre-scan payload."""
    return recorder.export_bytes()


def symbol_export(symbol: str, store: MemoryStore, recorder: FlightRecorder) -> dict:
    """Build one portable, scan-by-scan diagnostic bundle for a symbol."""
    return {
        "symbol": symbol.strip().upper(),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "candidate_history": store.history_for_symbol(symbol),
        "flight_recorder": recorder.history_for_symbol(symbol),
        "trade_outcomes": get_trade_outcome_store(recorder).for_symbol(symbol),
    }


def symbol_outcome(bundle: dict) -> str:
    """Map a symbol bundle to Walter's four troubleshooting outcomes."""
    flights = bundle.get("flight_recorder") or []
    candidates = bundle.get("candidate_history") or []
    if not flights:
        return (
            f"No {bundle.get('symbol', 'symbol')} record: discovery never supplied it."
        )
    prefilter_passed = any(
        any(
            event.get("stage") == "prefilter" and event.get("passed")
            for event in trace.get("events", [])
        )
        for trace in flights
    )
    if not prefilter_passed:
        return "Discovered but prefilter failed: the prefilter removed it."
    strengthened = any(
        str(record.get("candidate_status") or record.get("status", "")).lower()
        == "strengthening"
        for record in candidates
    )
    if not strengthened:
        return "Candidate/Watch but never Strengthening: workflow or confirmation blocked it."
    return (
        "Strengthening but not obvious to you: presentation or alert delivery failed."
    )


def symbol_chart_rows(bundle: dict) -> list[dict]:
    """Create a compact scan timeline suitable for Streamlit's line chart."""
    stage_number = {
        stage: index + 1
        for index, stage in enumerate(
            (
                "discovery",
                "snapshot",
                "prefilter",
                "Scanner V2",
                "Participation Gate",
                "Structure Gate",
                "qualified_for_ranking",
                "actionable display",
            )
        )
    }
    candidate_by_time = {
        str(item.get("scan_timestamp") or item.get("timestamp")): item
        for item in bundle.get("candidate_history", [])
    }
    rows = []
    for trace in bundle.get("flight_recorder", []):
        candidate = candidate_by_time.get(str(trace.get("timestamp")), {})
        row = {
            "Scan": trace.get("timestamp"),
            "Stage reached": stage_number.get(trace.get("stage_reached"), 0),
        }
        for key, label in (
            ("current_momentum", "Momentum"),
            ("opportunity_score", "Opportunity"),
            ("conviction_v2_score", "Conviction"),
        ):
            value = candidate.get(key)
            if isinstance(value, (int, float)):
                row[label] = value
        rows.append(row)
    return rows


def get_secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default


def secrets_mapping() -> dict:
    try:
        return dict(st.secrets)
    except Exception:
        return {}


with startup_step("loading secrets"):
    settings = Settings.from_mapping(secrets_mapping())
memory_checkpoint("settings initialization", object_name="Settings")

mission_header_slot = st.empty()
scan_trust_slot = st.empty()
market_session_slot = st.empty()
early_setup_slot = st.empty()
mission_plan_slot = st.empty()
opportunity_feed_slot = st.empty()
escalation_engine_slot = st.empty()
system_status_panel = st.expander("System Status", expanded=False)
scan_runtime_slot = system_status_panel.container()
with startup_step("loading Webull secrets"):
    webull_credentials = load_credentials(
        WEBULL_CREDENTIAL_NAMES, secrets=secrets_mapping()
    )
webull_startup_diagnostics = credential_diagnostics(webull_credentials)
for diagnostic in webull_startup_diagnostics:
    logging.getLogger(__name__).info("Webull credential startup check: %s", diagnostic)
system_status_panel.caption("Webull startup: " + " · ".join(webull_startup_diagnostics))
memory_checkpoint("dashboard container initialization", object_name="Streamlit DeltaGenerators")

session_defaults = {
    "walter_candidate_ledger": WalterCandidateLedger(),
    "free_float_inspection": None,
    "last_scan_attempt": None,
    "scan_failure_count": 0,
    "last_escalation_alert": "",
    "active_early_setup_symbols": set(),
    "opportunity_feed_snapshot": {},
    "opportunity_feed_events": [],
    "rejected_candidate_history": [],
    "rejection_diagnostics_signature": (),
    ALERT_VOICE_SESSION_KEY: SYSTEM_DEFAULT_VOICE_ID,
    DAVID_AVAILABLE_SESSION_KEY: False,
    ACTIVE_VOICE_SESSION_KEY: SYSTEM_DEFAULT_VOICE_ID,
    VOICE_WARNING_SESSION_KEY: "",
    VOICE_CONFIRMATION_SESSION_KEY: "",
}
for key, default in session_defaults.items():
    if key not in st.session_state:
        st.session_state[key] = default
runtime_context = scan_context(st.session_state)
memory_checkpoint("session cache initialization", object_name="st.session_state")
memory_profile("startup", session_state=st.session_state)
persisted_alert_voice()

with st.sidebar:
    st.header("Control")
    alpaca_possible = bool(get_secret("ALPACA_API_KEY")) and bool(
        get_secret("ALPACA_SECRET_KEY")
    )
    webull_possible = all(credential.present for credential in webull_credentials.values())
    live_possible = alpaca_possible or webull_possible
    data_modes, default_mode = live_data_modes(
        alpaca_configured=alpaca_possible, webull_configured=webull_possible
    )
    current_watchdog = importlib.import_module("mide.watchdog").PROCESS_SCAN_WATCHDOG
    initialize_session_controls(
        st.session_state,
        default_mode=data_modes[default_mode],
        scan_running=current_watchdog.is_running,
    )
    mode = st.radio(
        "Data mode", data_modes, key=DATA_MODE_KEY,
        on_change=select_data_mode, args=(st.session_state,),
    )
    selected_provider = st.session_state[PROVIDER_KEY]
    st.caption(f"Decision Funnel v{BUILD.version} · {BUILD.git_sha}")
    scanner_version = "Walter Architecture v1.0"
    auto_refresh = st.toggle(
        "Auto live scan every 60 seconds", key=AUTO_SCAN_KEY,
        disabled=not mode.startswith("Live "),
        on_change=update_auto_scan, args=(st.session_state,),
    )
    alerts = st.toggle("Audible watch/advance alerts", value=True)
    david_available = david_available_from_query()
    voice_options = stable_voice_options(david_available)
    available_voice_ids = voice_ids(voice_options)
    requested_voice = selected_alert_voice()
    widget_voice = (
        requested_voice
        if requested_voice in available_voice_ids
        else SYSTEM_DEFAULT_VOICE_ID
    )
    if st.session_state.get(ALERT_VOICE_WIDGET_KEY) != widget_voice:
        st.session_state[ALERT_VOICE_WIDGET_KEY] = widget_voice
    selected_voice = st.selectbox(
        "Alert voice",
        available_voice_ids,
        index=available_voice_ids.index(widget_voice),
        key=ALERT_VOICE_WIDGET_KEY,
        format_func=lambda voice_id: voice_label(
            voice_by_identifier(voice_options, voice_id) or system_voice_option()
        ),
        on_change=persist_selected_alert_voice,
    )
    active_voice = active_voice_identifier(
        (
            requested_voice
            if requested_voice not in available_voice_ids
            else selected_voice
        ),
        voice_options,
    )
    st.query_params[ALERT_VOICE_QUERY_KEY] = selected_voice
    if st.session_state.get(VOICE_WARNING_SESSION_KEY):
        st.warning(st.session_state[VOICE_WARNING_SESSION_KEY])
    st.components.v1.html(
        f"""<script>
        const voiceParam = '{ALERT_VOICE_QUERY_KEY}';
        const params = new URLSearchParams(window.parent.location.search);
        const selectedVoice = {selected_voice!r};
        const discover = () => {{
          const voices = ('speechSynthesis' in window) ? window.speechSynthesis.getVoices() : [];
          const davidAvailable = voices.some(v => v.name === 'David' || v.voiceURI === 'David' || v.name.includes('David'));
          window.localStorage.setItem('walter_alert_voice', selectedVoice);
          window.localStorage.setItem('walter_david_available', davidAvailable ? '1' : '0');
          const storedVoice = window.localStorage.getItem('walter_alert_voice');
          const storedDavidAvailable = window.localStorage.getItem('walter_david_available') || '0';
          let changed = false;
          if (!params.get(voiceParam) && storedVoice) {{ params.set(voiceParam, storedVoice); changed = true; }}
          if (params.get('walter_david_available') !== storedDavidAvailable) {{ params.set('walter_david_available', storedDavidAvailable); changed = true; }}
          if (changed) window.parent.location.replace(`${{window.parent.location.pathname}}?${{params}}`);
        }};
        if ('speechSynthesis' in window) {{
          if (window.speechSynthesis.getVoices().length) discover();
          else window.speechSynthesis.onvoiceschanged = discover;
        }}
        </script>""",
        height=0,
    )
    pending_voice_confirmation = st.session_state.pop(
        VOICE_CONFIRMATION_SESSION_KEY, ""
    )
    if pending_voice_confirmation:
        selected_meta = voice_by_identifier(
            voice_options, pending_voice_confirmation
        ) or named_voice_option(pending_voice_confirmation)
        play_alert(
            "assets/alert.wav",
            f"Voice changed to {selected_meta['name']}.",
            normalize_alert_voice(active_voice),
        )
    show_pass = False
    inspect_symbol = ""
    with st.expander("Diagnostics", expanded=False):
        st.caption(
            "Optional troubleshooting tools are hidden here to keep the trading view focused."
        )
        show_pass = st.toggle("Show removed/pass candidates", value=False)
        inspect_symbol = (
            st.text_input("Symbol lookup", placeholder="BIYA").strip().upper()
        )
        st.divider()
        st.write("Speech engine in use: Browser Web Speech API")
        st.write(f"Operating system: {platform.system()} {platform.release()}".strip())
        st.write(f"David available: {david_available}")
        st.write(
            f"Active voice identifier: {st.session_state.get(ACTIVE_VOICE_SESSION_KEY, SYSTEM_DEFAULT_VOICE_ID)}"
        )
        st.write(f"Voice currently selected: {selected_voice}")
        sidebar_scan = completed_scan_for_view(st.session_state, "Diagnostics")
        sidebar_diagnostics = sidebar_scan.diagnostics if sidebar_scan else {}
        stream_diagnostics = sidebar_diagnostics.get("webull_stream", {})
        completed_provider = sidebar_scan.provider if sidebar_scan else None
        st.write(f"Selected provider: {selected_provider}")
        st.write(f"Completed scan provider: {completed_provider or 'No completed scan'}")
        if completed_provider == "WEBULL":
            actual_sources = sidebar_scan.pipeline_sources
            st.write("Actual Live Webull pipeline providers and endpoints")
            if actual_sources:
                st.dataframe(actual_sources, use_container_width=True, hide_index=True)
            else:
                st.caption("Provider paths appear after the first Live Webull scan.")
            st.write(f"Webull authentication: {stream_diagnostics.get('authentication_status', 'pending')}")
            st.write(f"Stream connection: {stream_diagnostics.get('stream_connection_status', 'disconnected')}")
            st.write(f"Subscribed symbols: {stream_diagnostics.get('subscribed_symbols', 0)}")
            st.write(f"Cached Symbols: {stream_diagnostics.get('cached_symbols', 0)}")
            st.write(f"Symbols Missing Prices: {stream_diagnostics.get('symbols_missing_prices', 0)}")
            st.write(f"Stream Messages Received: {stream_diagnostics.get('messages_received', 0)}")
            st.write(f"Last Stream Timestamp: {stream_diagnostics.get('last_message_timestamp') or 'N/A'}")
            st.write(f"Stream Disconnect Count: {stream_diagnostics.get('disconnect_count', 0)}")
            st.write(f"Stream latency: {stream_diagnostics.get('stream_latency_ms') or 'N/A'} ms")
            failures = stream_diagnostics.get("subscription_failures", [])
            st.write(f"Subscription failures/errors: {len(failures)}")
            if failures:
                st.warning(" · ".join(failures[-3:]))
        st.divider()
        st.write("Webull Connection Test")
        st.caption("Runs live only in the deployed app using Streamlit secrets; it does not change scan results.")
        if st.button("Run Webull Connection Test", use_container_width=True):
            try:
                from mide.webull_live import WebullOpenAPIClient
                alpaca_module = importlib.import_module("mide.market_data_providers")
                universe = alpaca_module.AlpacaProvider(
                    get_secret("ALPACA_API_KEY"), get_secret("ALPACA_SECRET_KEY"),
                    feed=settings.feed, timeout=8).assets()
                eligible = [row.get("symbol") for row in universe
                            if row.get("tradable", True) and row.get("status", "active") == "active"]
                connection_rows = run_connection_test(
                    app_key=webull_credentials["WEBULL_APP_KEY"].value,
                    app_secret=webull_credentials["WEBULL_APP_SECRET"].value,
                    eligible_symbols=eligible, client_factory=WebullOpenAPIClient)
                st.dataframe(connection_rows, use_container_width=True, hide_index=True)
                failures = [row for row in connection_rows if row["Status"] == "FAIL"]
                (st.error if failures else st.success)(
                    "Webull Connection Test: " + ("FAIL" if failures else "PASS"))
            except Exception as exc:
                st.error(f"Webull Connection Test failed: {type(exc).__name__}: {exc}")
    st.subheader("Session backups")
    st.caption(
        "Download both files before refreshing, restarting, or deploying Walter."
    )
    st.download_button(
        "Download Candidate History",
        data=get_store().export_bytes(),
        file_name="candidate_history.jsonl",
        mime="application/x-ndjson",
        use_container_width=True,
    )
    # Filled after scan orchestration below so its payload cannot be a snapshot
    # taken before a just-requested scan appends to the recorder.
    flight_recorder_download_slot = st.empty()
    run_scan = st.button(
        "Run live scan",
        type="primary",
        use_container_width=True,
        disabled=not mode.startswith("Live ") or st.session_state.scan_in_progress,
        on_click=request_scan,
        args=(st.session_state,),
    )
    st.button(
        "Stop scan",
        use_container_width=True,
        disabled=not st.session_state.scan_in_progress,
        on_click=request_stop,
        args=(st.session_state,),
    )
    use_demo = st.button("Load demo data", use_container_width=True)
    st.divider()
    if settings.feed == "sip":
        st.success("SIP feed selected")
    else:
        st.warning("IEX feed selected. Set ALPACA_FEED='sip' for consolidated data.")


def arm_live_clock_engine(
    enabled: bool,
    refresh_seconds: int,
    last_updated: datetime | None,
    last_scan_attempt: datetime | None = None,
    retry_seconds: int = 5,
) -> None:
    """Keep dashboard clocks live and trigger scheduled scans without showing a timer."""
    updated_ms = int(last_updated.timestamp() * 1000) if last_updated else 0
    attempt_ms = int(last_scan_attempt.timestamp() * 1000) if last_scan_attempt else 0
    baseline_ms = max(updated_ms, attempt_ms)
    refresh_ms = max(1, int(refresh_seconds)) * 1000
    retry_ms = max(1, int(retry_seconds)) * 1000
    st.components.v1.html(
        f"""<script>
        (() => {{
          const root = window.parent;
          const enabled = {str(enabled).lower()};
          const updatedAt = {updated_ms};
          const attemptedAt = {attempt_ms};
          const baselineAt = {baseline_ms};
          const refreshMs = {refresh_ms};
          const retryMs = {retry_ms};
          // Keep an in-flight marker in this browser tab to prevent repeated
          // reloads while Streamlit performs its blocking scan rerun. Store the
          // scan baseline as well because server and browser clocks can skew.
          const scanKey = 'walterScanState';
          if (root.__walterLiveClockInterval) root.clearInterval(root.__walterLiveClockInterval);

          const node = id => root.document.getElementById(id);
          const setText = (id, value) => {{ const el = node(id); if (el) el.textContent = value; }};
          const marketNow = now => {{
            const parts = new Intl.DateTimeFormat('en-US', {{
              timeZone: 'America/New_York', hour: 'numeric', minute: '2-digit',
              second: '2-digit', hour12: true, timeZoneName: 'short'
            }}).formatToParts(now);
            const value = type => parts.find(part => part.type === type)?.value || '';
            const hour = Number(value('hour')) % 12;
            const minute = Number(value('minute'));
            const isPm = value('dayPeriod') === 'PM';
            const hour24 = hour + (isPm ? 12 : 0);
            let phase = 'Market Closed';
            const clockMinutes = hour24 * 60 + minute;
            if (clockMinutes >= 240 && clockMinutes < 570) phase = 'Pre-Market';
            else if (clockMinutes >= 570 && clockMinutes < 960) phase = 'Live Market';
            else if (clockMinutes >= 960 && clockMinutes < 1200) phase = 'After-Hours';
            return {{
              text: `${{value('hour')}}:${{value('minute')}}:${{value('second')}} ${{value('dayPeriod')}} ${{value('timeZoneName')}}`,
              phase
            }};
          }};
          const tick = () => {{
            const now = Date.now();
            const market = marketNow(now);
            setText('walter-market-time', market.text);
            setText('walter-market-phase', market.phase);
            if (!enabled) {{
              root.sessionStorage.removeItem(scanKey);
              return;
            }}
            let scanState = null;
            try {{
              scanState = JSON.parse(root.sessionStorage.getItem(scanKey) || 'null');
            }} catch (_) {{
              root.sessionStorage.removeItem(scanKey);
            }}
            if (scanState && scanState.baselineUpdatedAt !== baselineAt) {{
              root.sessionStorage.removeItem(scanKey);
              scanState = null;
            }}
            const deadline = attemptedAt > updatedAt
              ? attemptedAt + retryMs
              : (updatedAt ? updatedAt + refreshMs : now);
            if (!scanState && now < deadline) return;
            if (!scanState) {{
              scanState = {{startedAt: now, baselineUpdatedAt: baselineAt}};
              root.sessionStorage.setItem(scanKey, JSON.stringify(scanState));
              root.setTimeout(() => root.location.reload(), 80);
            }}
          }};
          tick();
          root.__walterLiveClockInterval = root.setInterval(tick, 1000);
        }})();
        </script>""",
        height=0,
    )


def _run_live_pipeline(
    scanner_version: str = "Walter Architecture v1.0",
    *,
    status,
    client_factory=None,
    credential_checker=None,
    provider_name: str = "ALPACA",
):
    """Execute the live scan through the single Walter Architecture pipeline."""
    scan_started = perf_counter()
    repair_mide_module_links()
    if provider_name.upper() == "WEBULL":
        log_startup("initializing Webull provider")
        resolved = load_credentials(WEBULL_CREDENTIAL_NAMES, secrets=secrets_mapping())
        app_key = resolved["WEBULL_APP_KEY"].value
        app_secret = resolved["WEBULL_APP_SECRET"].value
        if not app_key or not app_secret:
            raise RuntimeError("Webull credentials are not configured in Streamlit Secrets/environment.")
        context = scan_context(st.session_state)
        client = context.provider_instance
        if not isinstance(client, LiveWebullProvider):
            alpaca_key = get_secret("ALPACA_API_KEY")
            alpaca_secret = get_secret("ALPACA_SECRET_KEY")
            if not alpaca_key or not alpaca_secret:
                raise RuntimeError("Alpaca credentials are required for the temporary /v2/assets symbol master.")
            provider_module = importlib.import_module("mide.market_data_providers")
            universe_client = provider_module.AlpacaProvider(
                alpaca_key, alpaca_secret, feed=settings.feed, timeout=8)
            client = LiveWebullProvider(
                app_key, app_secret, universe_client=universe_client)
            context.provider_instance = client
        logging.getLogger(__name__).warning(
            "Walter quote/bars/stream provider: WEBULL SDK; symbol master: ALPACA /v2/assets"
        )
    else:
        api_key = get_secret("ALPACA_API_KEY")
        secret = get_secret("ALPACA_SECRET_KEY")
        if not api_key or not secret:
            raise RuntimeError("Alpaca credentials are not configured in Streamlit Secrets.")
        # Legacy mode is isolated behind lazy imports so selecting Live Webull
        # cannot import or instantiate an Alpaca client.
        alpaca_module = importlib.import_module("mide.alpaca")
        provider_module = importlib.import_module("mide.market_data_providers")
        client_factory = client_factory or provider_module.AlpacaProvider
        credential_checker = credential_checker or alpaca_module.credential_status
        client: MarketDataProvider = client_factory(api_key, secret, feed=settings.feed, timeout=8)
        try:
            environment = credential_checker(client)
            status.write(f"Alpaca credentials accepted ({environment} environment)")
        except Exception as exc:
            record_provider_failure(client.diagnostics, provider="Alpaca",
                operation="credential check", exception=exc,
                recovery_action="continue with available discovery sources")
            client.warnings.append(f"Alpaca credential check unavailable: {exc}")
        client.diagnostics["selected_provider"] = "ALPACA"
        logging.getLogger(__name__).warning("Walter live market-data provider: ALPACA")
    with scan_runtime_slot:
        progress = st.progress(0, text="Starting Walter Architecture")

    state = {"seeds": [], "reasons": {}, "snapshots": {}, "news": [],
             "candidates": [], "analyzed": [], "ranked": [],
             "stage_diagnostics": [], "scan_stage_counts": {},
             "runtime_stages": {},
             "expansion_candidate_ledger": []}
    universe_verification = UniverseVerification(
        client, feed=settings.feed, market_session=market_phase()
    )
    history = get_store()
    previous = history.latest_by_symbol()
    policy = ArchitecturePolicy(
        settings.min_price, settings.max_price, settings.max_free_float,
        settings.include_etfs,
    )

    def announce(number, detail=""):
        name = WALTER_STAGES[number - 1]
        message = f"{number}/8 {name}" + (f": {detail}" if detail else "")
        log(message)
        status.write(message)
        progress.progress((number - 1) / 8, text=message)

    @instrument_startup("loading universe")
    def discover():
        # Catalyst retrieval deliberately does not happen here. Discovery sources
        # alone establish the immutable membership of this scan.
        # Callable identity keeps injected/test discovery providers isolated while
        # the stable production callable still reuses one universe all session.
        cache_key = (
            f"{datetime.now().astimezone().date().isoformat()}:{settings.feed}:"
            f"{provider_name.upper()}:{id(build_seed_symbols)}"
        )
        cached = st.session_state.get("walter_session_universe_cache", {})
        universe_started = perf_counter()
        try:
            cached_entry = cached.get(cache_key)
            if cached_entry:
                seeds, reasons = cached_entry["seeds"], cached_entry["reasons"]
                if isinstance(client, LiveWebullProvider):
                    logging.getLogger(__name__).info(
                        "Webull universe construction exit before HTTP request: "
                        "session universe cache hit key=%s cached_symbol_count=%s "
                        "first_10_returned_symbols=%s",
                        cache_key, len(seeds), list(seeds[:10]),
                    )
            else:
                if isinstance(client, LiveWebullProvider):
                    logging.getLogger(__name__).info(
                        "Webull universe construction cache miss: invoking "
                        "build_seed_symbols → LiveWebullProvider.assets → "
                        "WebullOpenAPIClient.assets"
                    )
                discovery_parameters = inspect.signature(build_seed_symbols).parameters
                if "universe_verification" in discovery_parameters:
                    seeds, reasons = build_seed_symbols(
                        client, settings, [], universe_verification=universe_verification
                    )
                else:  # Test/deployment compatibility for an injected legacy callable.
                    seeds, reasons = build_seed_symbols(client, settings, [])
                cached = {cache_key: {"seeds": list(seeds), "reasons": dict(reasons)}}
                st.session_state.walter_session_universe_cache = cached
        except Exception as exc:
            record_provider_failure(
                client.diagnostics, provider="Alpaca Trading API", operation="universe discovery",
                exception=exc, recovery_action="stop scan and preserve last successful scan",
            )
            raise RuntimeError(f"Universe discovery failed: {exc}") from exc
        if not seeds:
            first_empty = client.diagnostics.get("universe_first_empty") or {
                "location": "app._run_live_pipeline.discover: session universe cache",
                "record_count": 0,
                "api_response": "<not available from cached universe>",
            }
            logging.getLogger(__name__).error(
                "UNIVERSE DISCOVERY ABORT record_count=0 first_empty_location=%s "
                "api_response=%r",
                first_empty["location"], first_empty.get("api_response"),
            )
            raise RuntimeError("Universe discovery returned zero eligible symbols")
        if isinstance(client, LiveWebullProvider):
            logging.getLogger(__name__).info(
                "WEBULL symbols discovered before streaming=%s", len(seeds)
            )
        state["universe_elapsed_ms"] = round((perf_counter() - universe_started) * 1000, 3)
        state["seeds"], state["reasons"] = seeds, reasons
        state["runtime_stages"]["Universe discovered"] = (
            runtime_stage_observation(seeds)
        )
        observe_runtime_collection_count(
            client.diagnostics, "universe discovered", seeds,
            statement="build_seed_symbols(...) returned seeds",
        )
        observe_runtime_collection_count(
            client.diagnostics, "seeds", state["seeds"],
            statement='state["seeds"], state["reasons"] = seeds, reasons',
        )
        state["scan_stage_counts"]["universe_discovered"] = len(seeds)
        price_started = perf_counter()
        prices = {}
        if isinstance(client, LiveWebullProvider):
            # Complete the Webull REST snapshot before Price Gate begins. The
            # provider starts its persistent stream only after this returns.
            try:
                prices = client.initialize_quotes(seeds, batch_size=settings.batch_size)
            except Exception as exc:
                record_provider_failure(
                    client.diagnostics, provider="Webull OpenAPI SDK", operation="initial quote snapshot",
                    exception=exc, affected_symbols=seeds,
                    recovery_action="stop scan and preserve last successful scan",
                )
                raise RuntimeError(f"Webull initial snapshot failed: {exc}") from exc
            if not prices:
                raise RuntimeError("Webull snapshot returned zero symbols")
        for offset in range(0, len(seeds), settings.batch_size):
            batch = seeds[offset:offset + settings.batch_size]
            try:
                if isinstance(client, LiveWebullProvider):
                    prices.update(client.latest_trades(batch, initialize=False))
                elif hasattr(client, "latest_trades"):
                    prices.update(client.latest_trades(batch))
                else:  # Compatibility for injected providers during migration.
                    minimal = client.snapshots(batch)
                    for symbol, snap in minimal.items():
                        trade, daily = snap.get("latestTrade") or {}, snap.get("dailyBar") or {}
                        prices[symbol] = float(trade.get("p") or daily.get("c") or 0)
            except Exception as exc:
                client.warnings.append(f"Price batch unavailable: {exc}")
                record_provider_failure(
                    client.diagnostics, provider=("Webull OpenAPI" if isinstance(client, LiveWebullProvider) else "Alpaca"), operation="latest prices",
                    exception=exc, affected_symbols=batch,
                    recovery_action="reject symbols with unavailable price evidence",
                )
        price_failures = sorted(set(seeds) - set(prices))
        state["price_elapsed_ms"] = round((perf_counter() - price_started) * 1000, 3)
        price_rows = [
            {"symbol": symbol, "price": prices.get(symbol)} for symbol in seeds
        ]
        state["stage_diagnostics"].append(stage_diagnostic(
            "Snapshot retrieval", price_rows,
            [row for row in price_rows if row["price"] is not None],
            rejection_reasons=("Snapshot unavailable" for _symbol in price_failures),
            fields=("price",),
        ))
        transitions = [{
            "transition_function_name": "minimal price retrieval for Price Gate",
            "input_count": len(seeds), "output_count": len(seeds),
            "removed_count": 0,
            "exact_reason_categories": ["price unavailable"],
            "affected_symbols_grouped_by_reason": {
                "price unavailable": price_failures
            },
        }]
        universe_verification.finish(
            seeds, transitions=transitions,
            entered_price_gate=set(seeds),
        )
        # Membership and provenance are fixed before Price Gate. Missing price
        # evidence produces an explicit gate decision and never changes Stage 0.
        provider = (client.diagnostics.get("market_data_sources", {}).get("universe_provider")
                    or getattr(client, "provider_name", client.__class__.__name__))
        universe_records = []
        for symbol in seeds:
            record = {"symbol": symbol, "price": prices.get(symbol)}
            record.update(
                provider=provider,
                sources=list(reasons.get(symbol, [])),
                discovery_reasons=list(reasons.get(symbol, [])),
            )
            universe_records.append(record)
        return universe_records

    def retrieve_market_data(records):
        started = perf_counter()
        symbols = [item["symbol"] for item in records]
        state["scan_stage_counts"]["snapshot_requests_sent"] = len(symbols)
        snapshots = {}
        for offset in range(0, len(symbols), settings.batch_size):
            batch = symbols[offset:offset + settings.batch_size]
            try:
                snapshots.update(client.snapshots(batch))
            except Exception as exc:
                client.warnings.append(f"Snapshot batch unavailable: {exc}")
                record_provider_failure(
                    client.diagnostics, provider=("Webull OpenAPI cache" if isinstance(client, LiveWebullProvider) else "Alpaca"), operation="market data snapshots",
                    exception=exc, affected_symbols=batch,
                    recovery_action="retain symbols with unusable data evidence",
                )
        state["snapshots"] = snapshots
        state["scan_stage_counts"]["snapshot_records_received"] = len(snapshots)
        refreshed = {item["symbol"]: item for item in snapshot_identity_records(snapshots)}
        state["runtime_stages"]["Symbols loaded"] = runtime_stage_observation(
            list(refreshed.values())
        )
        state["scan_stage_counts"]["snapshot_records_normalized"] = len(refreshed)
        inspect_session_state_dataframes(st.session_state)
        # ``state["snapshots"]`` is the application cache consumed by every
        # subsequent stage, regardless of which provider filled it.
        state["scan_stage_counts"]["snapshot_cache_populated"] = len(state["snapshots"])
        for record in records:
            update = refreshed.get(record["symbol"])
            if update:
                record.update(update)
            else:
                record.update(snapshot_status="unavailable", data_usable=False)
        snapshot_elapsed_ms = round((perf_counter() - started) * 1000, 3)
        state["market_data_timing"] = {
            "stage": "Market Data Retrieval", "input_count": len(symbols),
            "output_count": len(snapshots),
            "elapsed_ms": snapshot_elapsed_ms,
            "percentage_reduction": round((1 - len(symbols) / len(state["seeds"])) * 100, 2)
            if state["seeds"] else 0.0,
            **price_gate_savings_metrics(
                len(state["seeds"]), len(symbols), settings.batch_size,
                state["price_elapsed_ms"], snapshot_elapsed_ms,
            ),
        }

    def catalyst(records):
        news_provider = (
            UnavailableNewsProvider(
                "Webull raw news unavailable",
                "Webull OpenAPI exposes summaries, not ticker-level articles; configure a separately licensed NewsProvider for catalysts",
            )
            if isinstance(client, LiveWebullProvider)
            else MarketDataNewsProvider(client)
        )
        service = NewsService([news_provider])
        symbols = [item["symbol"] for item in records]
        try:
            news_items = service.fetch(symbols=symbols, force_lookback=True)
        except Exception as exc:
            client.warnings.append(f"News unavailable; scan continued: {exc}")
            news_items = []
        state["news"] = news_items
        client.diagnostics["news_coverage"] = dict(service.metrics)
        client.diagnostics.setdefault("provider_failures", []).extend(
            service.metrics.get("provider_failure_diagnostics", [])
        )
        client.diagnostics["news_evidence"] = symbol_news_evidence(news_items)
        indexed = index_news(news_items)
        decisions = {}
        for item in records:
            symbol = item["symbol"]
            news = indexed.get(symbol)
            updates = {"discovery_reasons": state["reasons"].get(symbol, [])}
            if news:
                updates.update(headline=news.get("headline", ""),
                               catalyst_score=news.get("catalyst_score", 0),
                               news_flags=news.get("flags", []))
            decisions[symbol] = Decision(
                True, "Catalyst", "Catalyst evidence assessed" if news else "No catalyst found",
                updates,
            )
        assessed = [dict(item, **decisions[item["symbol"]].updates) for item in records]
        state["stage_diagnostics"].append(stage_diagnostic(
            "Catalyst detection", assessed, assessed,
            fields=("headline", "catalyst_score"),
        ))
        return decisions

    def free_float(records):
        symbols = [item["symbol"] for item in records]
        selected = {
            symbol: state["snapshots"][symbol]
            for symbol in symbols if symbol in state["snapshots"]
        }
        fmp_key = get_secret("FMP_API_KEY") or get_secret(
            "FINANCIAL_MODELING_PREP_API_KEY"
        )
        if fmp_key:
            provider = FreeFloatClient(fmp_key, timeout=12)
            try:
                _count, errors = enrich_snapshots_with_free_float(selected, provider)
            except Exception as exc:
                errors = {symbol: str(exc) for symbol in symbols}
                record_provider_failure(
                    client.diagnostics, provider="Financial Modeling Prep",
                    operation="free-float lookup", exception=exc,
                    affected_symbols=symbols,
                    recovery_action="fall back to the next free-float provider",
                )
            client.diagnostics["free_float_provider"] = "Financial Modeling Prep"
            if errors:
                client.warnings.append(
                    f"FMP free-float unavailable for {len(errors)} symbols"
                )
                for symbol, error in errors.items():
                    record_provider_failure(
                        client.diagnostics, provider="Financial Modeling Prep",
                        operation="free-float lookup", exception=RuntimeError(error),
                        affected_symbols=[symbol],
                        recovery_action="fall back to Yahoo Finance; preserve snapshot data",
                    )
        if hasattr(client, "enrich_free_float"):
            try:
                client.enrich_free_float(state["snapshots"], symbols)
            except Exception as exc:
                client.warnings.append(f"Free-float fallback unavailable: {exc}")
                record_provider_failure(
                    client.diagnostics, provider="Yahoo Finance",
                    operation="free-float fallback", exception=exc,
                    affected_symbols=symbols,
                    recovery_action="skip unavailable enrichment and preserve snapshot data",
                )
        refreshed = {
            item["symbol"]: item
            for item in snapshot_identity_records(state["snapshots"])
        }
        decisions = {}
        for item in records:
            symbol = item["symbol"]
            update = refreshed.get(symbol, {})
            decisions[symbol] = free_float_decision(
                update, policy.max_free_float
            )
        return decisions

    def participation(records):
        symbols = {item["symbol"] for item in records}
        eligible_snapshots = {
            symbol: snap for symbol, snap in state["snapshots"].items()
            if symbol in symbols
        }
        state["scan_stage_counts"]["prefilter_input"] = len(eligible_snapshots)
        candidates = prefilter_snapshots(eligible_snapshots, settings)
        state["runtime_stages"]["Prefiltered"] = runtime_stage_observation(
            candidates
        )
        state["scan_stage_counts"]["prefilter_output"] = len(candidates)
        candidate_symbols = {item["symbol"] for item in candidates}
        prefilter_decisions = {
            symbol: prefilter_decision(symbol, snap, settings)
            for symbol, snap in eligible_snapshots.items()
        }
        prefilter_reasons = [
            decision["reason"] for symbol, decision in prefilter_decisions.items()
            if symbol not in candidate_symbols
        ]
        snapshot_metrics = []
        for symbol, snap in eligible_snapshots.items():
            snapshot_metrics.append({
                "symbol": symbol,
                "latest_trade": (snap.get("latestTrade") or {}).get("p"),
                "latest_quote_bid": (snap.get("latestQuote") or {}).get("bp"),
                "latest_quote_ask": (snap.get("latestQuote") or {}).get("ap"),
                "daily_volume": (snap.get("dailyBar") or {}).get("v"),
                "previous_close": (snap.get("prevDailyBar") or {}).get("c"),
            })
        state["stage_diagnostics"].append(stage_diagnostic(
            "Prefilter", snapshot_metrics, candidates,
            rejection_reasons=prefilter_reasons,
            fields=("latest_trade", "latest_quote_bid", "latest_quote_ask",
                    "daily_volume", "previous_close"),
        ))
        candidate_by_symbol = {item["symbol"]: item for item in candidates}
        state["scan_stage_counts"]["structure_engine_input"] = len(candidates)
        history_symbols = sum(
            1 for item in candidates if is_valid_us_symbol(item.get("symbol"))
        )
        logging.getLogger(__name__).info(
            "Participation history submission stage_input=%d snapshot_prefilter_output=%d "
            "symbols_submitted=%d history_batches=%d",
            len(records), len(candidates), history_symbols,
            (history_symbols + 19) // 20,
        )
        analyzed = analyze_candidates(
            client, candidates, index_news(state["news"]), state["reasons"]
        )
        analyzed = history.enrich_velocity(analyzed, previous=previous)
        analyzed_by_symbol = {item["symbol"]: item for item in analyzed}
        state["candidates"], state["analyzed"] = candidates, analyzed
        state["runtime_stages"]["Analyzed"] = runtime_stage_observation(analyzed)
        observe_runtime_collection_count(
            client.diagnostics, "candidates", state["candidates"],
            statement="candidates = prefilter_snapshots(eligible_snapshots, settings)",
        )
        observe_runtime_collection_count(
            client.diagnostics, "analyzed", state["analyzed"],
            statement="analyzed = history.enrich_velocity(analyze_candidates(...))",
        )
        result = {}
        for item in records:
            symbol = item["symbol"]
            if symbol not in candidate_by_symbol:
                prefilter = prefilter_decisions[symbol]
                result[symbol] = Decision(
                    False, "Participation",
                    prefilter["failed_rule"] or "Market participation prefilter not satisfied",
                    evidence={
                        "failed_metrics": prefilter["failed_metrics"],
                        "measured_values": prefilter["measured_values"],
                        "thresholds": prefilter["thresholds"],
                        "exact_reason": prefilter["reason"],
                    },
                )
            elif symbol not in analyzed_by_symbol:
                candidate = candidate_by_symbol[symbol]
                result[symbol] = Decision(
                    False, "Participation", "Missing or insufficient intraday bars",
                    evidence={"failed_metrics": [{
                        "metric": "intraday_bars",
                        "measured": candidate.get("intraday_bar_count"),
                        "operator": "unavailable_or_insufficient",
                        "threshold": "provider/timeframe minimum",
                    }], "available_snapshot_metrics": {
                        key: candidate.get(key) for key in (
                            "volume", "dollar_volume", "prev_volume", "spread_pct"
                        )
                    }},
                )
            else:
                analyzed_record = analyzed_by_symbol[symbol]
                result[symbol] = Decision(True, "Participation", "Participation evidence measured", analyzed_record)
        state["stage_diagnostics"].append(stage_diagnostic(
            "Participation", candidates, analyzed,
            rejection_reasons=(
                "Insufficient intraday data for assessment"
                for item in candidates if item["symbol"] not in analyzed_by_symbol
            ),
            fields=("volume", "dollar_volume", "prev_volume", "spread_pct"),
        ))
        return result

    def expansion(records):
        state["runtime_stages"]["Candidates"] = runtime_stage_observation(records)
        result = {}
        for item in records:
            advanced, audit, confluence = behavioral_decision(item)
            state["expansion_candidate_ledger"].append(
                expansion_candidate_diagnostic(item, audit, confluence)
            )
            result[item["symbol"]] = Decision(
                advanced, "Expansion", f"Confluence {confluence}",
                {"decision_funnel": audit, "confluence_score": confluence,
                 "eligible": True,
                 "final_decision": "Attention Earned" if advanced else "Rejected",
                 "candidate_status": item.get("candidate_status", "Entry Ready") if advanced else "Removed",
                 "scanner_version": "Walter Architecture v1.0"},
            )
        state["pre_expansion_candidates"] = pre_expansion_candidate_diagnostics(
            records, result
        )
        expanded = [item for item in records if result[item["symbol"]].passed]
        state["stage_diagnostics"].append(stage_diagnostic(
            "Expansion", records, expanded,
            rejection_reasons=(
                result[item["symbol"]].reason for item in records
                if not result[item["symbol"]].passed
            ),
            fields=("participation_score", "volume_acceleration", "vwap_relation"),
        ))
        return result

    class RuntimeStore:
        def persist(self, results):
            # The complete ledger, including rejected candidates, is durable before
            # Mission Publication makes qualified records visible.
            history.append(results)

    def rank(records):
        ranked_records = sorted(records, key=trader_priority_sort_key)
        state["runtime_stages"]["Ranked"] = runtime_stage_observation(
            ranked_records
        )
        observe_runtime_collection_count(
            client.diagnostics, "ranked", ranked_records,
            statement=(
                "WalterArchitectureV1._assess(\"Expansion Assessment\", ...) "
                "then sorted(records, key=trader_priority_sort_key)"
            ),
        )
        return ranked_records

    def publish(records):
        state["runtime_stages"]["Published"] = runtime_stage_observation(records)
        observe_runtime_collection_count(
            client.diagnostics, "published", records,
            statement="WalterArchitectureV1.publish(records)",
        )
        state["ranked"] = records
        observe_runtime_collection_count(
            client.diagnostics, 'state["ranked"]', state["ranked"],
            statement='state["ranked"] = records',
        )
        # Transitional identity alias for integrations invoked during the scan;
        # it is the exact pipeline list, never a second result container.
        st.session_state.records = records

    architecture = WalterArchitectureV1(
        policy=policy,
        discover=discover,
        catalyst=catalyst,
        participation=participation,
        expansion=expansion,
        free_float=free_float,
        rank=rank,
        store=RuntimeStore(),
        publish=publish,
        stage_observer=lambda number, _name, candidates: announce(
            number, f"{len(candidates)} candidates" if number > 1 else ""
        ),
        failure_observer=lambda stage, symbol, exc: record_provider_failure(
            client.diagnostics, provider="Walter candidate processing",
            operation=stage, exception=exc, affected_symbols=[symbol],
            recovery_action="mark only the affected candidate Technical Failure and continue",
        ),
        ledger=st.session_state.walter_candidate_ledger,
        after_price_gate=retrieve_market_data,
    )
    scan_context(st.session_state).pipeline = architecture
    ledger = architecture.run()
    ranked = state["ranked"]
    # Entry readiness is an observational view of the already-completed
    # Expansion decision. It does not add a gate or alter ranking membership.
    state["stage_diagnostics"].append(stage_diagnostic(
        "Entry readiness", ranked, ranked,
        fields=("candidate_status", "qualified_for_entry", "trigger_diagnostics"),
    ))
    state["stage_diagnostics"].append(stage_diagnostic(
        "Ranking", ranked, ranked,
        fields=("mission_rank", "conviction_score", "participation_score"),
    ))
    # Outcome measurement is strictly downstream of publication and receives
    # detached snapshots, never the authoritative candidate objects.
    try:
        MissionOutcomeStore().process_scan(
            [dict(record) for record in ranked],
            timestamp=datetime.now(timezone.utc),
        )
    except (OSError, ValueError, TypeError) as exc:
        client.warnings.append(f"Mission outcome measurement unavailable: {exc}")
    operational = dict(architecture.operational_summary)
    operational["provider_failures"] = len(
        client.diagnostics.get("provider_failures", [])
    )
    client.diagnostics["walter_architecture"] = {
        "version": "1.0", "stages": list(architecture.trace),
        "terminal_outcomes": {
            outcome: sum(item.get("terminal_outcome") == outcome for item in ledger)
            for outcome in ("Rejected", "Qualified and Ranked", "Technical Failure")
        },
        "operational_health": operational,
        "verification": architecture.verification_report,
        "universe_verification": universe_verification.report,
    }
    diagnostic_order = {
        name: position for position, name in enumerate((
            "Snapshot retrieval", "Prefilter", "Catalyst detection",
            "Participation", "Expansion", "Entry readiness", "Ranking",
        ))
    }
    stage_diagnostics = sorted(
        state["stage_diagnostics"],
        key=lambda item: diagnostic_order.get(item["stage"], len(diagnostic_order)),
    )
    client.diagnostics["post_universe_pipeline"] = {
        "universe_count": len(state["seeds"]),
        "stages": stage_diagnostics,
        "table": diagnostics_table(stage_diagnostics),
        "pre_expansion_candidates": state.get("pre_expansion_candidates", []),
    }
    timing_summary = []
    for item in architecture.trace:
        elapsed_ms = item["execution_time_ms"]
        if item["stage"] == "Universe Construction":
            elapsed_ms = state["universe_elapsed_ms"]
        elif item["stage"] == "Price Gate":
            elapsed_ms = state["price_elapsed_ms"] + item["execution_time_ms"]
        timing_summary.append({
            "stage": item["stage"], "input_count": item["input_count"],
            "output_count": item["output_count"], "elapsed_ms": round(elapsed_ms, 3),
            "percentage_reduction": round(
                (1 - item["output_count"] / item["input_count"]) * 100, 2
            ) if item["input_count"] else 0.0,
        })
        if item["stage"] == "Price Gate":
            timing_summary.append(state["market_data_timing"])
    timing_summary.append({
        "stage": "Total Scan", "input_count": len(state["seeds"]),
        "output_count": len(ranked),
        "elapsed_ms": round((perf_counter() - scan_started) * 1000, 3),
        "percentage_reduction": round(
            (1 - len(ranked) / len(state["seeds"])) * 100, 2
        ) if state["seeds"] else 0.0,
    })
    client.diagnostics["pipeline_timing_summary"] = timing_summary
    state["scan_stage_counts"]["final_candidates"] = len(ranked)
    client.diagnostics["scan_stage_counts"] = dict(state["scan_stage_counts"])
    if isinstance(client, LiveWebullProvider):
        client.diagnostics["production_webull_runtime_stages"] = dict(
            state["runtime_stages"]
        )
        client.diagnostics["production_webull_runtime_report_pending"] = True
        client.diagnostics["active_pipeline_sources"] = client.pipeline_sources()
    runtime_recorder = get_flight_recorder()
    recorder_runtime_diagnostics = {}
    flight_scan = record_scan_safely(
        runtime_recorder, seeds=state["seeds"],
        discovery_reasons=state["reasons"], snapshots=state["snapshots"],
        candidates=state["candidates"], analyzed=state["analyzed"],
        records=ranked, settings=settings, scanner_v2=True,
        expansion_candidate_ledger=state["expansion_candidate_ledger"],
        runtime_diagnostics=recorder_runtime_diagnostics,
    )
    client.diagnostics["flight_recorder_runtime"] = recorder_runtime_diagnostics
    if flight_scan is not None:
        client.diagnostics["flight_recorder"] = flight_scan
    log("Timing summary: " + json.dumps(timing_summary, separators=(",", ":")))
    progress.progress(1.0, text="Walter Architecture complete")
    status.update(label=f"Scan complete: {len(ranked)} ranked records",
                  state="complete", expanded=False)
    return (ranked, len(state["seeds"]), len(state["candidates"]),
            list(client.warnings), dict(client.diagnostics))


def run_live(
    scanner_version: str = "Walter Architecture v1.0",
    *,
    client_factory=None,
    credential_checker=None,
    provider_name: str = "ALPACA",
):
    """Run and report the complete live pipeline without leaving a LIVE spinner.

    This boundary deliberately covers status creation as well as every discovery,
    market-data, analysis, and persistence stage. It records the traceback and
    returns a completed degraded result so no unexpected exception can terminate
    the runtime.
    """
    status = None
    try:
        with scan_runtime_slot:
            status = st.status("Walter is scanning…", expanded=True)
        architecture = scanner_implementation(scanner_version).for_runtime(
            lambda: _run_live_pipeline(
                scanner_version,
                status=status,
                client_factory=client_factory,
                credential_checker=credential_checker,
                provider_name=provider_name,
            )
        )
        with startup_step("beginning scanner"):
            return architecture.run()
    except Exception as exc:
        logging.getLogger(__name__).exception("Live scan pipeline failed")
        log(f"Live scan pipeline failed: {type(exc).__name__}: {exc}")
        if status is not None:
            try:
                status.update(
                    label=f"Scan failed: {type(exc).__name__}: {exc}",
                    state="error",
                    expanded=True,
                )
            except Exception:
                logging.getLogger(__name__).exception(
                    "Could not update failed live-scan status"
                )
        # This is the final containment boundary. A UI, persistence, malformed
        # response, or unexpected candidate error must never take Walter down.
        diagnostics = {"provider_failures": []}
        record_provider_failure(
            diagnostics, provider="Walter Runtime", operation="live scan",
            exception=exc, recovery_action="return an empty completed scan and retry next cycle",
        )
        if status is not None:
            try:
                status.update(
                    label=f"Scan complete with recovery: {type(exc).__name__}",
                    state="complete", expanded=False,
                )
            except Exception:
                pass
        diagnostics["scan_completed"] = False
        return [], 0, 0, [f"Recovered live scan failure: {exc}"], diagnostics


should_scan = False

if use_demo or mode == "Demo":
    demo_result = evaluate_decision_funnel(demo_records())
    store_completed_scan(st.session_state, CompletedScan(
        provider=None, records=demo_result, diagnostics={}, warnings=[],
        symbols_sampled=len(demo_result), prefilter_count=len(demo_result),
        completed_at=datetime.now().astimezone(), source_label="Demonstration data",
    ))
else:
    due = (
        mode.startswith("Live ")
        and auto_refresh
        and live_possible
        and not st.session_state.scan_in_progress
        and (
            completed_scan_for_view(st.session_state, "scheduler") is None
            or (
                datetime.now().astimezone()
                - completed_scan_for_view(st.session_state, "scheduler").completed_at
            ).total_seconds()
            >= settings.refresh_seconds
        )
    )
    should_scan = st.session_state[SCAN_REQUESTED_KEY] or due

if mode.startswith("Live ") and should_scan and not st.session_state[STOP_REQUESTED_KEY]:
    st.session_state.last_scan_attempt = datetime.now().astimezone()
    try:
        # Resolve the watchdog dynamically: a deployment may have replaced the
        # module while this Streamlit session still holds older app globals.
        repair_mide_module_links()
        watchdog = importlib.import_module("mide.watchdog").PROCESS_SCAN_WATCHDOG
        records, universe_count, prefiltered, warnings, diagnostics = watchdog.run(
            lambda: run_live(scanner_version, provider_name=selected_provider),
            before_retry=repair_mide_module_links,
            on_acquired=lambda: begin_scheduled_scan(st.session_state),
            on_finished=lambda: finish_scan(st.session_state),
        )
        if diagnostics.get("scan_completed", True):
            completed_at = datetime.now().astimezone()
            scan = CompletedScan(
                provider=selected_provider,
                records=records,
                diagnostics=diagnostics,
                warnings=warnings,
                symbols_sampled=universe_count,
                prefilter_count=prefiltered,
                completed_at=completed_at,
                source_label=(
                    f"Live {selected_provider} · {universe_count} symbols sampled · "
                    f"{prefiltered} prefiltered"
                ),
            )
            observe_runtime_collection_count(
                diagnostics, "CompletedScan.records", scan.records,
                statement="scan = CompletedScan(records=records, ...)",
            )
            publish_scan_result(st.session_state, scan)
            st.session_state.scan_failure_count = 0
        else:
            st.session_state.scan_failure_count += 1
            actual_failure = warnings[-1] if warnings else "Unknown provider failure"
            st.error(
                f"Scan stopped; the last successful scan remains displayed. {actual_failure}"
            )
    except ScanAlreadyRunning as exc:
        log(f"Scan deferred: {exc}")
        st.info("Another Walter session is scanning. This session will retry automatically.")
    except Exception as exc:
        st.session_state.scan_failure_count += 1
        log(f"Scan failed: {type(exc).__name__}: {exc}")
        st.error(f"Live scan could not complete: {exc}")
        st.info(
            "Walter remains online and will retry automatically with backoff."
        )
# The sidebar slot keeps its original layout position, but the bytes are read
# only after this run's scan (if any) has finished recording.
with flight_recorder_download_slot:
    st.download_button(
        "Download Flight Recorder",
        data=flight_recorder_download_bytes(get_flight_recorder()),
        file_name="flight_recorder.jsonl",
        mime="application/x-ndjson",
        use_container_width=True,
    )

completed_scan = completed_scan_for_view(st.session_state, "Radar")
records = completed_scan.records if completed_scan else []
api_warnings = completed_scan.warnings if completed_scan else []
scan_diagnostics = completed_scan.diagnostics if completed_scan else {}
updated = completed_scan.completed_at if completed_scan else None
current_rejections = scan_diagnostics.get("rejected_candidates", [])
if current_rejections:
    signature = tuple(
        (row.get("Symbol"), row.get("Stage"), row.get("Rule"), row.get("Timestamp"))
        for row in current_rejections
    )
    if signature != st.session_state.get("rejection_diagnostics_signature"):
        st.session_state.rejected_candidate_history = (
            list(current_rejections)
            + list(st.session_state.get("rejected_candidate_history", []))
        )[:100]
        st.session_state.rejection_diagnostics_signature = signature
updated_text = format_eastern_time(updated)
clock = market_clock()

if records:
    with st.expander("Decision Funnel audit trails", expanded=False):
        for record in records:
            st.markdown(decision_funnel_markup(record), unsafe_allow_html=True)

actionable_records = actionable_candidate_records(records)
if completed_scan:
    observe_runtime_collection_count(
        scan_diagnostics, "actionable_candidate_records(records)", actionable_records,
        statement="actionable_records = actionable_candidate_records(records)",
    )
rejected_records = st.session_state.get("rejected_candidate_history", [])
display_records = (
    actionable_records
    if show_pass
    else [r for r in actionable_records if r.get("status") not in {"PASS", "Removed"}]
)
if completed_scan:
    observe_runtime_collection_count(
        scan_diagnostics, "dashboard render", display_records,
        statement=(
            "display_records = actionable_records" if show_pass else
            'display_records = [r for r in actionable_records if r.get("status") '
            'not in {"PASS", "Removed"}]'
        ),
    )
    runtime_stages = scan_diagnostics.get("production_webull_runtime_stages")
    if (
        scan_diagnostics.get("production_webull_runtime_report_pending")
        and isinstance(runtime_stages, dict)
    ):
        runtime_stages["Dashboard"] = runtime_stage_observation(display_records)
        print_scan_stage_counts(runtime_stages)
        scan_diagnostics["production_webull_runtime_report_pending"] = False

mission = walter_mission_control(actionable_records)
focus_count = int(mission["primary"] is not None) + int(
    mission["secondary"] is not None
)
escalation_count = sum(
    escalation_snapshot(record)["state"] in {"Watch Closely", "Entry Window Open"}
    for record in actionable_records
)
auto_scan = (
    f"Every {settings.refresh_seconds} sec"
    if mode.startswith("Live ") and auto_refresh
    else "Disabled"
)
with mission_header_slot:
    st.markdown(
        mission_control_header_markup(
            live=mode.startswith("Live "),
            market_phase=clock.phase,
            market_time=clock.time_text,
            symbols_sampled=completed_scan.symbols_sampled if completed_scan else 0,
            prefilter_count=completed_scan.prefilter_count if completed_scan else 0,
            candidate_count=len(actionable_records),
            focus_count=focus_count,
            escalation_count=escalation_count,
            auto_scan=auto_scan,
            funnel_counts=scan_diagnostics.get("funnel_counts", {}),
        ),
        unsafe_allow_html=True,
    )
integrity_report = scan_integrity_report(
    records,
    live=mode.startswith("Live "),
    funnel_counts=scan_diagnostics.get("funnel_counts", {}),
    provider_diagnostics=None,
)
with scan_trust_slot:
    st.markdown(data_integrity_markup(integrity_report), unsafe_allow_html=True)
with market_session_slot:
    st.markdown(
        market_session_quality_markup(actionable_records), unsafe_allow_html=True
    )
with early_setup_slot:
    render_early_setups(records)
with mission_plan_slot:
    render_walter_mission_control(actionable_records)

focus_records = [
    item["record"]
    for item in (mission["primary"], mission["secondary"])
    if item is not None
]
if updated:
    feed_snapshot, feed_events = update_opportunity_feed(
        focus_records,
        st.session_state.opportunity_feed_snapshot,
        st.session_state.opportunity_feed_events,
        updated,
    )
    st.session_state.opportunity_feed_snapshot = feed_snapshot
    st.session_state.opportunity_feed_events = feed_events
with opportunity_feed_slot:
    render_live_opportunity_feed(st.session_state.opportunity_feed_events)

arm_live_clock_engine(
    mode.startswith("Live ") and auto_refresh and live_possible,
    settings.refresh_seconds,
    updated,
    st.session_state.last_scan_attempt,
    retry_seconds=min(60, 5 * (2 ** min(st.session_state.scan_failure_count, 3))),
)

with escalation_engine_slot:
    render_escalation_engine(actionable_records)

with system_status_panel:
    st.markdown(
        f"**Last Scan:** <span id='walter-last-scan'>{html.escape(updated_text)}</span>",
        unsafe_allow_html=True,
    )
    status_columns = st.columns(3)
    status_columns[0].metric("Symbols Sampled", completed_scan.symbols_sampled if completed_scan else 0)
    status_columns[1].metric("Prefiltered", completed_scan.prefilter_count if completed_scan else 0)
    status_columns[2].metric("Ranked", len(records))
    st.caption(completed_scan.source_label if completed_scan else "No scan has been run")
    if updated:
        st.success(f"Scan Complete · {len(records)} ranked records")
        st.progress(1.0, text="Progress: complete")
    else:
        st.progress(0.0, text="Progress: waiting for first scan")

    if not records:
        if updated:
            st.warning("The scan completed but produced no ranked records.")
            if scan_diagnostics:
                st.subheader("Scan diagnostics")
                st.json(scan_diagnostics)
            for warning in api_warnings:
                st.warning(warning)
        else:
            st.info(
                "Dashboard loaded successfully. Walter will scan automatically in live mode, or press **Run live scan** to begin now."
            )

    operational_health = (
        (scan_diagnostics.get("walter_architecture") or {}).get("operational_health")
        if isinstance(scan_diagnostics, dict) else None
    )
    if operational_health:
        st.subheader("Walter operational diagnostics")
        health_columns = st.columns(5)
        health_columns[0].metric("Discovered", operational_health["symbols_discovered"])
        health_columns[1].metric("Rejected", operational_health["symbols_rejected"])
        health_columns[2].metric("Ranked", operational_health["symbols_ranked"])
        health_columns[3].metric("Published", operational_health["symbols_published"])
        health_columns[4].metric("Provider failures", operational_health["provider_failures"])
        st.dataframe(
            operational_health["stage_metrics"], use_container_width=True,
            hide_index=True,
        )
        st.caption(
            "Healthy · persistence completed before publication · publication identity verified"
        )

    post_universe = (
        scan_diagnostics.get("post_universe_pipeline")
        if isinstance(scan_diagnostics, dict) else None
    )
    if post_universe:
        st.subheader("Diagnostics")
        st.caption(
            f"Post-universe symbol accounting from "
            f"{post_universe.get('universe_count', 0):,} loaded symbols."
        )
        st.dataframe(
            post_universe.get("table", []), use_container_width=True,
            hide_index=True,
        )
        st.markdown("**Top 20 candidates before Expansion**")
        st.caption(
            "Ranked from the records entering Expansion, including candidates "
            "that the Expansion gate subsequently rejected."
        )
        pre_expansion = post_universe.get("pre_expansion_candidates", [])
        if pre_expansion:
            st.dataframe(pre_expansion, use_container_width=True, hide_index=True)
        else:
            st.info("No candidates reached Expansion in the latest scan.")

    verification = (
        (scan_diagnostics.get("walter_architecture") or {}).get("verification")
        if isinstance(scan_diagnostics, dict) else None
    )
    if verification:
        st.subheader("Architecture Verification Dashboard")
        integrity = int(verification.get("overall_integrity", 0))
        st.metric("Overall Integrity", f"{integrity}%")
        contract_rows = [
            {"Contract": name, "Integrity": "✔" if passed else "✘"}
            for name, passed in verification.get("contracts", {}).items()
        ]
        st.dataframe(contract_rows, use_container_width=True, hide_index=True)
        st.markdown("**Candidate Accounting**")
        st.dataframe(
            verification.get("accounting", []), use_container_width=True,
            hide_index=True,
        )
        if verification.get("failures"):
            st.error("Architecture contract verification failed")
            st.dataframe(
                verification["failures"], use_container_width=True, hide_index=True,
            )
        else:
            st.success("Every Walter architecture contract passed.")
        if inspect_symbol:
            st.markdown(f"**Candidate Trace — {inspect_symbol}**")
            trace_rows = candidate_trace(
                list(st.session_state.walter_candidate_ledger.records.values()),
                inspect_symbol,
            )
            if trace_rows:
                st.dataframe(trace_rows, use_container_width=True, hide_index=True)
            else:
                st.info("No recorded candidate identity matches this symbol.")

    st.markdown("#### Legacy Candidate Diagnostics")
    if inspect_symbol:
        st.subheader(f"Symbol lookup: {inspect_symbol}")
        match = next((r for r in records if r.get("symbol") == inspect_symbol), None)
        if match:
            st.success(
                f"{inspect_symbol} was analyzed and ranked {match.get('status', 'UNKNOWN')}."
            )
            st.write(
                "; ".join(match.get("reasons", [])) or "No elevated evidence recorded."
            )
            st.write(
                "Cautions: "
                + ("; ".join(match.get("cautions", [])) or "None recorded.")
            )
        else:
            st.warning(f"{inspect_symbol} is not in the current ranked set.")

    strengthening = (
        scan_diagnostics.get("strengthening")
        if isinstance(scan_diagnostics, dict)
        else None
    )
    if strengthening:
        st.subheader("Strengthening qualification")
        c1, c2 = st.columns(2)
        c1.metric(
            "Candidates discovered", strengthening.get("candidates_discovered", 0)
        )
        c2.metric("Candidates rejected", strengthening.get("candidates_rejected", 0))
        st.write("Rejected by first rule")
        st.json(strengthening.get("rejected_by_rule", {}))
        for decision in strengthening.get("decisions", []):
            symbol = decision.get("symbol", "UNKNOWN")
            with st.expander(
                f"{symbol} — {decision.get('status', 'Strengthening decision')}",
                expanded=False,
            ):
                st.markdown(f"**{symbol}**")
                st.markdown(decision.get("status", "Strengthening decision"))
                failed_structure_reasons = (
                    decision.get("failed_structure_gate_reasons") or []
                )
                if failed_structure_reasons:
                    st.markdown("**Failed Structure Gate reasons**")
                    for reason in failed_structure_reasons:
                        st.write(f"✗ {reason}")
                for check in decision.get("checks", []):
                    mark = "✓" if check.get("passed") else "✗"
                    st.write(f"{mark} {check.get('rule')}")
                    if not check.get("passed") and decision.get(
                        "first_rejection_rule"
                    ) == check.get("rule"):
                        break
                if decision.get("first_rejection_rule"):
                    st.caption(
                        f"First rejection rule: {decision.get('first_rejection_rule')}"
                    )
                if decision.get("volume_pace"):
                    st.write("Volume Pace Intelligence diagnostics")
                    st.json(decision.get("volume_pace"))
                if decision.get("vwap_gate"):
                    st.write("VWAP gate diagnostics")
                    st.json(decision.get("vwap_gate"))
    elif not inspect_symbol:
        st.caption("No diagnostics recorded for this scan yet.")
    st.caption(f"{clock.phase} — Rankings describe evidence only.")

state_changes = escalation_state_changes(actionable_records)
new_early_symbols, active_early_symbols = newly_entered_symbols(
    records, st.session_state.active_early_setup_symbols
)
st.session_state.active_early_setup_symbols = active_early_symbols
state_change_signature = "|".join(
    f"{item['symbol']}:{item['from']}->{item['to']}" for item in state_changes
)
alert_phrase = escalation_alert_phrase(actionable_records) or scan_alert_phrase(
    actionable_records
)
entry_alert_open = "Entry Window" in alert_phrase or "Entry Ready" in alert_phrase
if alerts and new_early_symbols and not entry_alert_open:
    coiled = next(
        record
        for record in records
        if str(record.get("symbol") or "").upper() == new_early_symbols[0]
    )
    structure = coiled.get("structure") or {}
    float_millions = structure.get("float_millions")
    float_phrase = (
        f" Float {float(float_millions):.1f} million."
        if float_millions is not None
        else ""
    )
    play_alert(
        "assets/alert.wav",
        (
            f"{new_early_symbols[0]}. Coiling. VWAP {structure.get('vwap_status', 'developing')}. "
            f"SuperTrend {float(structure.get('supertrend_distance_pct') or 0):.2f} percent away. "
            f"Participation {'accelerating' if structure.get('participation_accelerating') else 'steady'}."
            f"{float_phrase} Probability of breakout {float(structure.get('probability_of_breakout') or 0):.0f} percent."
        ),
        alert_voice_for_session(),
    )
elif alerts and alert_phrase:
    # Escalation transitions are audible once per distinct scan transition, rather
    # than replaying whenever Streamlit reruns for an unrelated widget change.
    if (
        not state_change_signature
        or state_change_signature != st.session_state.last_escalation_alert
    ):
        play_alert("assets/alert.wav", alert_phrase, alert_voice_for_session())
        if state_change_signature:
            st.session_state.last_escalation_alert = state_change_signature

tab_names = [
        "Radar",
        "Diagnostics",
        "Session Replay",
        "Trade Outcomes",
        "What changed",
        "Data validation",
        "Method",
    ]
active_tab = st.radio(
    "View", tab_names, horizontal=True, key="active_dashboard_tab",
    help="Diagnostic views are loaded only when selected to keep memory bounded.",
)
if active_tab == "Radar":
    view_scan = completed_scan_for_view(st.session_state, "Radar")
    if not display_records:
        st.success("No stock currently deserves elevated attention.")
    else:
        radar_sort = st.selectbox(
            "Sort candidates by",
            ("Walter Priority", "RS Score"),
            help="RS Score sorting is presentation-only and never changes qualification.",
        )
        for section_name, section_records, expanded in scanner_v2_display_sections(
            display_records
        ):
            if not section_records:
                continue
            with st.expander(
                f"{section_name.upper()} ({len(section_records)})", expanded=expanded
            ):
                sort_key = (
                    (lambda record: float(record.get("relative_strength_score", 0) or 0))
                    if radar_sort == "RS Score"
                    else trader_priority_sort_key
                )
                sorted_records = sorted(section_records, key=sort_key, reverse=True)
                for record in sorted_records[:10]:
                    opportunity_card(record)
                st.dataframe(
                    radar_table(sorted_records), width="stretch", hide_index=True
                )
if active_tab == "Diagnostics":
    view_scan = completed_scan_for_view(st.session_state, "Diagnostics")
    st.subheader("WEBULL SDK RUNTIME INSPECTION")
    st.caption(
        "Temporary read-only inspection of the SDK installed in this Streamlit runtime. "
        "The report does not read or include credentials, headers, tokens, or secrets."
    )
    from mide.webull_runtime_inspection import (
        format_runtime_report,
        inspect_webull_runtime,
    )

    webull_runtime_report = inspect_webull_runtime()
    st.write(f"Distribution installed: **{webull_runtime_report['installed']}**")
    st.write(f"Installed version: **{webull_runtime_report['version'] or 'N/A'}**")
    with st.expander("Distribution files containing webull", expanded=False):
        st.code("\n".join(webull_runtime_report["webull_files"]) or "(none)")
    st.markdown("**Importable top-level modules supplied by the distribution**")
    st.dataframe(
        webull_runtime_report["top_level_modules"],
        use_container_width=True,
        hide_index=True,
    )
    inspection_text = format_runtime_report(webull_runtime_report)
    st.code(inspection_text, language="text")
    st.caption("Names matching requested SDK capability terms are marked [HIGHLIGHT].")
    st.download_button(
        "Download Runtime Inspection Report",
        data=inspection_text,
        file_name="webull-sdk-runtime-inspection.txt",
        mime="text/plain",
    )
    st.divider()
    active_sources = (
        view_scan.pipeline_sources if view_scan else []
    )
    st.subheader("Active Pipeline Data Sources")
    st.write(
        f"Completed scan provider: **{view_scan.provider if view_scan else 'No completed scan'}**"
    )
    st.caption(
        "Runtime provider and endpoint paths for the selected Live Webull scan; "
        "Alpaca usage is called out explicitly rather than hidden behind the selection label."
    )
    if active_sources:
        st.dataframe(active_sources, use_container_width=True, hide_index=True)
    else:
        st.caption("Run a Live Webull scan to populate provider and endpoint evidence.")

    st.subheader("Universe Definition")
    universe_report = (
        (scan_diagnostics.get("walter_architecture") or {}).get("universe_verification")
        if isinstance(scan_diagnostics, dict) else None
    ) or {}
    if universe_report:
        status_value = universe_report.get("status", "FAIL")
        (st.success if status_value == "PASS" else st.error)(
            f"Universe verification: {status_value}"
        )
        metadata = universe_report.get("scan_metadata", {})
        st.caption(
            f"Provider/source flow: {', '.join(metadata.get('provider_names', []))} · "
            f"Feed: {metadata.get('configured_data_feed', '—')} · "
            f"Session: {metadata.get('market_session', '—')}"
        )
        st.markdown("**Source counts**")
        st.dataframe(universe_report.get("sources", []), use_container_width=True,
                     hide_index=True)
        st.markdown("**Merge counts**")
        st.json(universe_report.get("merge_accounting", {}))
        st.markdown("**Snapshot availability (non-filtering)**")
        st.json(universe_report.get("pre_price_transitions", []))
        losses = universe_report.get("unexplained_losses", [])
        st.markdown(f"**Unexplained losses:** {len(losses)}")
        if losses:
            st.code("\n".join(losses))
        with st.expander("Symbol-level universe path", expanded=False):
            st.dataframe(universe_report.get("symbols", []), use_container_width=True,
                         hide_index=True)
        st.download_button(
            "Download source provenance",
            data=json.dumps({
                "symbols": universe_report.get("symbols", []),
                "malformed_identifiers": universe_report.get("malformed_identifiers", []),
            }, indent=2, default=str),
            file_name="universe-source-provenance.json",
            mime="application/json",
        )
    else:
        st.caption("Universe verification appears after a live scan.")

    st.subheader("Mission Candidate Outcomes")
    outcome_diagnostics = MissionOutcomeStore().diagnostics()
    outcome_columns = st.columns(4)
    for column, (label, value) in zip(
        outcome_columns,
        (
            ("Tracking", outcome_diagnostics["candidates_being_tracked"]),
            ("Completed", outcome_diagnostics["completed_outcomes"]),
            ("Unresolved", outcome_diagnostics["unresolved_outcomes"]),
            ("Missing data", outcome_diagnostics["missing_data_events"]),
        ),
    ):
        column.metric(label, value)
    st.caption("Measurement only; these records do not feed ranking or qualification.")
    render_calibration_dashboard(MissionOutcomeStore().analytics().dashboard())

    st.subheader("Candidate Ledger Decision Explanations")
    ledger_explanations = [
        {
            "Symbol": record.get("symbol"),
            "Rank": record.get("mission_rank"),
            "Outcome": record.get("terminal_outcome"),
            **(record.get("decision_explanation") or {}),
        }
        for record in st.session_state.walter_candidate_ledger.records.values()
    ]
    if ledger_explanations:
        st.dataframe(ledger_explanations, use_container_width=True, hide_index=True)
    else:
        st.caption("Decision explanations appear after Walter completes a scan.")

    runtime_evidence = importlib.import_module("mide.runtime_evidence")
    current_scan_export = runtime_evidence.current_scan_export
    json_bytes = runtime_evidence.json_bytes
    read_scans = runtime_evidence.read_scans
    runtime_file = runtime_evidence.runtime_file
    symbol_history = runtime_evidence.symbol_history
    symbol_summary = runtime_evidence.symbol_summary
    st.subheader("Rejected Candidates")
    st.caption(
        "Most recent 100 Stage 2+ rejections. Select the Stage, Rule, or Symbol "
        "column header to sort; this diagnostic view does not affect scanner decisions."
    )
    st.dataframe(
        rejected_candidates_table(rejected_records), width="stretch", hide_index=True
    )
    st.subheader("Free Float Cache")
    persistent_cache = cache_diagnostics_or_default(FreeFloatClient(""))
    cache_metrics = {
        "Cache Hits": scan_diagnostics.get("fmp_float_cache_hits", 0),
        "Cache Misses": scan_diagnostics.get("fmp_float_cache_misses", 0),
        "Cached Symbols": scan_diagnostics.get(
            "fmp_float_cached_symbols", persistent_cache.cached_symbols
        ),
        "FMP Requests Made": scan_diagnostics.get("fmp_requests_this_scan", 0),
        "FMP Requests Avoided": scan_diagnostics.get("fmp_requests_avoided", 0),
        "Oldest Cache Entry": scan_diagnostics.get(
            "fmp_float_cache_oldest_entry", persistent_cache.oldest_entry
        ) or "—",
        "Newest Cache Entry": scan_diagnostics.get(
            "fmp_float_cache_newest_entry", persistent_cache.newest_entry
        ) or "—",
    }
    st.caption(
        "Request counters describe the most recent scan; inventory describes "
        "today's persistent cache."
    )
    st.caption(
        "Cache Hits and FMP Requests Avoided both count per-symbol lookups served "
        "from a fresh cache entry, including cached failures."
    )
    metric_columns = st.columns(3)
    for index, (label, value) in enumerate(cache_metrics.items()):
        metric_columns[index % 3].metric(label, value)

    st.divider()
    st.subheader("Free Float Inspector")
    st.caption(
        "Temporary diagnostic: inspect the provider's raw float-related fields "
        "without affecting the scan or ranking logic."
    )
    with st.form("free_float_inspector"):
        float_ticker = st.text_input(
            "Ticker", placeholder="NCRA", key="free_float_inspector_ticker"
        ).strip().upper()
        inspect_float = st.form_submit_button("Inspect free float")
    if inspect_float:
        fmp_api_key = get_secret("FMP_API_KEY") or get_secret(
            "FINANCIAL_MODELING_PREP_API_KEY"
        )
        if not fmp_api_key:
            st.session_state.free_float_inspection = {
                "ticker": float_ticker,
                "provider": "Financial Modeling Prep",
                "request_succeeded": False,
                "returned_fields": {
                    "sharesOutstanding": None,
                    "floatShares": None,
                    "freeFloat": None,
                    "marketCap": None,
                },
                "computed_free_float": None,
                "computed_from": None,
                "source": None,
                "cache_status": "Cache was not checked because FMP_API_KEY is not configured.",
                "cache_bypassed": False,
                "error": "FMP_API_KEY is not configured.",
            }
        else:
            inspector_provider = FreeFloatClient(fmp_api_key, timeout=12)
            st.session_state.free_float_inspection = inspect_free_float(
                inspector_provider,
                float_ticker,
                YahooFinanceFloatProvider(timeout=12, max_workers=1),
            ).as_dict()

    float_result = st.session_state.free_float_inspection
    if float_result:
        st.markdown(f"**Ticker:** `{float_result['ticker'] or '—'}`")
        st.markdown(f"**Provider:** {float_result['provider']}")
        st.markdown(f"**Source:** {float_result.get('source') or 'Unavailable'}")
        if float_result.get("cache_status"):
            st.info(float_result["cache_status"])
        if float_result.get("cache_bypassed"):
            st.warning("This live FMP request intentionally bypassed the cache.")
        request_label = "SUCCESS" if float_result["request_succeeded"] else "FAILED"
        (st.success if float_result["request_succeeded"] else st.error)(
            f"API Request: {request_label}"
        )
        st.markdown("**Returned fields:**")
        for field, value in float_result["returned_fields"].items():
            st.code(f"{field} = {'?' if value is None else value}", language=None)
        computed = float_result["computed_free_float"]
        st.markdown("**Computed Free Float:**")
        st.code(f"{computed:,.0f}" if computed is not None else "Unavailable", language=None)
        if float_result.get("computed_from"):
            st.caption(f"Computed from {float_result['computed_from']}.")
        if float_result.get("error"):
            st.caption(float_result["error"])
        elif computed is None:
            st.info(
                "The request succeeded, but the provider did not return a recognized "
                "free-float field for this ticker."
            )

    st.divider()
    st.subheader("News Coverage")
    news_coverage = scan_diagnostics.get("news_coverage", {})
    if news_coverage:
        coverage_labels = {
            "active_provider": "Active provider",
            "last_successful_fetch": "Last successful fetch",
            "requests_made": "Requests made",
            "articles_received": "Articles received",
            "unique_symbols_discovered": "Unique symbols discovered",
            "provider_failures": "Provider failures",
            "articles_without_symbols": "Articles with no symbol tags",
            "symbols_seeded_from_news": "Symbols seeded from news",
        }
        coverage_rows = [
            {"Metric": label, "Value": news_coverage.get(key, "—")}
            for key, label in coverage_labels.items()
        ]
        for row in coverage_rows:
            row["Value"] = str(row["Value"])
        st.dataframe(
            coverage_rows,
            width="stretch",
            hide_index=True,
        )
        downstream = news_coverage.get("symbols_rejected_downstream") or []
        if downstream:
            st.caption("News-seeded symbols rejected downstream (exact reason)")
            st.dataframe(downstream, width="stretch", hide_index=True)
        with st.expander("Ticker news inspector", expanded=False):
            news_inspect_symbol = st.text_input(
                "Did Walter receive news for ticker?",
                value="CYCU",
                key="news_coverage_inspector_symbol",
            ).strip().upper()
            inspection = (scan_diagnostics.get("news_ticker_inspections") or {}).get(
                news_inspect_symbol
            )
            if inspection:
                st.json(inspection)
            else:
                st.info(
                    f"No provider-tagged article or pipeline trace was recorded for "
                    f"{news_inspect_symbol or 'that ticker'} in this scan."
                )
    else:
        st.info("No news-provider coverage diagnostics are available for this scan.")

    st.divider()
    st.subheader("Reuters / Benzinga — last 90 minutes")
    recent_wire_news = scan_diagnostics.get("recent_wire_news", [])
    if recent_wire_news:
        st.dataframe(recent_wire_news, width="stretch", hide_index=True)
    else:
        st.info("No Reuters or Benzinga symbols were published in the last 90 minutes.")

    with st.expander("Runtime Evidence", expanded=False):
        st.caption(
            "Read-only exports retain all scans recorded during the trading day/session; "
            "they do not alter scanner decisions."
        )
        runtime_recorder = get_flight_recorder()
        runtime_scans = read_scans(runtime_recorder.path)
        current_export = current_scan_export(
            runtime_scans[-1] if runtime_scans else None
        )
        st.download_button(
            "Download Current Scan JSON",
            data=json_bytes(current_export),
            file_name="walter_current_scan.json",
            mime="application/json",
            disabled=not runtime_scans,
        )

        history_symbol = (
            st.text_input(
                "Symbol",
                value=inspect_symbol,
                placeholder="DFNS",
                key="runtime_evidence_symbol",
            )
            .strip()
            .upper()
        )
        history = (
            symbol_history(runtime_scans, history_symbol) if history_symbol else []
        )
        summary = symbol_summary(history, history_symbol) if history_symbol else None
        if history_symbol:
            if summary:
                st.write(summary)
            else:
                st.info(f"No retained runtime records found for {history_symbol}.")
        st.download_button(
            "Export Symbol History",
            data=json_bytes(history),
            file_name=f"walter_{history_symbol.lower() or 'symbol'}_history.json",
            mime="application/json",
            disabled=not history,
        )

        for label, path, filename in (
            (
                "Download Flight Recorder JSONL",
                runtime_recorder.path,
                "flight_recorder.jsonl",
            ),
            (
                "Download Candidate History JSONL",
                get_store().path,
                "candidate_history.jsonl",
            ),
        ):
            contents, absent_message = runtime_file(path)
            if contents is None:
                st.info(absent_message)
            else:
                st.download_button(
                    label,
                    data=contents,
                    file_name=filename,
                    mime="application/x-ndjson",
                )

    st.subheader("Current trigger diagnostics")
    for record in display_records:
        diagnostic = record.get("trigger_diagnostics") or {}
        checks = diagnostic.get("checks") or []
        if not checks:
            continue
        with st.expander(
            f"{record.get('symbol', '')} — trigger {diagnostic.get('trigger', 'N/A')}",
            expanded=False,
        ):
            st.dataframe(
                [
                    {
                        "Condition": check.get("condition", ""),
                        "Result": "PASS" if check.get("passed") else "FAIL",
                        "Explanation": (
                            check.get("passed_reason")
                            if check.get("passed")
                            else check.get("failed_reason")
                            or "Covered by VWAP Distance"
                        ),
                    }
                    for check in checks
                ],
                width="stretch",
                hide_index=True,
            )
    st.subheader("Walter Flight Recorder")
    latest_flight_scan = get_flight_recorder().latest_scan()
    if not latest_flight_scan:
        st.info("Run a live scan to create the first flight-recorder trace.")
    else:
        st.caption(
            f"Most recent scan {latest_flight_scan.get('scan_id')} · "
            f"{latest_flight_scan.get('timestamp')}"
        )
        st.write("Per-scan funnel")
        funnel = latest_flight_scan.get("funnel", {})
        funnel_columns = st.columns(7)
        for column, label in zip(
            funnel_columns,
            [
                "Sampled",
                "Prefiltered",
                "Analyzed",
                "Participation PASS",
                "Structure PASS",
                "Qualified",
                "Displayed",
            ],
        ):
            column.metric(label, funnel.get(label, 0))
        rejected_expansion = [
            item for item in latest_flight_scan.get("expansion_candidate_ledger", [])
            if not item.get("passed")
        ][:50]
        st.write("First 50 rejected Participation → Expansion candidates")
        if rejected_expansion:
            st.dataframe(rejected_expansion, width="stretch", hide_index=True)
        else:
            st.info("No Expansion Assessment rejections were recorded in this scan.")
        diagnostic_symbol = (
            st.text_input(
                "Look up symbol across recorded scans",
                value=inspect_symbol,
                placeholder="EDBL",
            )
            .strip()
            .upper()
        )
        if diagnostic_symbol:
            bundle = symbol_export(
                diagnostic_symbol, get_store(), get_flight_recorder()
            )
            st.info(symbol_outcome(bundle))
            st.download_button(
                f"Download {diagnostic_symbol} symbol history",
                data=json.dumps(bundle, indent=2, default=str),
                file_name=f"{diagnostic_symbol}_symbol_history.json",
                mime="application/json",
            )
            chart_rows = symbol_chart_rows(bundle)
            if chart_rows:
                st.caption(
                    "Stage reached: 1 Discovery · 2 Snapshot · 3 Prefilter · "
                    "4 Scanner V2 · 5 Participation · 6 Structure · 7 Qualified · 8 Displayed"
                )
                st.line_chart(chart_rows, x="Scan")
            trace = bundle["flight_recorder"][-1] if bundle["flight_recorder"] else None
            if trace:
                st.success(
                    f"Latest appearance reached {trace.get('stage_reached', 'discovery')}."
                )
                evidence = trace.get("evidence") or {}
                if evidence.get("quality_score") is not None:
                    st.metric(
                        "Alert Quality Score",
                        f"{evidence.get('quality_grade')} · {evidence.get('quality_score')}/100",
                        help="Ranking only; scanner acceptance and rejection are unchanged.",
                    )
                if evidence.get("alignment_score") is not None:
                    st.metric(
                        "Alignment Score",
                        f"{evidence['alignment_score']}/3 · {evidence.get('alignment_label')}",
                        help="Ranking only; scanner acceptance and thresholds are unchanged.",
                    )
                    for timeframe in ("30s", "1m", "5m"):
                        aligned = (evidence.get("timeframe_alignment") or {}).get(
                            timeframe, {}
                        ).get("aligned", False)
                        st.write(f"{timeframe}  {'✓' if aligned else '✗'}")
                for decision in trace.get("events", []):
                    mark = "✅" if decision.get("passed") else "❌"
                    with st.expander(
                        f"{mark} {decision.get('stage')} — {decision.get('reason')}",
                        expanded=True,
                    ):
                        st.write(f"Timestamp: {decision.get('timestamp')}")
                        st.write("Measured values")
                        st.json(decision.get("measured_values", {}))
                        st.write("Thresholds")
                        st.json(decision.get("thresholds", {}))

if active_tab == "Session Replay":
    view_scan = completed_scan_for_view(st.session_state, "Session Replay")
    build_session_replay = importlib.import_module("mide.session_replay").build_session_replay
    st.subheader("Runtime Session Replay")
    st.caption(
        "A read-only reconstruction from Candidate History and Flight Recorder files. "
        "Replay never changes scanner behavior, qualification, or scoring."
    )
    if view_scan:
        st.caption(
            f"Current completed scan: {view_scan.provider or 'Demo'} · "
            f"{view_scan.completed_at.isoformat()}"
        )
    replay_symbol = (
        st.text_input(
            "Ticker to replay",
            value=inspect_symbol,
            placeholder="DFNS",
            key="replay_symbol",
        )
        .strip()
        .upper()
    )
    if replay_symbol:
        replay = build_session_replay(
            symbol_export(replay_symbol, get_store(), get_flight_recorder())
        )
        if replay["latest_outcome"]:
            outcome = replay["latest_outcome"]
            st.info(
                f"Recorded outcome: {outcome['outcome']} · P/L "
                f"{outcome.get('pl_pct') if outcome.get('pl_pct') is not None else 'N/A'}% · "
                f"MFE {outcome.get('mfe', 'N/A')} · MAE {outcome.get('mae', 'N/A')}"
            )
        if not replay["scans"]:
            st.info(f"No runtime history was retained for {replay_symbol}.")
        else:
            st.markdown("#### Lifecycle milestones")
            milestone_columns = st.columns(3)
            for index, (label, timestamp) in enumerate(replay["milestones"].items()):
                milestone_columns[index % 3].metric(label, timestamp or "Not reached")

            st.markdown("#### Replay events")
            st.caption(
                f"{replay['summary']['total_scans']} scans compressed into "
                f"{replay['summary']['summarized_events']} events."
            )
            for scan in replay["scans"]:
                time_range = scan["timestamp"]
                if scan["scan_count"] > 1:
                    time_range += (
                        f" → {scan['end_timestamp']} ({scan['scan_count']} scans)"
                    )
                with st.expander(
                    f"{time_range} · {scan['state']} · {scan['recommendation']}",
                    expanded=False,
                ):
                    left, middle, right = st.columns(3)
                    left.metric(
                        "Quality Score",
                        (
                            f"{scan.get('quality_grade')} · {scan.get('quality_score')}/100"
                            if scan.get("quality_score") is not None
                            else "N/A"
                        ),
                        help="Ranking only; this score never changes scanner qualification.",
                    )
                    left.metric(
                        "Participation Surge",
                        (
                            scan.get("participation_surge")
                            if scan.get("participation_surge") is not None
                            else "N/A"
                        ),
                    )
                    left.metric(
                        "Expansion Quality",
                        (
                            scan.get("expansion_quality")
                            if scan.get("expansion_quality") is not None
                            else "N/A"
                        ),
                    )
                    middle.metric(
                        "VWAP Distance",
                        (
                            scan.get("vwap_distance")
                            if scan.get("vwap_distance") is not None
                            else "N/A"
                        ),
                    )
                    middle.metric("SuperTrend", scan.get("supertrend_state") or "N/A")
                    middle.metric(
                        "Alignment Score",
                        (
                            f"{scan['alignment_score']}/3 · {scan.get('alignment_label')}"
                            if scan.get("alignment_score") is not None
                            else "N/A"
                        ),
                        help="Ranking only; replay does not re-evaluate qualification.",
                    )
                    for timeframe in ("30s", "1m", "5m"):
                        aligned = (scan.get("timeframe_alignment") or {}).get(
                            timeframe, {}
                        ).get("aligned", False)
                        middle.write(f"{timeframe}  {'✓' if aligned else '✗'}")
                    right.metric(
                        "VPI", scan.get("vpi") if scan.get("vpi") is not None else "N/A"
                    )
                    right.metric(
                        "Volume Acceleration",
                        (
                            scan.get("volume_acceleration")
                            if scan.get("volume_acceleration") is not None
                            else "N/A"
                        ),
                    )
                    right.metric(
                        "RS Score",
                        (
                            f"{float(scan['relative_strength_score']):+.1f}%"
                            if scan.get("relative_strength_score") is not None
                            else "N/A"
                        ),
                        help=f"Relative to {scan.get('relative_strength_benchmark') or 'market benchmark'}; ranking signal only.",
                    )
                    st.write(f"**Recommendation:** {scan['recommendation']}")
                    st.write("**Promotion blockers recorded for this event**")
                    if scan["promotion_blockers"]:
                        for blocker in scan["promotion_blockers"]:
                            evidence = ""
                            if "measured" in blocker or "threshold" in blocker:
                                evidence = (
                                    f" — measured: {blocker.get('measured', 'N/A')}; "
                                    f"required: {blocker.get('threshold', 'N/A')}"
                                )
                            st.markdown(
                                f"- **{blocker['category']}** — {blocker['reason']}{evidence}"
                            )
                    else:
                        st.success("No promotion blocker was retained for this event.")
                    st.write("**Trigger diagnostics**")
                    st.json(
                        scan.get("trigger_diagnostics")
                        or {
                            "result": scan.get("trigger_result"),
                            "details": "Not retained",
                        }
                    )

            st.markdown("#### Automatic summary")
            st.write(
                f"**Why Walter promoted this stock:** {replay['summary']['why_promoted']}"
            )
            st.write(
                f"**Why Walter did not recommend entry:** {replay['summary']['why_no_entry']}"
            )
            st.write(
                f"**Single most common blocker:** {replay['summary']['most_limiting_rule']} "
                f"({replay['summary']['most_limiting_rule_count']} scans)"
            )

if active_tab == "Trade Outcomes":
    view_scan = completed_scan_for_view(st.session_state, "Trade Outcomes")
    OUTCOME_LABELS = importlib.import_module("mide.trade_outcomes").OUTCOME_LABELS
    st.subheader("Trade Outcome Feedback")
    st.caption(
        "Feedback is descriptive only. Walter provides recommendations and never "
        "changes scanner thresholds automatically."
    )
    outcome_recorder = get_flight_recorder()
    outcome_store = get_trade_outcome_store(outcome_recorder)
    outcome_scan_time = (scan_diagnostics.get("flight_recorder") or {}).get("timestamp")
    for alert_record in actionable_records:
        outcome_store.register_alert(alert_record, timestamp=outcome_scan_time)
    available_alerts = outcome_store.all()
    if not available_alerts:
        st.info("No alerts have been recorded yet.")
    else:
        labels = {
            item["alert_id"]: f"{item['symbol']} · {item['alert_time']}"
            for item in available_alerts
        }
        selected_id = st.selectbox("Alert", list(labels), format_func=labels.get)
        selected = next(item for item in available_alerts if item["alert_id"] == selected_id)
        with st.form("trade_outcome_form"):
            outcome_label = st.selectbox(
                "Outcome", OUTCOME_LABELS,
                index=OUTCOME_LABELS.index(selected["outcome"])
                if selected.get("outcome") in OUTCOME_LABELS else 0,
            )
            left, right = st.columns(2)
            entry_price = left.number_input("Entry price", min_value=0.0, value=float(selected.get("entry_price") or 0), format="%.4f")
            exit_price = right.number_input("Exit price", min_value=0.0, value=float(selected.get("exit_price") or 0), format="%.4f")
            mfe = left.number_input("MFE (%)", value=float(selected.get("mfe") or 0), format="%.2f")
            mae = right.number_input("MAE (%)", value=float(selected.get("mae") or 0), format="%.2f")
            if st.form_submit_button("Save outcome"):
                saved = outcome_store.mark(selected_id, outcome=outcome_label, entry_price=entry_price, exit_price=exit_price, mfe=mfe, mae=mae)
                st.success(f"Saved {saved['outcome']} for {saved['symbol']} ({saved.get('pl_pct')}% P/L).")
        outcome_export = {
            "flight_recorder": outcome_recorder.scans(),
            "trade_outcomes": outcome_store.all(),
        }
        st.download_button("Export Flight Recorder with outcomes", data=json.dumps(outcome_export, indent=2), file_name="flight_recorder_with_outcomes.json", mime="application/json")
    st.markdown("#### Observed win rates")
    for dimension, groups in outcome_store.analytics().items():
        st.write(f"**{dimension.replace('_', ' ').title()}**")
        if groups:
            st.dataframe(groups, hide_index=True, width="stretch")
        else:
            st.caption("No completed Winner/Loser trades yet.")
    st.markdown("#### Recommendations")
    recommendations = outcome_store.recommendations()
    if recommendations:
        for recommendation in recommendations:
            st.info(recommendation)
    else:
        st.caption("At least five completed trades in a cohort are needed for a recommendation.")

if active_tab == "What changed":
    view_scan = completed_scan_for_view(st.session_state, "What changed")
    changed_records = view_scan.records if view_scan else []
    for record in sorted(
        changed_records, key=lambda r: abs(r.get("velocity", 0)), reverse=True
    )[:15]:
        direction = "strengthened" if record.get("velocity", 0) > 0 else "weakened"
        st.markdown(
            f"**{record['symbol']}** {direction}: "
            f"{record.get('previous_score', record.get('current_momentum', record['opportunity_score'])):.1f} → "
            f"{record.get('current_momentum', record['opportunity_score']):.1f} ({record.get('velocity', 0):+.1f})"
        )

if active_tab == "Data validation":
    view_scan = completed_scan_for_view(st.session_state, "Data validation")
    validation_records = view_scan.records if view_scan else []
    validation_warnings = view_scan.warnings if view_scan else []
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Completed provider", view_scan.provider if view_scan else "No completed scan"
    )
    c2.metric("Ranked records", len(validation_records))
    c3.metric(
        "Nonzero dominance",
        sum(r.get("market_dominance_score", 0) > 0 for r in validation_records),
    )
    c4.metric("API warnings", len(validation_warnings))
    for warning in validation_warnings:
        st.warning(warning)

if active_tab == "Method":
    st.markdown("""
Scanner V1 is preserved as the classic technical screener. Scanner V2 is an adaptive momentum assistant: Walter rewards fresh catalysts, flat bases beginning to expand, increasing feed and dollar volume, RVOL, float turnover, acceleration and improvements versus the previous scan. VWAP, EMA65 and SuperTrend improve ranking and state progression, but they no longer eliminate promising discovery-stage candidates.

**Indicator verification before formula changes**

- **SuperTrend parameters currently used:** period `10`, multiplier `3.0`, based on `(high + low) / 2` bands and an exponentially smoothed ATR using `alpha = 1 / period`. Walter applies these parameters to the current session's one-minute bars and to resampled 1m/3m/5m/10m confirmation frames.
- **VWAP calculation currently used:** current-session cumulative typical price VWAP, where typical price is `(high + low + close) / 3`, multiplied by each bar's volume and divided by cumulative volume.
- **Likely Webull differences:** Webull may source consolidated real-time data, extended-hours/session templates, proprietary tick aggregation, rounding, and configurable indicator presets that can differ from Walter's Alpaca feed and fixed `10, 3.0` SuperTrend settings.
- **Data limitations:** Walter currently receives Alpaca bars at the configured feed and computes the primary SuperTrend catalyst from the available scan bars; exact Webull matching is limited without Webull's raw bar feed, session settings, extended-hours handling, and confirmed default SuperTrend preset.
""")
