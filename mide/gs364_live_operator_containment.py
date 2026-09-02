"""GS364: contain live-session memory pressure and operator-alert noise.

This layer is operational/presentation only.  It does not change discovery
membership, scanner scoring, qualification, readiness thresholds, execution, or
orders.  Live evidence from 2026-09-02 showed three independent operator/runtime
problems that share the same full-app rerun path:

* ``MemoryStore.latest_by_symbol`` read/split the entire growing JSONL file on
  every scan even though callers only need the latest record per symbol.
* Sidebar backup buttons eagerly materialized the entire Candidate History and
  Flight Recorder as raw bytes on every app rerun.  Large backups are now gzip
  streamed and cached by file identity so Streamlit receives a bounded payload.
* Day-gainer provenance alone could promote a flat/weak symbol to LOOK NOW, and
  GS363's second audio component could make the intended chime cadence ambiguous.

The latest-record cache preserves the existing ``limit_lines`` contract exactly:
only symbols whose latest occurrence falls inside the requested trailing line
window are returned.  The first call streams the file once with bounded memory;
subsequent append-only growth is parsed from the prior byte offset.
"""
from __future__ import annotations

from copy import deepcopy
import gzip
import io
import json
from pathlib import Path
import shutil
import threading
from typing import Any


LARGE_EXPORT_BYTES = 4 * 1024 * 1024
_HISTORY_LOCK = threading.Lock()
_HISTORY_CACHE: dict[str, dict[str, Any]] = {}
_EXPORT_LOCK = threading.Lock()
_EXPORT_CACHE: dict[tuple[str, int, int], bytes] = {}


def _path_identity(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return int(getattr(stat, "st_dev", 0)), int(getattr(stat, "st_ino", 0))


def _parse_history_line(raw_line: bytes) -> dict | None:
    try:
        item = json.loads(raw_line.decode("utf-8", errors="ignore"))
    except (ValueError, TypeError, UnicodeError):
        return None
    return item if isinstance(item, dict) else None


def bounded_latest_by_symbol(store, limit_lines: int = 5000) -> dict[str, dict]:
    """Return the legacy trailing-window latest map without whole-file materialization."""
    path = Path(store.path)
    if not path.exists():
        return {}

    limit = max(1, int(limit_lines))
    stat = path.stat()
    key = str(path.resolve())
    identity = _path_identity(path)

    with _HISTORY_LOCK:
        cached = _HISTORY_CACHE.get(key)

    can_extend = bool(
        cached
        and cached.get("identity") == identity
        and int(cached.get("offset", 0)) <= stat.st_size
        and (
            stat.st_size > int(cached.get("offset", 0))
            or stat.st_mtime_ns == int(cached.get("mtime_ns", -1))
        )
    )

    if can_extend:
        latest = dict(cached["latest"])
        line_count = int(cached["line_count"])
        offset = int(cached["offset"])
        if stat.st_size > offset:
            with path.open("rb") as handle:
                handle.seek(offset)
                for raw_line in handle:
                    line_count += 1
                    item = _parse_history_line(raw_line)
                    if not item:
                        continue
                    symbol = str(item.get("symbol") or "").strip().upper()
                    if symbol:
                        latest[symbol] = (line_count, item)
    else:
        latest: dict[str, tuple[int, dict]] = {}
        line_count = 0
        with path.open("rb") as handle:
            for raw_line in handle:
                line_count += 1
                item = _parse_history_line(raw_line)
                if not item:
                    continue
                symbol = str(item.get("symbol") or "").strip().upper()
                if symbol:
                    latest[symbol] = (line_count, item)

    final_stat = path.stat()
    snapshot = {
        "identity": _path_identity(path),
        "offset": final_stat.st_size,
        "mtime_ns": final_stat.st_mtime_ns,
        "line_count": line_count,
        "latest": latest,
    }
    with _HISTORY_LOCK:
        _HISTORY_CACHE[key] = snapshot

    cutoff = max(0, line_count - limit)
    return {
        symbol: item
        for symbol, (line_number, item) in latest.items()
        if line_number > cutoff
    }


def bounded_history_for_symbol(store, symbol: str) -> list[dict]:
    """Stream one-symbol history instead of splitting the complete JSONL in memory."""
    wanted = str(symbol or "").strip().upper()
    path = Path(store.path)
    if not wanted or not path.exists():
        return []
    matches: list[dict] = []
    with path.open("rb") as handle:
        for raw_line in handle:
            item = _parse_history_line(raw_line)
            if item and str(item.get("symbol") or "").upper() == wanted:
                matches.append(item)
    return matches


def _gzip_export(path: Path) -> bytes:
    """Stream-compress one large JSONL file and cache only the compressed payload."""
    if not path.exists():
        return b""
    stat = path.stat()
    if stat.st_size < LARGE_EXPORT_BYTES:
        return path.read_bytes()

    key = (str(path.resolve()), int(stat.st_size), int(stat.st_mtime_ns))
    with _EXPORT_LOCK:
        cached = _EXPORT_CACHE.get(key)
    if cached is not None:
        return cached

    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode="wb", compresslevel=5, mtime=0) as archive:
        with path.open("rb") as source:
            shutil.copyfileobj(source, archive, length=1024 * 1024)
    payload = output.getvalue()

    with _EXPORT_LOCK:
        # Retain only the newest compressed version of this path.
        for old_key in tuple(_EXPORT_CACHE):
            if old_key[0] == key[0] and old_key != key:
                _EXPORT_CACHE.pop(old_key, None)
        _EXPORT_CACHE[key] = payload
    return payload


