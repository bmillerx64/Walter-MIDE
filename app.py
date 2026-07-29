from __future__ import annotations

from datetime import datetime, timezone, timedelta
import html
import importlib
import json
import logging
import platform
import sys
import streamlit as st


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

from mide.config import Settings
from mide.alpaca import AlpacaClient, AlpacaError, credential_status
from mide.news import index_news, recent_wire_news_log
from mide.discovery import (
    analyze_candidates,
    build_seed_symbols,
    prefilter_snapshots,
    snapshot_identity_records,
)
from mide.scanner_v2 import (
    apply_scanner_v2,
    participation_gate_rejection_diagnostics,
    strengthening_diagnostics,
)
from mide.memory import MemoryStore
from mide.flight_recorder import FlightRecorder
from mide.runtime_evidence import (
    current_scan_export,
    json_bytes,
    read_scans,
    runtime_file,
    symbol_history,
    symbol_summary,
)
from mide.session_replay import build_session_replay
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
    rejected_candidate_records,
    rejected_candidates_table,
    trader_priority_sort_key,
    render_walter_mission_control,
    render_early_setups,
    render_live_opportunity_feed,
    render_escalation_engine,
    mission_control_header_markup,
    decision_funnel_markup,
    market_session_quality_markup,
    walter_mission_control,
)
from mide.live_opportunity_feed import update_opportunity_feed
from mide.early_setup import newly_entered_symbols
from mide.time_service import format_eastern_time, market_clock, market_phase_at
from mide.watchdog import ScanAlreadyRunning
from mide.decision_engine import (
    evaluate as evaluate_decision_funnel,
    IdentityPolicy,
    stage2_filter,
)
from mide.free_float_inspector import inspect_free_float
from mide.free_float import FreeFloatClient, enrich_snapshots_with_free_float
from mide.version import BUILD

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


def log(message: str) -> None:
    stamp = datetime.now().astimezone().strftime("%H:%M:%S")
    print(f"[WALTER {stamp}] {message}", flush=True)


@st.cache_resource
def get_store() -> MemoryStore:
    return MemoryStore()


@st.cache_resource
def get_flight_recorder() -> FlightRecorder:
    # Resolve the class at call time so a Streamlit hot reload never keeps the
    # pre-deployment FlightRecorder class captured by this app module.
    repair_mide_module_links()
    recorder_class = importlib.import_module("mide.flight_recorder").FlightRecorder
    return recorder_class()


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

mission_header_slot = st.empty()
market_session_slot = st.empty()
early_setup_slot = st.empty()
mission_plan_slot = st.empty()
opportunity_feed_slot = st.empty()
escalation_engine_slot = st.empty()
system_status_panel = st.expander("System Status", expanded=False)
scan_runtime_slot = system_status_panel.container()

