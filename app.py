from __future__ import annotations

from datetime import datetime, timezone, timedelta
import platform
import streamlit as st

from mide.config import Settings
from mide.alpaca import AlpacaClient, AlpacaError, credential_status
from mide.news import index_news
from mide.discovery import build_seed_symbols, prefilter_snapshots, analyze_candidates
from mide.scanner_v2 import (
    apply_scanner_v2,
    participation_gate_rejection_diagnostics,
    strengthening_diagnostics,
)
from mide.memory import MemoryStore
from mide.flight_recorder import FlightRecorder
from mide.demo import demo_records
from mide.ui import (
    inject_css,
    metric_strip,
    radar_table,
    opportunity_card,
    play_alert,
    scanner_v2_display_sections,
    scanner_v2_dashboard_counts,
    actionable_candidate_records,
    rejected_candidate_records,
    rejected_candidates_table,
    automatic_watching_sort_key,
    trader_priority_sort_key,
)
from mide.time_service import format_eastern_time, market_clock, market_phase_at

VERSION = "1.0.2"

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


st.set_page_config(page_title="Walter MIDE Radar", page_icon="📡", layout="wide")
inject_css()


def log(message: str) -> None:
    stamp = datetime.now().astimezone().strftime("%H:%M:%S")
    print(f"[WALTER {stamp}] {message}", flush=True)


@st.cache_resource
def get_store() -> MemoryStore:
    return MemoryStore()


@st.cache_resource
def get_flight_recorder() -> FlightRecorder:
    return FlightRecorder()


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

st.title("📡 Walter · MIDE Radar")
st.caption(f"Market Intelligence Decision Engine · $0.02–$5.00 · v{VERSION}")
st.success(
    "Walter is online. Live mode scans automatically every 60 seconds and still supports manual scans."
)

