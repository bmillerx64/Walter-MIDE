from __future__ import annotations

from datetime import datetime, timezone, timedelta
import streamlit as st

from mide.config import Settings
from mide.alpaca import AlpacaClient, AlpacaError, credential_status
from mide.news import index_news
from mide.discovery import build_seed_symbols, prefilter_snapshots, analyze_candidates
from mide.scanner_v2 import apply_scanner_v2
from mide.memory import MemoryStore
from mide.demo import demo_records
from mide.ui import inject_css, metric_strip, radar_table, opportunity_card, play_alert, state_sections, scanner_v2_dashboard_counts
from mide.time_service import format_eastern_time, market_clock, market_phase_at

VERSION = "1.0.2"

VOICE_OPTIONS = ["System default", "Microsoft David", "Google US English", "Samantha"]
DEFAULT_VOICE = VOICE_OPTIONS[0]
ALERT_VOICE_SESSION_KEY = "alert_voice_name"
ALERT_VOICE_QUERY_KEY = "alert_voice"


def normalize_alert_voice(voice_name: str) -> str:
    """Return the speech-synthesis voice name used by both manual and automatic scans."""
    return "" if voice_name == DEFAULT_VOICE else voice_name


def selected_alert_voice(session_state=None) -> str:
    """Read the current voice choice from session state for every alert path."""
    state = st.session_state if session_state is None else session_state
    return state.get(ALERT_VOICE_SESSION_KEY, DEFAULT_VOICE)


def persisted_alert_voice(query_params=None, session_state=None) -> str:
    """Resolve voice choice from URL-persisted state, then session state, then default."""
    state = st.session_state if session_state is None else session_state
    params = st.query_params if query_params is None else query_params
    raw = params.get(ALERT_VOICE_QUERY_KEY, "") if params is not None else ""
    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    if raw in VOICE_OPTIONS:
        state[ALERT_VOICE_SESSION_KEY] = raw
        return raw
    return state.get(ALERT_VOICE_SESSION_KEY, DEFAULT_VOICE)


def alert_voice_for_session(session_state=None) -> str:
    """Resolve the persisted voice choice into the value passed to play_alert."""
    return normalize_alert_voice(selected_alert_voice(session_state))


def market_phase(now: datetime | None = None) -> str:
    """Return the U.S. equity market phase from the shared Eastern clock."""
    return market_phase_at(now)


def scan_alert_phrase(records: list[dict]) -> str:
    """Build the per-scan audible alert, prioritizing actionable Entry Ready symbols."""
    entry_symbols = [
        r.get("symbol") for r in records
        if r.get("candidate_status") == "Entry Ready" or r.get("status") == "Entry Ready"
    ]
    entry_symbols = [str(s).upper() for s in entry_symbols if s]
    if entry_symbols:
        if len(entry_symbols) == 1:
            symbol_text = entry_symbols[0]
        else:
            symbol_text = f"{', '.join(entry_symbols[:-1])} and {entry_symbols[-1]}"
        return f"Entry Ready: {symbol_text}."

    dashboard_counts = scanner_v2_dashboard_counts(records)
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
st.success("Walter is online. Live mode scans automatically every 60 seconds and still supports manual scans.")

session_defaults = {
    "records": [],
    "source_label": "No scan has been run",
    "api_warnings": [],
    "last_updated": None,
    "scan_diagnostics": {},
    "scan_in_progress": False,
    ALERT_VOICE_SESSION_KEY: DEFAULT_VOICE,
}
for key, default in session_defaults.items():
    if key not in st.session_state:
        st.session_state[key] = default
persisted_alert_voice()

with st.sidebar:
    st.header("Control")
    live_possible = bool(get_secret("ALPACA_API_KEY")) and bool(get_secret("ALPACA_SECRET_KEY"))
    mode = st.radio("Data mode", ["Live Alpaca", "Demo"], index=0 if live_possible else 1)
    scanner_version = st.radio("Scanner", ["Scanner V2 (adaptive momentum)", "Scanner V1 (classic screener)"], index=0)
    auto_refresh = st.toggle("Auto live scan every 60 seconds", value=True, disabled=(mode != "Live Alpaca"))
    alerts = st.toggle("Audible watch/advance alerts", value=True)
    selected_voice = st.selectbox("Alert voice", VOICE_OPTIONS, key=ALERT_VOICE_SESSION_KEY)
    st.query_params[ALERT_VOICE_QUERY_KEY] = selected_voice
    st.components.v1.html(
        f"""<script>
        window.localStorage.setItem('walter_alert_voice', {selected_voice!r});
        const params = new URLSearchParams(window.parent.location.search);
        if (!params.get('{ALERT_VOICE_QUERY_KEY}')) {{
          const stored = window.localStorage.getItem('walter_alert_voice');
          if (stored) {{
            params.set('{ALERT_VOICE_QUERY_KEY}', stored);
            window.parent.history.replaceState(null, '', `${{window.parent.location.pathname}}?${{params}}`);
          }}
        }}
        </script>""",
        height=0,
    )
    show_pass = st.toggle("Show removed/pass candidates", value=False)
    inspect_symbol = st.text_input("Why did/didn't a symbol appear?", placeholder="BIYA").strip().upper()
    run_scan = st.button("Run live scan", type="primary", use_container_width=True, disabled=(mode != "Live Alpaca"))
    use_demo = st.button("Load demo data", use_container_width=True)
    st.divider()
    if settings.feed == "sip":
        st.success("SIP feed selected")
    else:
        st.warning("IEX feed selected. Set ALPACA_FEED='sip' for consolidated data.")


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
        news_items = client.news(datetime.now(timezone.utc) - timedelta(days=3), limit=200)
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
        batch = seeds[i:i + settings.batch_size]
        try:
            snapshots.update(client.snapshots(batch))
        except Exception as exc:
            client.warnings.append(f"Snapshot batch skipped: {exc}")
        done = min(i + len(batch), len(seeds))
        progress.progress(0.24 + 0.36 * (done / total), text=f"Snapshots {done}/{len(seeds)}")

    log("Stage 4/5: prefiltering")
    status.write("4/5 Filtering the strongest candidates")
    candidates = prefilter_snapshots(snapshots, settings)
    progress.progress(0.68, text=f"{len(candidates)} candidates prefiltered")

    log("Stage 5/5: analyzing bars and scoring")
    status.write("5/5 Analyzing VWAP, SuperTrend, EMA, volume and catalysts")
    records = analyze_candidates(client, candidates, index_news(news_items), reasons)
    store = get_store()
    previous = store.latest_by_symbol()
    records = store.enrich_velocity(records, previous=previous)
    if scanner_version.startswith("Scanner V2"):
        records = apply_scanner_v2(records, previous)
    else:
        for record in records:
            record["scanner_version"] = "V1"
            record.setdefault("candidate_status", record.get("status", "PASS"))
    store.append(records)
    progress.progress(1.0, text="Scan complete")
    status.update(label=f"Scan complete: {len(records)} ranked records", state="complete", expanded=False)
    log(f"Complete: {len(records)} ranked records")
    return records, len(seeds), len(candidates), list(client.warnings), dict(client.diagnostics)


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
            or (datetime.now().astimezone() - st.session_state.last_updated).total_seconds() >= settings.refresh_seconds
        )
    )
    should_scan = run_scan or due