session_defaults = {
    "records": [],
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
    ALERT_VOICE_SESSION_KEY: SYSTEM_DEFAULT_VOICE_ID,
    DAVID_AVAILABLE_SESSION_KEY: False,
    ACTIVE_VOICE_SESSION_KEY: SYSTEM_DEFAULT_VOICE_ID,
    VOICE_WARNING_SESSION_KEY: "",
    VOICE_CONFIRMATION_SESSION_KEY: "",
}
for key, default in session_defaults.items():
    if key not in st.session_state:
        st.session_state[key] = default
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
    scanner_version = "Decision Funnel 3.0"
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
    scanner_version: str = "Decision Funnel 3.0",
    *,
    status,
    client_factory=None,
    credential_checker=None,
):
    api_key = get_secret("ALPACA_API_KEY")
    secret = get_secret("ALPACA_SECRET_KEY")
    if not api_key or not secret:
        raise AlpacaError("Alpaca credentials are not configured in Streamlit Secrets.")

    # Resolve deployment-sensitive classes/functions for every attempt. A retry
    # therefore gets a fresh client and cannot retain a class detached during a
    # Streamlit/GitHub hot reload.
    repair_mide_module_links()
    alpaca_module = importlib.import_module("mide.alpaca")
    client_factory = client_factory or alpaca_module.AlpacaClient
    credential_checker = credential_checker or alpaca_module.credential_status
    client = client_factory(api_key, secret, feed=settings.feed, timeout=12)
    try:
        environment = credential_checker(client)
        status.write(f"Alpaca credentials accepted ({environment} environment)")
        log(f"Credentials accepted by Alpaca {environment} environment")
    except Exception as exc:
        raise AlpacaError(str(exc)) from exc
    with scan_runtime_slot:
        progress = st.progress(0, text="Starting")

    log("Stage 1/5: fetching news")
    status.write("1/5 Fetching recent news")
    try:
        news_items = client.news(
            datetime.now(timezone.utc) - timedelta(days=3), limit=200
        )
    except Exception as exc:
        client.warnings.append(f"News unavailable; scan continued: {exc}")
        news_items = []
    progress.progress(0.12, text="News loaded")

    log("Stage 2/5: building discovery universe")
    status.write("2/5 Building discovery universe")
    seeds, reasons = build_seed_symbols(client, settings, news_items)
    progress.progress(0.24, text=f"{len(seeds)} symbols discovered")

    for key, value in client.diagnostics.items():
        log(f"Discovery diagnostic: {key}={value}")
    for warning in client.warnings:
        log(f"Warning: {warning}")

    log(f"Stage 3/5: fetching snapshots for {len(seeds)} symbols")
    status.write(f"3/5 Fetching snapshots for {len(seeds)} symbols")
    snapshots = {}
    total = max(1, len(seeds))
    for i in range(0, len(seeds), settings.batch_size):
        batch = seeds[i : i + settings.batch_size]
        try:
            snapshots.update(client.snapshots(batch))
        except Exception as exc:
            client.warnings.append(f"Snapshot batch skipped: {exc}")
        done = min(i + len(batch), len(seeds))
        progress.progress(
            0.24 + 0.36 * (done / total), text=f"Snapshots {done}/{len(seeds)}"
        )

    # Alpaca's snapshot schema is limited to trades, quotes, and OHLCV bars; it
    # does not include free-float fundamentals.  Enrich only the snapshots that
    # need float data with the configured reference-data provider before Stage 2.
    fmp_api_key = get_secret("FMP_API_KEY") or get_secret(
        "FINANCIAL_MODELING_PREP_API_KEY"
    )
    if fmp_api_key:
        float_count, float_errors = enrich_snapshots_with_free_float(
            snapshots, FreeFloatClient(fmp_api_key, timeout=12)
        )
        client.diagnostics["free_float_provider"] = "Financial Modeling Prep"
        client.diagnostics["free_float_enriched"] = float_count
        client.diagnostics["free_float_provider_failures"] = len(float_errors)
        if float_errors:
            sample = ", ".join(sorted(float_errors)[:5])
            client.warnings.append(
                f"FMP free-float unavailable for {len(float_errors)} symbols"
                f" (sample: {sample})"
            )
    else:
        client.diagnostics["free_float_provider"] = "not configured"
        client.warnings.append(
            "FMP_API_KEY is not configured; Stage 2 free-float lookups cannot be enriched"
        )

    policy = IdentityPolicy(settings.min_price, settings.max_price,
                            settings.max_free_float, settings.include_etfs)
    # Alpaca snapshots intentionally contain real-time market fields, not
    # fundamental share statistics.  Ask the fallback only for symbols which
    # have already passed the price range so the provider is not needlessly
    # queried for the whole discovery universe.
    price_qualified = [
        record["symbol"] for record in snapshot_identity_records(snapshots)
        if policy.min_price <= record["price"] <= policy.max_price
    ]
    if hasattr(client, "enrich_free_float"):
        try:
            client.enrich_free_float(snapshots, price_qualified)
        except Exception as exc:
            client.warnings.append(f"Free-float fallback unavailable; scan continued: {exc}")
    eligible_identities, stage2_rejections, funnel_counts = stage2_filter(
        snapshot_identity_records(snapshots), policy
    )
    eligible_symbols = {record["symbol"] for record in eligible_identities}
    eligible_snapshots = {
        symbol: snapshot for symbol, snapshot in snapshots.items()
        if symbol in eligible_symbols
    }
    log("Stage 4/5: applying Stage 2 and prefiltering")
    status.write("4/5 Applying tradability, price, and free-float gates")
    candidates = [
        candidate
        for candidate in prefilter_snapshots(eligible_snapshots, settings)
        if candidate.get("symbol") in eligible_symbols
    ]
    progress.progress(0.68, text=f"{len(candidates)} Stage 2-qualified candidates")

    # A candidate can reach analysis only through the authoritative gate above.
    stage3_candidates = candidates
    funnel_counts["stage_3_analysis"] = len(stage3_candidates)
    client.diagnostics["stage_2_rejections"] = stage2_rejections
    client.diagnostics["funnel_counts"] = funnel_counts
    log(
        "Decision funnel: "
        + " -> ".join(f"{name}={count}" for name, count in funnel_counts.items())
    )

    log("Stage 5/5: analyzing bars and scoring")
    status.write(
        f"5/5 Analyzing {len(stage3_candidates)} free-float-qualified symbols"
    )
    records = analyze_candidates(client, stage3_candidates, index_news(news_items), reasons)
    analyzed_records = records
    store = get_store()
    previous = store.latest_by_symbol()
    records = store.enrich_velocity(records, previous=previous)
    records = evaluate_decision_funnel(records, policy)
    funnel_counts["stage_3_analysis"] = len(records)
    funnel_counts["monitored"] = sum(
        record.get("final_decision") == "Attention Earned" for record in records
    )
    funnel_counts["entry_ready"] = sum(
        record.get("candidate_status") == "Entry Ready" for record in records
    )
    client.diagnostics["decision_funnel"] = {
        "universe": len(records),
        "eligible": sum(record["eligible"] for record in records),
        "rejected": sum(record["final_decision"] == "Rejected" for record in records),
    }
    wire_news_log = recent_wire_news_log(
        news_items,
        snapshots=snapshots,
        analyzed=analyzed_records,
        records=records,
        settings=settings,
    )
    for item in wire_news_log:
        log("Recent wire news: " + json.dumps(item, separators=(",", ":")))
    client.diagnostics["recent_wire_news"] = wire_news_log

    # Commit the completed scan to the UI before best-effort persistence.  A
    # recorder or history write must never leave the previous scan displayed.
    st.session_state.records = records
    st.session_state.symbols_sampled = len(seeds)
    st.session_state.prefilter_count = len(candidates)
    st.session_state.source_label = (
        f"Live {settings.feed.upper()} · {len(seeds)} symbols sampled · "
        f"{len(candidates)} prefiltered"
    )
    st.session_state.api_warnings = list(client.warnings)
    st.session_state.scan_diagnostics = dict(client.diagnostics)
    st.session_state.last_updated = datetime.now().astimezone()

    flight_scan = record_scan_safely(
        get_flight_recorder(),
        seeds=seeds,
        discovery_reasons=reasons,
        snapshots=snapshots,
        candidates=candidates,
        analyzed=analyzed_records,
        records=records,
        settings=settings,
        scanner_v2=False,
        recent_news_log=wire_news_log,
    )
    if flight_scan is not None:
        client.diagnostics["flight_recorder"] = {
            "scan_id": flight_scan["scan_id"],
            "timestamp": flight_scan["timestamp"],
            "funnel": flight_scan["funnel"],
        }
    else:
        client.diagnostics["flight_recorder_error"] = "write failed; scan continued"
    try:
        store.append(records)
    except Exception as exc:
        logging.getLogger(__name__).exception("Scan history write failed")
        log(
            "Scan history write failed; dashboard updated: "
            f"{type(exc).__name__}: {exc}"
        )
    # Preserve the immediately previous evidence only for the display layer. This
    # is attached after persistence so it cannot affect Scanner V2 or compound in
    # candidate history across refreshes.
    for record in records:
        record["opportunity_pulse_previous"] = previous.get(record["symbol"], {})
    progress.progress(1.0, text="Scan complete")
    status.update(
        label=f"Scan complete: {len(records)} ranked records",
        state="complete",
        expanded=False,
    )
    log(f"Complete: {len(records)} ranked records")
    return (
        records,
        len(seeds),
        len(candidates),
        list(client.warnings),
        dict(client.diagnostics),
    )


