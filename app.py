from __future__ import annotations

from mide.startup_memory import checkpoint as memory_checkpoint

memory_checkpoint("app.py bootstrap")

from datetime import datetime, timezone, timedelta
import html
import importlib
import inspect
import json
import logging
import platform
import sys
memory_checkpoint("app.py standard-library imports")

import streamlit as st
memory_checkpoint("streamlit import", object_name="streamlit module graph")


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
from mide.alpaca import AlpacaClient, AlpacaError, credential_status
memory_checkpoint("providers import", object_name="mide.alpaca")
from mide.news import index_news, recent_wire_news_log
from mide.news_provider import (
    AlpacaNewsProvider,
    NewsService,
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


def record_scan_safely(recorder, *, recent_news_log=None, **scan_data):
    """Write an optional flight trace without affecting the live dashboard."""
    try:
        try:
            return recorder.record_scan(
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
            return recorder.record_scan(**scan_data)
    except Exception as exc:
        logging.getLogger(__name__).exception("Flight Recorder write failed")
        log(
            "Flight Recorder write failed; dashboard updated: "
            f"{type(exc).__name__}: {exc}"
        )
        return None


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


settings = Settings.from_mapping(secrets_mapping())
memory_checkpoint("settings initialization", object_name="Settings")

mission_header_slot = st.empty()
market_session_slot = st.empty()
early_setup_slot = st.empty()
mission_plan_slot = st.empty()
opportunity_feed_slot = st.empty()
escalation_engine_slot = st.empty()
system_status_panel = st.expander("System Status", expanded=False)
scan_runtime_slot = system_status_panel.container()
memory_checkpoint("dashboard container initialization", object_name="Streamlit DeltaGenerators")

session_defaults = {
    "records": [],
    "walter_candidate_ledger": WalterCandidateLedger(),
    "source_label": "No scan has been run",
    "api_warnings": [],
    "last_updated": None,
    "scan_diagnostics": {},
    "free_float_inspection": None,
    "scan_in_progress": False,
    "last_scan_attempt": None,
    "scan_failure_count": 0,
    "symbols_sampled": 0,
    "prefilter_count": 0,
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
memory_checkpoint("session cache initialization", object_name="st.session_state")
memory_profile("startup", session_state=st.session_state)
persisted_alert_voice()

with st.sidebar:
    st.header("Control")
    live_possible = bool(get_secret("ALPACA_API_KEY")) and bool(
        get_secret("ALPACA_SECRET_KEY")
    )
    mode = st.radio(
        "Data mode", ["Live Alpaca", "Demo"], index=0 if live_possible else 1
    )
    st.caption(f"Decision Funnel v{BUILD.version} · {BUILD.git_sha}")
    scanner_version = "Walter Architecture v1.0"
    auto_refresh = st.toggle(
        "Auto live scan every 60 seconds", value=True, disabled=(mode != "Live Alpaca")
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
    st.download_button(
        "Download Flight Recorder",
        data=get_flight_recorder().export_bytes(),
        file_name="flight_recorder.jsonl",
        mime="application/x-ndjson",
        use_container_width=True,
    )
    run_scan = st.button(
        "Run live scan",
        type="primary",
        use_container_width=True,
        disabled=(mode != "Live Alpaca"),
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
):
    """Execute the live scan through the single Walter Architecture pipeline."""
    api_key = get_secret("ALPACA_API_KEY")
    secret = get_secret("ALPACA_SECRET_KEY")
    if not api_key or not secret:
        raise AlpacaError("Alpaca credentials are not configured in Streamlit Secrets.")

    repair_mide_module_links()
    alpaca_module = importlib.import_module("mide.alpaca")
    client_factory = client_factory or alpaca_module.AlpacaClient
    credential_checker = credential_checker or alpaca_module.credential_status
    client = client_factory(api_key, secret, feed=settings.feed, timeout=12)
    # Account validation is useful evidence, not permission for one provider to
    # terminate the scan. Public/fallback discovery may still produce a universe.
    try:
        environment = credential_checker(client)
        status.write(f"Alpaca credentials accepted ({environment} environment)")
    except Exception as exc:
        record_provider_failure(
            client.diagnostics, provider="Alpaca", operation="credential check",
            exception=exc, recovery_action="continue with available public discovery sources",
        )
        client.warnings.append(f"Alpaca credential check unavailable: {exc}")
    with scan_runtime_slot:
        progress = st.progress(0, text="Starting Walter Architecture")

    state = {"seeds": [], "reasons": {}, "snapshots": {}, "news": [],
             "candidates": [], "analyzed": [], "ranked": []}
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

    def discover():
        # Catalyst retrieval deliberately does not happen here. Discovery sources
        # alone establish the immutable membership of this scan.
        try:
            discovery_parameters = inspect.signature(build_seed_symbols).parameters
            if "universe_verification" in discovery_parameters:
                seeds, reasons = build_seed_symbols(
                    client, settings, [], universe_verification=universe_verification
                )
            else:  # Test/deployment compatibility for an injected legacy callable.
                seeds, reasons = build_seed_symbols(client, settings, [])
        except Exception as exc:
            record_provider_failure(
                client.diagnostics, provider="Alpaca", operation="universe discovery",
                exception=exc, recovery_action="complete scan with an empty universe",
            )
            client.warnings.append(f"Universe discovery unavailable: {exc}")
            seeds, reasons = [], {}
        state["seeds"], state["reasons"] = seeds, reasons
        snapshots = {}
        for offset in range(0, len(seeds), settings.batch_size):
            batch = seeds[offset:offset + settings.batch_size]
            try:
                snapshots.update(client.snapshots(batch))
            except Exception as exc:
                client.warnings.append(f"Snapshot batch unavailable: {exc}")
                record_provider_failure(
                    client.diagnostics, provider="Alpaca", operation="market data snapshots",
                    exception=exc, affected_symbols=batch,
                    recovery_action="retain symbols as Technical Failure candidates and continue",
                )
        state["snapshots"] = snapshots
        observed_valid = {
            row["symbol"] for row in universe_verification._observations
            if is_valid_us_symbol(row["symbol"])
        }
        not_selected = sorted(observed_valid - set(seeds))
        snapshot_failures = sorted(set(seeds) - set(snapshots))
        transitions = [{
            "transition_function_name": "broad-market eligibility and rotating slice",
            "input_count": len(observed_valid), "output_count": len(seeds),
            "removed_count": len(not_selected),
            "exact_reason_categories": ["outside configured rotating broad-market slice"],
            "affected_symbols_grouped_by_reason": {
                "outside configured rotating broad-market slice": not_selected
            },
        }, {
            "transition_function_name": "snapshot batch retrieval before Price Gate",
            "input_count": len(seeds), "output_count": len(seeds) - len(snapshot_failures),
            "removed_count": len(snapshot_failures),
            "exact_reason_categories": ["market data snapshot unavailable"],
            "affected_symbols_grouped_by_reason": {
                "market data snapshot unavailable": snapshot_failures
            },
        }]
        universe_verification.finish(
            seeds, transitions=transitions,
            entered_price_gate=set(seeds) - set(snapshot_failures),
        )
        records = snapshot_identity_records(snapshots)
        by_symbol = {item["symbol"]: item for item in records}
        # Symbols whose snapshot failed remain accountable as unusable data.
        return [by_symbol.get(symbol, {
            "symbol": symbol, "price": None, "data_usable": False,
            "technical_failure": "Market data snapshot unavailable",
        }) for symbol in seeds]

    def catalyst(records):
        service = NewsService([AlpacaNewsProvider(client)])
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
            value = next((update.get(key) for key in (
                "free_float", "float_shares", "shares_float"
            ) if update.get(key) is not None), None)
            try:
                passed = float(value) <= policy.max_free_float
            except (TypeError, ValueError):
                passed = False
            reason = (
                "Free float within configured limit" if passed else
                "Usable free-float value unavailable" if value is None else
                "Free float exceeds configured limit"
            )
            decisions[symbol] = Decision(passed, "Free Float", reason, update)
        return decisions

    def participation(records):
        symbols = {item["symbol"] for item in records}
        eligible_snapshots = {
            symbol: snap for symbol, snap in state["snapshots"].items()
            if symbol in symbols
        }
        candidates = prefilter_snapshots(eligible_snapshots, settings)
        candidate_by_symbol = {item["symbol"]: item for item in candidates}
        analyzed = analyze_candidates(
            client, candidates, index_news(state["news"]), state["reasons"]
        )
        analyzed = history.enrich_velocity(analyzed, previous=previous)
        analyzed_by_symbol = {item["symbol"]: item for item in analyzed}
        state["candidates"], state["analyzed"] = candidates, analyzed
        result = {}
        for item in records:
            symbol = item["symbol"]
            if symbol not in candidate_by_symbol:
                result[symbol] = Decision(False, "Participation", "Market participation prefilter not satisfied")
            elif symbol not in analyzed_by_symbol:
                result[symbol] = Decision(False, "Participation", "Insufficient intraday data for assessment")
            else:
                analyzed_record = analyzed_by_symbol[symbol]
                result[symbol] = Decision(True, "Participation", "Participation evidence measured", analyzed_record)
        return result

    def expansion(records):
        result = {}
        for item in records:
            advanced, audit, confluence = behavioral_decision(item)
            result[item["symbol"]] = Decision(
                advanced, "Expansion", f"Confluence {confluence}",
                {"decision_funnel": audit, "confluence_score": confluence,
                 "eligible": True,
                 "final_decision": "Attention Earned" if advanced else "Rejected",
                 "candidate_status": item.get("candidate_status", "Entry Ready") if advanced else "Removed",
                 "scanner_version": "Walter Architecture v1.0"},
            )
        return result

    class RuntimeStore:
        def persist(self, results):
            # The complete ledger, including rejected candidates, is durable before
            # Mission Publication makes qualified records visible.
            history.append(results)

    def rank(records):
        return sorted(records, key=trader_priority_sort_key)

    def publish(records):
        state["ranked"] = records
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
    )
    ledger = architecture.run()
    ranked = state["ranked"]
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
    st.session_state.symbols_sampled = len(state["seeds"])
    st.session_state.prefilter_count = len(state["candidates"])
    st.session_state.source_label = (
        f"Live {settings.feed.upper()} · {len(state['seeds'])} symbols sampled · "
        f"{len(ranked)} Walter-qualified"
    )
    st.session_state.api_warnings = list(client.warnings)
    st.session_state.scan_diagnostics = dict(client.diagnostics)
    st.session_state.last_updated = datetime.now().astimezone()
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
            )
        )
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
        return [], 0, 0, [f"Recovered live scan failure: {exc}"], diagnostics


should_scan = False

if use_demo or mode == "Demo":
    st.session_state.records = evaluate_decision_funnel(demo_records())
    st.session_state.symbols_sampled = len(st.session_state.records)
    st.session_state.prefilter_count = len(st.session_state.records)
    st.session_state.source_label = "Demonstration data"
    st.session_state.api_warnings = []
    st.session_state.last_updated = datetime.now().astimezone()
else:
    due = (
        mode == "Live Alpaca"
        and auto_refresh
        and live_possible
        and not st.session_state.scan_in_progress
        and (
            st.session_state.last_updated is None
            or (
                datetime.now().astimezone() - st.session_state.last_updated
            ).total_seconds()
            >= settings.refresh_seconds
        )
    )
    should_scan = run_scan or due

if mode == "Live Alpaca" and should_scan:
    st.session_state.last_scan_attempt = datetime.now().astimezone()
    try:
        st.session_state.scan_in_progress = True
        # Resolve the watchdog dynamically: a deployment may have replaced the
        # module while this Streamlit session still holds older app globals.
        repair_mide_module_links()
        watchdog = importlib.import_module("mide.watchdog").PROCESS_SCAN_WATCHDOG
        records, universe_count, prefiltered, warnings, diagnostics = watchdog.run(
            lambda: run_live(scanner_version), before_retry=repair_mide_module_links
        )
        st.session_state.records = records
        st.session_state.symbols_sampled = universe_count
        st.session_state.prefilter_count = prefiltered
        st.session_state.source_label = f"Live {settings.feed.upper()} · {universe_count} symbols sampled · {prefiltered} prefiltered"
        st.session_state.api_warnings = warnings
        st.session_state.scan_diagnostics = diagnostics
        st.session_state.last_updated = datetime.now().astimezone()
        st.session_state.scan_failure_count = 0
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
    finally:
        st.session_state.scan_in_progress = False

records = st.session_state.records
api_warnings = st.session_state.api_warnings
scan_diagnostics = st.session_state.scan_diagnostics
updated = st.session_state.last_updated
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
rejected_records = st.session_state.get("rejected_candidate_history", [])
display_records = (
    actionable_records
    if show_pass
    else [r for r in actionable_records if r.get("status") not in {"PASS", "Removed"}]
)

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
    if mode == "Live Alpaca" and auto_refresh
    else "Disabled"
)
with mission_header_slot:
    st.markdown(
        mission_control_header_markup(
            live=mode == "Live Alpaca",
            market_phase=clock.phase,
            market_time=clock.time_text,
            symbols_sampled=st.session_state.symbols_sampled,
            prefilter_count=st.session_state.prefilter_count,
            candidate_count=len(actionable_records),
            focus_count=focus_count,
            escalation_count=escalation_count,
            auto_scan=auto_scan,
            funnel_counts=scan_diagnostics.get("funnel_counts", {}),
        ),
        unsafe_allow_html=True,
    )
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
    mode == "Live Alpaca" and auto_refresh and live_possible,
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
    status_columns[0].metric("Symbols Sampled", st.session_state.symbols_sampled)
    status_columns[1].metric("Prefiltered", st.session_state.prefilter_count)
    status_columns[2].metric("Ranked", len(records))
    st.caption(st.session_state.source_label)
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
    st.subheader("Universe Construction Verification")
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
        st.markdown("**Pre-Price Gate removals**")
        st.json(universe_report.get("pre_price_transitions", []))
        losses = universe_report.get("unexplained_losses", [])
        st.markdown(f"**Unexplained losses:** {len(losses)}")
        if losses:
            st.code("\n".join(losses))
        with st.expander("Symbol-level universe path", expanded=False):
            st.dataframe(universe_report.get("symbols", []), use_container_width=True,
                         hide_index=True)
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
        st.dataframe(
            [
                {"Metric": label, "Value": news_coverage.get(key, "—")}
                for key, label in coverage_labels.items()
            ],
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
    build_session_replay = importlib.import_module("mide.session_replay").build_session_replay
    st.subheader("Runtime Session Replay")
    st.caption(
        "A read-only reconstruction from Candidate History and Flight Recorder files. "
        "Replay never changes scanner behavior, qualification, or scoring."
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
    for record in sorted(
        records, key=lambda r: abs(r.get("velocity", 0)), reverse=True
    )[:15]:
        direction = "strengthened" if record.get("velocity", 0) > 0 else "weakened"
        st.markdown(
            f"**{record['symbol']}** {direction}: "
            f"{record.get('previous_score', record.get('current_momentum', record['opportunity_score'])):.1f} → "
            f"{record.get('current_momentum', record['opportunity_score']):.1f} ({record.get('velocity', 0):+.1f})"
        )

if active_tab == "Data validation":
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Configured feed", settings.feed.upper())
    c2.metric("Ranked records", len(records))
    c3.metric(
        "Nonzero dominance",
        sum(r.get("market_dominance_score", 0) > 0 for r in records),
    )
    c4.metric("API warnings", len(api_warnings))
    for warning in api_warnings:
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