def _is_gzip_payload(value: object) -> bool:
    return isinstance(value, (bytes, bytearray)) and bytes(value[:2]) == b"\x1f\x8b"


def _number(record: dict, *keys: str) -> float | None:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def calibrated_opportunity_state(record: dict) -> dict:
    """Protect LOOK NOW from weak top-mover-only noise while preserving fresh events.

    Fresh news/re-ignition/volume-regime events keep the established early LOOK NOW
    behavior.  A plain Webull top-mover observation must additionally show price
    near/above VWAP, bullish SuperTrend, and at least one current flow confirmation.
    This preserves the live VIOT pattern (near VWAP + bullish ST + participation /
    dollar-flow confirmation) while keeping DGNX/GSUN-style flat top movers in
    DEVELOPING until their current evidence improves.
    """
    from . import gs310_unified_opportunity_state as unified

    original = getattr(unified.opportunity_state, "_gs364_original", unified.opportunity_state)
    view = original(record)
    if view.get("state") != unified.LOOK_NOW:
        return view

    provenance = set(view.get("attention_provenance") or [])
    if provenance.intersection({"FRESH_NEWS_SEED", "FRESH_REIGNITION", "FRESH_VOLUME_REGIME"}):
        return view
    if "WEBULL_TOP_MOVER" not in provenance:
        return view

    relation = str(record.get("vwap_relation") or "").lower()
    distance = _number(record, "vwap_distance_pct")
    near_vwap = relation == "above" and (distance is None or 0.0 <= distance <= 2.0)
    trend = bool(record.get("supertrend_bullish") or record.get("supertrend_flip"))
    participation = _number(record, "participation_surge_score", "participation_score") or 0.0
    volume_acceleration = _number(record, "volume_acceleration") or 0.0
    dollar_flow = _number(record, "dollar_flow_acceleration") or 0.0
    flow_confirmed = (
        participation >= 30.0
        or volume_acceleration >= 1.0
        or dollar_flow >= 1.25
    )
    if near_vwap and trend and flow_confirmed:
        return view

    downgraded = deepcopy(view)
    downgraded["state"] = unified.DEVELOPING
    downgraded["color"] = unified.STATE_COLORS[unified.DEVELOPING]
    downgraded["reason"] = (
        "Top-mover attention is present, but current structure/flow is not strong enough for LOOK NOW."
    )
    downgraded["next_step"] = (
        "Keep monitoring until price/trend and participation or fresh flow confirm the move."
    )
    return downgraded


def _exact_chime_markup(sound_path: str, count: int) -> str:
    """Play an exact cadence from one audio element instead of stacked components."""
    from .gs363_operator_attention_hierarchy import _extra_chime_markup

    # GS363's helper already performs serial replay from one audio element.  It
    # names its argument ``extra_chimes`` because GS363 also had a base chime;
    # GS364 suppresses that base sound and therefore passes the full desired count.
    return _extra_chime_markup(sound_path, max(0, int(count)))


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def _install_memory_containment() -> None:
    from . import flight_recorder, memory

    current_latest = memory.MemoryStore.latest_by_symbol
    if not getattr(current_latest, "_gs364_memory_containment", False):
        def latest_by_symbol(self, limit_lines=5000):
            return bounded_latest_by_symbol(self, limit_lines=limit_lines)

        _inherit(latest_by_symbol, current_latest)
        latest_by_symbol._gs364_memory_containment = True
        latest_by_symbol._gs364_original = current_latest
        memory.MemoryStore.latest_by_symbol = latest_by_symbol

    current_history = memory.MemoryStore.history_for_symbol
    if not getattr(current_history, "_gs364_memory_containment", False):
        def history_for_symbol(self, symbol: str):
            return bounded_history_for_symbol(self, symbol)

        _inherit(history_for_symbol, current_history)
        history_for_symbol._gs364_memory_containment = True
        history_for_symbol._gs364_original = current_history
        memory.MemoryStore.history_for_symbol = history_for_symbol

    current_memory_export = memory.MemoryStore.export_bytes
    if not getattr(current_memory_export, "_gs364_compressed_export", False):
        def memory_export_bytes(self):
            return _gzip_export(Path(self.path))

        _inherit(memory_export_bytes, current_memory_export)
        memory_export_bytes._gs364_compressed_export = True
        memory_export_bytes._gs364_original = current_memory_export
        memory.MemoryStore.export_bytes = memory_export_bytes

    current_flight_export = flight_recorder.FlightRecorder.export_bytes
    if not getattr(current_flight_export, "_gs364_compressed_export", False):
        def flight_export_bytes(self):
            return _gzip_export(Path(self.path))

        _inherit(flight_export_bytes, current_flight_export)
        flight_export_bytes._gs364_compressed_export = True
        flight_export_bytes._gs364_original = current_flight_export
        flight_recorder.FlightRecorder.export_bytes = flight_export_bytes


