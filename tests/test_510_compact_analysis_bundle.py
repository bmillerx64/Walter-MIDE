from datetime import datetime, timezone
import json
from pathlib import Path
from zipfile import ZipFile

from mide import gs510_compact_analysis_bundle as gs510


UTC = timezone.utc


def test_compact_bundle_keeps_rows_and_strips_only_cumulative_histories(tmp_path):
    candidate = tmp_path / "candidate_history.jsonl"
    flight = tmp_path / "flight_recorder.jsonl"
    rows = [
        {
            "symbol": "QNME",
            "timestamp": "2026-09-18T16:00:00Z",
            "price": 0.72,
            "participation_score": 71,
            "timeframes": {"1m": {"supertrend_bullish": True}},
            "architecture_audit": [{"stage": "one"}] * 20,
            "ranking_history": [{"rank": 1}] * 10,
            "discovery_history": [{"seen": True}] * 10,
            "reevaluation_history": [{"status": "LOOK NOW"}] * 10,
            "decision_explanation": {"why": "retain me"},
        },
        {
            "symbol": "MRNO",
            "timestamp": "2026-09-18T16:01:00Z",
            "price": 0.37,
            "mission_rank": 2,
            "catalyst_company_scale": {"relative_scale_band": "MAJOR_RELATIVE_SCALE"},
            "architecture_audit": [],
            "ranking_history": [],
            "discovery_history": [],
            "reevaluation_history": [],
        },
    ]
    candidate.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    flight_payload = b'{"scan_id":"one","symbols":["QNME","MRNO"]}\n'
    flight.write_bytes(flight_payload)

    info = gs510.build_analysis_bundle(
        candidate,
        flight,
        output_dir=tmp_path / "static",
        now=datetime(2026, 9, 18, 22, 0, tzinfo=UTC),
        token="fixed",
        review_window_hours=None,
    )

    archive = tmp_path / "static" / info["filename"]
    assert archive.exists()
    with ZipFile(archive) as zipped:
        compact_rows = [
            json.loads(line)
            for line in zipped.read("candidate_history_compact.jsonl").splitlines()
        ]
        assert zipped.read("flight_recorder.jsonl") == flight_payload
        manifest = json.loads(zipped.read("manifest.json"))

    assert [row["symbol"] for row in compact_rows] == ["QNME", "MRNO"]
    for row in compact_rows:
        for field in gs510.STRIPPED_CUMULATIVE_FIELDS:
            assert field not in row
    assert compact_rows[0]["decision_explanation"] == {"why": "retain me"}
    assert compact_rows[0]["timeframes"]["1m"]["supertrend_bullish"] is True
    assert compact_rows[1]["catalyst_company_scale"]["relative_scale_band"] == "MAJOR_RELATIVE_SCALE"
    assert manifest["candidate_rows"] == 2
    assert manifest["flight_recorder_semantics"] == "exact captured point-in-time prefix"
    assert manifest["trading_logic_changed"] is False


def test_compact_bundle_is_smaller_when_history_arrays_are_large(tmp_path):
    candidate = tmp_path / "candidate_history.jsonl"
    flight = tmp_path / "flight_recorder.jsonl"
    row = {
        "symbol": "RETO",
        "timestamp": "2026-09-18T15:00:00Z",
        "price": 4.2,
        "architecture_audit": [{"blob": "x" * 500}] * 100,
        "ranking_history": [{"blob": "y" * 500}] * 100,
        "discovery_history": [{"blob": "z" * 500}] * 100,
        "reevaluation_history": [{"blob": "w" * 500}] * 100,
    }
    candidate.write_text(json.dumps(row) + "\n", encoding="utf-8")
    flight.write_text('{"scan_id":"one"}\n', encoding="utf-8")

    info = gs510.build_analysis_bundle(
        candidate,
        flight,
        output_dir=tmp_path / "static",
        token="small",
    )

    assert info["candidate_compact_bytes"] < candidate.stat().st_size / 20


def test_live_app_renders_compact_analysis_controls():
    source = Path("app.py").read_text(encoding="utf-8")
    assert "render_compact_analysis_bundle_controls" in source


def test_gs552_compact_download_preloads_bytes_once_per_prepared_filename():
    source = Path("mide/gs510_compact_analysis_bundle.py").read_text(encoding="utf-8")
    assert "PAYLOAD_SESSION_KEY" in source
    assert '"bytes": archive_path.read_bytes()' in source
    assert 'data=payload["bytes"]' in source
    assert 'key=f"walter-gs552-download-{filename}"' in source
    assert 'on_click="ignore"' in source
    assert "data=materialize_compact_bundle" not in source