if mode == "Live Alpaca" and should_scan:
    try:
        st.session_state.scan_in_progress = True
        records, universe_count, prefiltered, warnings, diagnostics = run_live(scanner_version)
        st.session_state.records = records
        st.session_state.source_label = (
            f"Live {settings.feed.upper()} · {universe_count} symbols sampled · {prefiltered} prefiltered"
        )
        st.session_state.api_warnings = warnings
        st.session_state.scan_diagnostics = diagnostics
        st.session_state.last_updated = datetime.now().astimezone()
    except Exception as exc:
        log(f"Scan failed: {type(exc).__name__}: {exc}")
        st.error(f"Live scan could not complete: {exc}")
        st.info("Walter remains online. Correct the issue and press Run live scan again.")
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
        st.info("Dashboard loaded successfully. Walter will scan automatically in live mode, or press **Run live scan** to begin now.")
    if mode == "Live Alpaca" and auto_refresh:
        st.components.v1.html(
            f"<script>setTimeout(() => window.parent.location.reload(), {settings.refresh_seconds * 1000});</script>",
            height=0,
        )
    st.stop()

clock = market_clock()
st.info(f"{clock.banner_text}. Rankings describe evidence; they are not trade instructions.")

display_records = records if show_pass else [r for r in records if r.get("status") not in {"PASS", "Removed"}]

if inspect_symbol:
    with st.expander(f"Why / why not: {inspect_symbol}", expanded=True):
        match = next((r for r in records if r.get("symbol") == inspect_symbol), None)
        if match:
            st.success(f"{inspect_symbol} was analyzed and ranked {match.get('status', 'UNKNOWN')}.")
            st.write("; ".join(match.get("reasons", [])) or "No elevated evidence recorded.")
            st.write("Cautions: " + ("; ".join(match.get("cautions", [])) or "None recorded."))
        else:
            st.warning(f"{inspect_symbol} is not in the current ranked set.")

metric_strip(records)
alert_phrase = scan_alert_phrase(records)
if alerts and alert_phrase:
    play_alert("assets/alert.wav", alert_phrase, alert_voice_for_session())

tabs = st.tabs(["Radar", "What changed", "Data validation", "Method"])
with tabs[0]:
    if not display_records:
        st.success("No stock currently deserves elevated attention.")
    else:
        for section_name, section_records in state_sections(display_records).items():
            if not section_records:
                continue
            st.subheader(section_name.upper())
            sort_choice = st.selectbox(
                f"Sort {section_name}",
                ["State priority", "Symbol", "% change", "Dollar volume", "RVOL"],
                key=f"sort_{section_name.lower().replace(' ', '_')}",
            )
            sorted_records = sorted(
                section_records,
                key=lambda r: (
                    str(r.get("symbol", "")) if sort_choice == "Symbol" else
                    float(r.get("pct_change", 0) or 0) if sort_choice == "% change" else
                    float(r.get("dollar_volume", 0) or 0) if sort_choice == "Dollar volume" else
                    float(r.get("rvol_proxy", 0) or 0) if sort_choice == "RVOL" else
                    float(r.get("scanner_v2_score", r.get("opportunity_score", 0)) or 0)
                ),
                reverse=(sort_choice != "Symbol"),
            )
            for record in sorted_records[:10]:
                opportunity_card(record)
            st.dataframe(radar_table(sorted_records), width="stretch", hide_index=True)

with tabs[1]:
    for record in sorted(records, key=lambda r: abs(r.get("velocity", 0)), reverse=True)[:15]:
        direction = "strengthened" if record.get("velocity", 0) > 0 else "weakened"
        st.markdown(
            f"**{record['symbol']}** {direction}: "
            f"{record.get('previous_score', record['opportunity_score']):.1f} → "
            f"{record['opportunity_score']:.1f} ({record.get('velocity', 0):+.1f})"
        )

with tabs[2]:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Configured feed", settings.feed.upper())
    c2.metric("Ranked records", len(records))
    c3.metric("Nonzero dominance", sum(r.get("market_dominance_score", 0) > 0 for r in records))
    c4.metric("API warnings", len(api_warnings))
    for warning in api_warnings:
        st.warning(warning)

with tabs[3]:
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