session_defaults = {
    "records": [],
    "source_label": "No scan has been run",
    "api_warnings": [],
    "last_updated": None,
    "scan_diagnostics": {},
    "scan_in_progress": False,
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
    scanner_version = st.radio(
        "Scanner",
        ["Scanner V2 (adaptive momentum)", "Scanner V1 (classic screener)"],
        index=0,
    )
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


def arm_auto_scan_timer(enabled: bool, refresh_seconds: int) -> None:
    """Install one browser timer that survives Streamlit reruns by rearming itself."""
    if not enabled:
        st.components.v1.html(
            """<script>
            if (window.parent.__walterAutoScanTimer) {
              window.parent.clearTimeout(window.parent.__walterAutoScanTimer);
              window.parent.__walterAutoScanTimer = null;
            }
            </script>""",
            height=0,
        )
        return

    delay_ms = max(1, int(refresh_seconds)) * 1000
    st.components.v1.html(
        f"""<script>
        if (window.parent.__walterAutoScanTimer) {{
          window.parent.clearTimeout(window.parent.__walterAutoScanTimer);
        }}
        window.parent.__walterAutoScanTimer = window.parent.setTimeout(() => {{
          window.parent.__walterAutoScanTimer = null;
          window.parent.location.reload();
        }}, {delay_ms});
        </script>""",
        height=0,
    )


def run_live(scanner_version: str = "Scanner V2 (adaptive momentum)"):
    api_key = get_secret("ALPACA_API_KEY")
    secret = get_secret("ALPACA_SECRET_KEY")
    if not api_key or not secret:
        raise AlpacaError("Alpaca credentials are not configured in Streamlit Secrets.")

    client = AlpacaClient(api_key, secret, feed=settings.feed, timeout=12)
    status = st.status("Walter is scanning…", expanded=True)
    try:
        environment = credential_status(client)
        status.write(f"Alpaca credentials accepted ({environment} environment)")
        log(f"Credentials accepted by Alpaca {environment} environment")
    except Exception as exc:
        raise AlpacaError(str(exc)) from exc
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

    log("Stage 4/5: prefiltering")
    status.write("4/5 Filtering the strongest candidates")
    candidates = prefilter_snapshots(snapshots, settings)
    progress.progress(0.68, text=f"{len(candidates)} candidates prefiltered")

    log("Stage 5/5: analyzing bars and scoring")
    status.write("5/5 Analyzing VWAP, SuperTrend, EMA, volume and catalysts")
    records = analyze_candidates(client, candidates, index_news(news_items), reasons)
    analyzed_records = records
    store = get_store()
    previous = store.latest_by_symbol()
    records = store.enrich_velocity(records, previous=previous)
    if scanner_version.startswith("Scanner V2"):
        records = apply_scanner_v2(records, previous)
        participation_rejections = participation_gate_rejection_diagnostics(records)
        client.diagnostics["participation_gate_rejections"] = participation_rejections
        for detail in participation_rejections["details"]:
            log(
                "Participation gate rejected "
                f"{detail['symbol']}: "
                f"{'; '.join(detail['failed_reasons'])}"
            )
        client.diagnostics["strengthening"] = strengthening_diagnostics(records)
    else:
        for record in records:
            record["scanner_version"] = "V1"
            record.setdefault("candidate_status", record.get("status", "PASS"))
    flight_scan = get_flight_recorder().record_scan(
        seeds=seeds,
        discovery_reasons=reasons,
        snapshots=snapshots,
        candidates=candidates,
        analyzed=analyzed_records,
        records=records,
        settings=settings,
        scanner_v2=scanner_version.startswith("Scanner V2"),
    )
    client.diagnostics["flight_recorder"] = {
        "scan_id": flight_scan["scan_id"],
        "timestamp": flight_scan["timestamp"],
        "funnel": flight_scan["funnel"],
    }
    store.append(records)
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


should_scan = False

if use_demo or mode == "Demo":
    st.session_state.records = demo_records()
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
    try:
        st.session_state.scan_in_progress = True
        records, universe_count, prefiltered, warnings, diagnostics = run_live(
            scanner_version
        )
        st.session_state.records = records
        st.session_state.source_label = f"Live {settings.feed.upper()} · {universe_count} symbols sampled · {prefiltered} prefiltered"
        st.session_state.api_warnings = warnings
        st.session_state.scan_diagnostics = diagnostics
        st.session_state.last_updated = datetime.now().astimezone()
    except Exception as exc:
        log(f"Scan failed: {type(exc).__name__}: {exc}")
        st.error(f"Live scan could not complete: {exc}")
        st.info(
            "Walter remains online. Correct the issue and press Run live scan again."
        )
    finally:
        st.session_state.scan_in_progress = False

records = st.session_state.records
api_warnings = st.session_state.api_warnings
scan_diagnostics = st.session_state.scan_diagnostics
updated = st.session_state.last_updated
updated_text = format_eastern_time(updated)
st.caption(f"{st.session_state.source_label} · Last Scan {updated_text}")

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
    arm_auto_scan_timer(
        mode == "Live Alpaca" and auto_refresh and live_possible,
        settings.refresh_seconds,
    )
    # Continue rendering the Diagnostics tab: a zero-result scan can still
    # contain the most useful flight-recorder failure paths.

clock = market_clock()
st.info(
    f"{clock.banner_text}. Rankings describe evidence; they are not trade instructions."
)

actionable_records = actionable_candidate_records(records)
rejected_records = rejected_candidate_records(records)
display_records = (
    actionable_records
    if show_pass
    else [r for r in actionable_records if r.get("status") not in {"PASS", "Removed"}]
)

arm_auto_scan_timer(
    mode == "Live Alpaca" and auto_refresh and live_possible, settings.refresh_seconds
)

with st.expander("Legacy candidate diagnostics", expanded=False):
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

metric_strip(actionable_records)
alert_phrase = scan_alert_phrase(actionable_records)
if alerts and alert_phrase:
    play_alert("assets/alert.wav", alert_phrase, alert_voice_for_session())

tabs = st.tabs(["Radar", "Diagnostics", "What changed", "Data validation", "Method"])
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
                        "Explanation": check.get("passed_reason")
                        if check.get("passed")
                        else check.get("failed_reason") or "Covered by VWAP Distance",
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
                "Look up symbol in most recent scan",
                value=inspect_symbol,
                placeholder="EDBL",
            )
            .strip()
            .upper()
        )
        if diagnostic_symbol:
            trace = get_flight_recorder().latest_for_symbol(diagnostic_symbol)
            if not trace:
                st.warning(
                    f"{diagnostic_symbol} was not discovered in the most recent scan."
                )
            else:
                st.success(
                    f"{diagnostic_symbol} reached {trace.get('stage_reached', 'discovery')}."
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
    for record in sorted(
        records, key=lambda r: abs(r.get("velocity", 0)), reverse=True
    )[:15]:
        direction = "strengthened" if record.get("velocity", 0) > 0 else "weakened"
        st.markdown(
            f"**{record['symbol']}** {direction}: "
            f"{record.get('previous_score', record.get('current_momentum', record['opportunity_score'])):.1f} → "
            f"{record.get('current_momentum', record['opportunity_score']):.1f} ({record.get('velocity', 0):+.1f})"
        )

with tabs[3]:
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

with tabs[4]:
    st.markdown("""
Scanner V1 is preserved as the classic technical screener. Scanner V2 is an adaptive momentum assistant: Walter rewards fresh catalysts, flat bases beginning to expand, increasing feed and dollar volume, RVOL, float turnover, acceleration and improvements versus the previous scan. VWAP, EMA65 and SuperTrend improve ranking and state progression, but they no longer eliminate promising discovery-stage candidates.

**Indicator verification before formula changes**

- **SuperTrend parameters currently used:** period `10`, multiplier `3.0`, based on `(high + low) / 2` bands and an exponentially smoothed ATR using `alpha = 1 / period`. Walter applies these parameters to the current session's one-minute bars and to resampled 1m/3m/5m/10m confirmation frames.
- **VWAP calculation currently used:** current-session cumulative typical price VWAP, where typical price is `(high + low + close) / 3`, multiplied by each bar's volume and divided by cumulative volume.
- **Likely Webull differences:** Webull may source consolidated real-time data, extended-hours/session templates, proprietary tick aggregation, rounding, and configurable indicator presets that can differ from Walter's Alpaca feed and fixed `10, 3.0` SuperTrend settings.
- **Data limitations:** Walter currently receives Alpaca bars at the configured feed and computes the primary SuperTrend catalyst from the available scan bars; exact Webull matching is limited without Webull's raw bar feed, session settings, extended-hours handling, and confirmed default SuperTrend preset.
""")


if mode == "Live Alpaca" and auto_refresh:
    st.components.v1.html(
        f"<script>setTimeout(() => window.parent.location.reload(), {settings.refresh_seconds * 1000});</script>",
        height=0,
    )