def _install_download_metadata() -> None:
    import streamlit as st

    current = st.download_button
    if getattr(current, "_gs364_compressed_export", False):
        return

    def download_button(label, *args, **kwargs):
        data = kwargs.get("data")
        if data is None and args:
            data = args[0]
        if _is_gzip_payload(data):
            filename = str(kwargs.get("file_name") or "")
            if filename and not filename.endswith(".gz"):
                kwargs["file_name"] = filename + ".gz"
            kwargs["mime"] = "application/gzip"
        return current(label, *args, **kwargs)

    _inherit(download_button, current)
    download_button._gs364_compressed_export = True
    download_button._gs364_original = current
    st.download_button = download_button

    # UI modules hold the same Streamlit module object, but assign explicitly for
    # hot-reload clarity and tests that monkeypatch the module binding.
    try:
        from . import ui
        ui.st.download_button = download_button
    except Exception:
        pass


def _install_look_now_precision() -> None:
    from . import gs310_unified_opportunity_state as unified
    from . import gs311_unified_voice as voice
    from . import gs314_state_consistency as consistency
    from . import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(current, "_gs364_look_now_precision", False):
        calibrated = current
    else:
        original = current

        def calibrated(record: dict) -> dict:
            view = original(record)
            if view.get("state") != unified.LOOK_NOW:
                return view

            provenance = set(view.get("attention_provenance") or [])
            if provenance.intersection(
                {"FRESH_NEWS_SEED", "FRESH_REIGNITION", "FRESH_VOLUME_REGIME"}
            ):
                return view
            if "WEBULL_TOP_MOVER" not in provenance:
                return view

            relation = str(record.get("vwap_relation") or "").lower()
            distance = _number(record, "vwap_distance_pct")
            near_vwap = relation == "above" and (
                distance is None or 0.0 <= distance <= 2.0
            )
            trend = bool(record.get("supertrend_bullish") or record.get("supertrend_flip"))
            participation = (
                _number(record, "participation_surge_score", "participation_score") or 0.0
            )
            volume_acceleration = _number(record, "volume_acceleration") or 0.0
            dollar_flow = _number(record, "dollar_flow_acceleration") or 0.0
            flow_confirmed = (
                participation >= 30.0
                or volume_acceleration >= 1.0
                or dollar_flow >= 1.25
            )
            if near_vwap and trend and flow_confirmed:
                return view

            downgraded = deepcopy(view)
            downgraded["state"] = unified.DEVELOPING
            downgraded["color"] = unified.STATE_COLORS[unified.DEVELOPING]
            downgraded["reason"] = (
                "Top-mover attention is present, but current structure/flow is not strong enough for LOOK NOW."
            )
            downgraded["next_step"] = (
                "Keep monitoring until price/trend and participation or fresh flow confirm the move."
            )
            return downgraded

        calibrated._gs364_look_now_precision = True
        calibrated._gs364_original = original
        unified.opportunity_state = calibrated

    # These modules imported the function directly, so update their local binding
    # to keep every visible/voice surface on the same state contract.
    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


def _install_exact_chimes() -> None:
    from . import ui
    from .gs363_operator_attention_hierarchy import alert_chime_count

    current = ui.play_alert
    if getattr(current, "_gs364_exact_chimes", False):
        return

    def play_alert(sound_path: str, phrase: str, voice_name: str = ""):
        if not phrase:
            return current(sound_path, phrase, voice_name)

        # Preserve GS311 speech/transport diagnostics while suppressing the prior
        # base + extra-chime audio layers.  Then emit exactly one serial cadence.
        silent_path = str(Path(sound_path).with_name("__walter_voice_only__.missing"))
        result = current(silent_path, phrase, voice_name)
        count = alert_chime_count(phrase)
        markup = _exact_chime_markup(sound_path, count)
        if markup:
            ui.st.components.v1.html(markup, height=0, scrolling=False)
        return result

    _inherit(play_alert, current)
    play_alert._gs364_exact_chimes = True
    play_alert._gs364_original = current
    ui.play_alert = play_alert


def install() -> None:
    """Install bounded history/export behavior and precise operator alerts."""
    _install_memory_containment()
    _install_download_metadata()
    _install_look_now_precision()
    _install_exact_chimes()
