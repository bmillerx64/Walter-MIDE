from __future__ import annotations

from datetime import datetime, timedelta, timezone
import streamlit as st

from mide.config import Settings
from mide.alpaca import AlpacaClient, AlpacaError, credential_status
from mide.news import index_news
from mide.discovery import build_seed_symbols, prefilter_snapshots, analyze_candidates
from mide.scanner_v2 import apply_scanner_v2
from mide.memory import MemoryStore
from mide.demo import demo_records
from mide.ui import inject_css, metric_strip, radar_table, opportunity_card, play_alert

VERSION = "1.0.2"

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

with st.sidebar:
    st.header("Control")
    live_possible = bool(get_secret("ALPACA_API_KEY")) and bool(get_secret("ALPACA_SECRET_KEY"))
    mode = st.radio("Data mode", ["Live Alpaca", "Demo"], index=0 if live_possible else 1)
    scanner_version = st.radio("Scanner", ["Scanner V2 (adaptive momentum)", "Scanner V1 (classic screener)"], index=0)
    auto_refresh = st.toggle("Auto live scan every 60 seconds", value=True, disabled=(mode != "Live Alpaca"))
    alerts = st.toggle("Audible watch/advance alerts", value=True)
    voice_name = st.selectbox("Alert voice", ["System default", "Microsoft David", "Google US English", "Samantha"], index=0)
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

if "records" not in st.session_state:
    st.session_state.records = []
    st.session_state.source_label = "No scan has been run"
    st.session_state.api_warnings = []
    st.session_state.last_updated = None
    st.session_state.scan_diagnostics = {}
    st.session_state.scan_in_progress = False

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
updated_text = updated.strftime("%I:%M:%S %p %Z") if updated else "not yet"
st.caption(f"{st.session_state.source_label} · Updated {updated_text}")

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

local_now = datetime.now().astimezone()
hm = local_now.hour * 60 + local_now.minute
if hm < 8 * 60 + 30:
    phase = "Premarket discovery"
elif hm < 10 * 60 + 30:
    phase = "Opening momentum"
elif hm < 14 * 60:
    phase = "Midday validation"
elif hm < 16 * 60:
    phase = "Late-session momentum"
else:
    phase = "After-hours observation"
st.info(f"Market phase: **{phase}**. Rankings describe evidence; they are not trade instructions.")

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
new_alerts = [
    r for r in records
    if (r.get("alert_event") or (r.get("status") in ("EXCEPTIONAL", "ALERT", "WATCH NOW")
    and (r.get("status_changed") or r.get("velocity", 0) >= 10)))
]
if alerts and new_alerts:
    top = new_alerts[0]
    phrase = f"Walter alert. {top['symbol']}. {top['status']}. " + ". ".join(top.get("reasons", [])[:3])
    play_alert("assets/alert.wav", phrase, voice_name if voice_name != "System default" else "")

tabs = st.tabs(["Radar", "What changed", "Data validation", "Method"])
with tabs[0]:
    if not display_records:
        st.success("No stock currently deserves elevated attention.")
    else:
        for record in display_records[:10]:
            opportunity_card(record)
        st.dataframe(radar_table(display_records), width="stretch", hide_index=True)

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
""")


if mode == "Live Alpaca" and auto_refresh:
    st.components.v1.html(
        f"<script>setTimeout(() => window.parent.location.reload(), {settings.refresh_seconds * 1000});</script>",
        height=0,
    )
