from io import BytesIO
from pathlib import Path

from mide import gs496_static_session_backup as gs496


class ForceZip64Archive:
    def __init__(self):
        self.calls = []

    def open(self, arcname, mode, *, force_zip64=False):
        self.calls.append(
            {
                "arcname": arcname,
                "mode": mode,
                "force_zip64": force_zip64,
            }
        )
        if not force_zip64:
            raise RuntimeError("File size too large, try using force_zip64")
        return BytesIO()


def test_streamed_member_forces_zip64_writer_path(tmp_path):
    source = tmp_path / "candidate_history.jsonl"
    payload = b'{"symbol":"WALT"}\n' * 100
    source.write_bytes(payload)
    archive = ForceZip64Archive()

    copied = gs496._write_snapshot_member(
        archive,
        source,
        "candidate_history.jsonl",
        captured_size=len(payload),
        chunk_bytes=17,
    )

    assert copied == len(payload)
    assert archive.calls == [
        {
            "arcname": "candidate_history.jsonl",
            "mode": "w",
            "force_zip64": True,
        }
    ]


def test_source_explicitly_keeps_archive_and_member_zip64_enabled():
    source = Path("mide/gs496_static_session_backup.py").read_text(encoding="utf-8")

    assert "allowZip64=True" in source
    assert 'archive.open(arcname, "w", force_zip64=True)' in source


def test_gs507_forces_clean_runtime_without_breaking_gs445_marker_contract():
    requirements = Path("requirements.txt").read_text(encoding="utf-8")

    assert requirements.startswith("# GS445 deployment marker:")
    assert "# GS506 deployment marker:" in requirements
    assert "# GS507 deployment marker:" in requirements


def test_scope_lock_is_backup_transport_only():
    source = Path("mide/gs496_static_session_backup.py").read_text(encoding="utf-8")
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