def run_live(
    scanner_version: str = "Decision Funnel 3.0",
    *,
    client_factory=None,
    credential_checker=None,
):
    """Run and report the complete live pipeline without leaving a LIVE spinner.

    This boundary deliberately covers status creation as well as every discovery,
    market-data, analysis, and persistence stage.  Callers still receive the
    original exception so the watchdog can retry it, while both the traceback and
    terminal UI state are recorded for each failed attempt.
    """
    status = None
    try:
        with scan_runtime_slot:
            status = st.status("Walter is scanning…", expanded=True)
        return _run_live_pipeline(
            scanner_version,
            status=status,
            client_factory=client_factory,
            credential_checker=credential_checker,
        )
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
        raise


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
updated_text = format_eastern_time(updated)
clock = market_clock()

if records:
    with st.expander("Decision Funnel audit trails", expanded=False):
        for record in records:
            st.markdown(decision_funnel_markup(record), unsafe_allow_html=True)

actionable_records = actionable_candidate_records(records)
rejected_records = rejected_candidate_records(records)
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

tabs = st.tabs(
    [
        "Radar",
        "Diagnostics",
        "Session Replay",
        "What changed",
        "Data validation",
        "Method",
    ]
)
with tabs[0]:
    if not display_records:
        st.success("No stock currently deserves elevated attention.")
    else:
        for section_name, section_records, expanded in scanner_v2_display_sections(
            display_records
        ):
            if not section_records:
                continue
            with st.expander(
                f"{section_name.upper()} ({len(section_records)})", expanded=expanded
            ):
                sorted_records = sorted(
                    section_records, key=trader_priority_sort_key, reverse=True
                )
                for record in sorted_records[:10]:
                    opportunity_card(record)
                st.dataframe(
                    radar_table(sorted_records), width="stretch", hide_index=True
                )
        if rejected_records:
            with st.expander(
                f"REJECTED CANDIDATES ({len(rejected_records)})", expanded=False
            ):
                st.dataframe(
                    rejected_candidates_table(rejected_records),
                    width="stretch",
                    hide_index=True,
                )