def test_gs560_default_review_bundle_keeps_only_recent_two_hour_window(tmp_path):
    candidate = tmp_path / "candidate_history.jsonl"
    flight = tmp_path / "flight_recorder.jsonl"
    now = datetime(2026, 9, 25, 3, 30, tzinfo=UTC)

    candidate_rows = [
        {
            "symbol": "OLD",
            "discovery_last_seen_at": "2026-09-25T00:30:00Z",
            "architecture_audit": [{"old": True}],
        },
        {
            "symbol": "EDGE",
            "discovery_last_seen_at": "2026-09-25T01:30:00Z",
            "ranking_history": [{"rank": 2}],
        },
        {
            "symbol": "NEW",
            "last_reevaluated_at": "2026-09-25T03:20:00Z",
            "reevaluation_history": [{"status": "LOOK NOW"}],
        },
    ]
    candidate.write_text(
        "".join(json.dumps(row) + "\n" for row in candidate_rows),
        encoding="utf-8",
    )
    flight_rows = [
        {"scan_id": "old", "timestamp": "2026-09-25T00:29:59+00:00"},
        {"scan_id": "edge", "timestamp": "2026-09-25T01:30:00+00:00"},
        {"scan_id": "new", "timestamp": "2026-09-25T03:29:00+00:00"},
    ]
    flight.write_text(
        "".join(json.dumps(row) + "\n" for row in flight_rows),
        encoding="utf-8",
    )

    info = gs510.build_analysis_bundle(
        candidate,
        flight,
        output_dir=tmp_path / "static",
        now=now,
        token="gs560",
    )

    archive = tmp_path / "static" / info["filename"]
    with ZipFile(archive) as zipped:
        compact_rows = [
            json.loads(line)
            for line in zipped.read("candidate_history_compact.jsonl").splitlines()
        ]
        compact_flight = [
            json.loads(line)
            for line in zipped.read("flight_recorder.jsonl").splitlines()
        ]
        manifest = json.loads(zipped.read("manifest.json"))

    assert [row["symbol"] for row in compact_rows] == ["EDGE", "NEW"]
    assert [row["scan_id"] for row in compact_flight] == ["edge", "new"]
    assert manifest["review_window_hours"] == gs510.REVIEW_WINDOW_HOURS
    assert manifest["review_window_start_utc"] == "2026-09-25T01:30:00+00:00"
    assert manifest["candidate_rows_seen"] == 3
    assert manifest["candidate_rows"] == 2
    assert manifest["candidate_rows_omitted"] == 1
    assert manifest["flight_rows_seen"] == 3
    assert manifest["flight_rows_retained"] == 2
    assert manifest["flight_rows_omitted"] == 1
    assert info["candidate_rows"] == 2
    assert info["flight_rows"] == 2


def test_gs560_ui_describes_bounded_review_bundle():
    source = Path("mide/gs510_compact_analysis_bundle.py").read_text(encoding="utf-8")

    assert "most recent {REVIEW_WINDOW_HOURS:g} hours" in source
    assert "Full Session Backup remains the complete archive" in source
    assert "review_window_start_utc" in source

def test_scope_lock_is_forensics_only():
    source = Path("mide/gs510_compact_analysis_bundle.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "expansion_score =",
        "opportunity_score =",
        "catalyst_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "place_order(",
        "submit_order(",
        "request_scan(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in source for token in forbidden)


def test_gs551_compact_bundle_uses_streamlit_static_root_and_href(tmp_path):
    candidate = tmp_path / "candidate_history.jsonl"
    flight = tmp_path / "flight_recorder.jsonl"
    candidate.write_text('{"symbol":"TEST"}\n', encoding="utf-8")
    flight.write_text('{"scan_id":"one"}\n', encoding="utf-8")

    info = gs510.build_analysis_bundle(
        candidate,
        flight,
        output_dir=tmp_path / "static",
        token="gs551",
    )

    assert info["href"] == f"/app/static/{info['filename']}"
    assert gs510.STATIC_DIR == Path("static")


def test_gs552_invalid_static_link_fallback_is_removed():
    source = Path("mide/gs510_compact_analysis_bundle.py").read_text(encoding="utf-8")
    assert "analysis_bundle_link_markup" not in source
    assert "Direct compact-bundle download" not in source
    assert 'data=payload["bytes"]' in source
    assert 'STATIC_DIR = Path("static")' in source

