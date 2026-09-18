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


def test_compact_download_is_deferred_bytes_not_eager_on_rerun():
    source = Path("mide/gs510_compact_analysis_bundle.py").read_text(encoding="utf-8")
    assert "data=materialize_compact_bundle" in source
    assert "return archive_path.read_bytes()" in source
    assert 'on_click="ignore"' in source


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