with tabs[1]:
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
        api_key = get_secret("ALPACA_API_KEY")
        secret_key = get_secret("ALPACA_SECRET_KEY")
        if not api_key or not secret_key:
            st.session_state.free_float_inspection = {
                "ticker": float_ticker,
                "provider": "Alpaca Market Data",
                "request_succeeded": False,
                "returned_fields": {
                    "sharesOutstanding": None,
                    "floatShares": None,
                    "freeFloat": None,
                    "marketCap": None,
                },
                "computed_free_float": None,
                "computed_from": None,
                "error": "Alpaca credentials are not configured.",
            }
        else:
            inspector_client = AlpacaClient(
                api_key, secret_key, feed=settings.feed, timeout=12
            )
            st.session_state.free_float_inspection = inspect_free_float(
                inspector_client, float_ticker
            ).as_dict()

    float_result = st.session_state.free_float_inspection
    if float_result:
        st.markdown(f"**Ticker:** `{float_result['ticker'] or '—'}`")
        st.markdown(f"**Provider:** {float_result['provider']}")
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

with tabs[2]:
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

with tabs[3]:
    for record in sorted(
        records, key=lambda r: abs(r.get("velocity", 0)), reverse=True
    )[:15]:
        direction = "strengthened" if record.get("velocity", 0) > 0 else "weakened"
        st.markdown(
            f"**{record['symbol']}** {direction}: "
            f"{record.get('previous_score', record.get('current_momentum', record['opportunity_score'])):.1f} → "
            f"{record.get('current_momentum', record['opportunity_score']):.1f} ({record.get('velocity', 0):+.1f})"
        )

with tabs[4]:
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

with tabs[5]:
    st.markdown("""
Scanner V1 is preserved as the classic technical screener. Scanner V2 is an adaptive momentum assistant: Walter rewards fresh catalysts, flat bases beginning to expand, increasing feed and dollar volume, RVOL, float turnover, acceleration and improvements versus the previous scan. VWAP, EMA65 and SuperTrend improve ranking and state progression, but they no longer eliminate promising discovery-stage candidates.

**Indicator verification before formula changes**

- **SuperTrend parameters currently used:** period `10`, multiplier `3.0`, based on `(high + low) / 2` bands and an exponentially smoothed ATR using `alpha = 1 / period`. Walter applies these parameters to the current session's one-minute bars and to resampled 1m/3m/5m/10m confirmation frames.
- **VWAP calculation currently used:** current-session cumulative typical price VWAP, where typical price is `(high + low + close) / 3`, multiplied by each bar's volume and divided by cumulative volume.
- **Likely Webull differences:** Webull may source consolidated real-time data, extended-hours/session templates, proprietary tick aggregation, rounding, and configurable indicator presets that can differ from Walter's Alpaca feed and fixed `10, 3.0` SuperTrend settings.
- **Data limitations:** Walter currently receives Alpaca bars at the configured feed and computes the primary SuperTrend catalyst from the available scan bars; exact Webull matching is limited without Webull's raw bar feed, session settings, extended-hours handling, and confirmed default SuperTrend preset.
""")
