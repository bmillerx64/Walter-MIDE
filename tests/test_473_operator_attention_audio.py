from __future__ import annotations

from pathlib import Path

from mide import escalation
from mide import gs473_operator_attention_audio as gs473


def _tf(bullish=True, above=True, available=True):
    return {
        "data_available": available,
        "current_supertrend_bullish": bullish,
        "current_above_vwap": above,
    }


def _lesl(**overrides):
    record = {
        "symbol": "LESL",
        "candidate_status": "Entry Ready",
        "status": "WATCH NOW",
        "qualified_for_entry": False,
        "qualified_for_alert": False,
        "vwap_distance_pct": 9.5678,
        "participation_gate": {"passed": True},
        "structure_gate": {"passed": True},
        "timeframes": {
            "30s": _tf(bullish=False, above=False, available=False),
            "1m": _tf(),
            "3m": _tf(),
            "5m": _tf(),
        },
    }
    record.update(overrides)
    return record


def test_lesl_live_shape_gets_one_look_now_attention_phrase_without_entry_authority():
    record = _lesl()

    detail = gs473.operator_attention_candidate(record)
    phrase = gs473.operator_attention_audio_phrase([record])

    assert detail["active"] is True
    assert detail["fresh"] is True
    assert detail["cascade"] == ["1m", "3m", "5m"]
    assert detail["qualified_for_entry"] is False
    assert detail["qualified_for_alert"] is False
    assert phrase.startswith("LESL. LOOK NOW.")
    assert "1m, 3m, and 5m are bullish above VWAP" in phrase
    assert "Extended 9.6 percent above VWAP" in phrase
    assert "Do not chase" in phrase


def test_same_continuous_watch_now_is_not_repeated_next_scan():
    record = _lesl(
        opportunity_pulse_previous={
            "symbol": "LESL",
            "candidate_status": "Entry Ready",
            "status": "WATCH NOW",
        }
    )

    assert gs473.operator_attention_candidate(record)["active"] is True
    assert gs473.operator_attention_candidate(record)["fresh"] is False
    assert gs473.operator_attention_audio_phrase([record]) == ""


def test_fresh_watch_now_requires_existing_participation_structure_and_cascade():
    failed_participation = _lesl(participation_gate={"passed": False})
    weak_structure = _lesl(structure_gate={"passed": False})
    no_cascade = _lesl(
        timeframes={
            "30s": _tf(bullish=False, above=False, available=False),
            "1m": _tf(),
            "3m": _tf(),
            "5m": _tf(bullish=False),
        }
    )

    assert gs473.operator_attention_audio_phrase([failed_participation]) == ""
    assert gs473.operator_attention_audio_phrase([weak_structure]) == ""
    assert gs473.operator_attention_audio_phrase([no_cascade]) == ""


def test_genuine_30s_1m_3m_path_can_alert_before_5m_confirmation():
    record = _lesl(
        vwap_distance_pct=2.2,
        timeframes={
            "30s": _tf(),
            "1m": _tf(),
            "3m": _tf(),
            "5m": _tf(bullish=False),
        },
    )

    phrase = gs473.operator_attention_audio_phrase([record])

    assert "30s, 1m, and 3m are bullish above VWAP" in phrase
    assert "Attention only; entry is not authorized yet" in phrase
    assert "Do not chase" not in phrase


def test_existing_escalation_audio_keeps_priority(monkeypatch):
    calls = []

    def established(records):
        calls.append(records)
        return "WALT escalation changed to Entry Window Open."

    monkeypatch.setattr(escalation, "escalation_alert_phrase", established)
    gs473.install()

    phrase = escalation.escalation_alert_phrase([_lesl()])

    assert phrase == "WALT escalation changed to Entry Window Open."
    assert len(calls) == 1


def test_installer_is_idempotent(monkeypatch):
    monkeypatch.setattr(escalation, "escalation_alert_phrase", lambda records: "")
    gs473.install()
    first = escalation.escalation_alert_phrase
    gs473.install()
    second = escalation.escalation_alert_phrase

    assert first is second
    assert getattr(first, "_walter_gs473_operator_attention_audio_owner", False) is True


def test_gs384_installs_gs473_before_its_idempotence_return():
    source = Path("mide/gs384_diagnostic_signal_to_noise.py").read_text(encoding="utf-8")
    assert "gs473_operator_attention_audio" in source
    assert source.index("install_gs473()") < source.index(
        'if getattr(current_sources, "_gs384_signal_to_noise", False):'
    )


def test_scope_lock_audio_only_never_mutates_scanner_or_execution_authority():
    source = Path("mide/gs473_operator_attention_audio.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_watch =",
        "qualified_for_entry =",
        "qualified_for_alert =",
        "candidate_status =",
        "participation_score =",
        "expansion_score =",
        "vwap_distance_pct =",
        "place_order(",
        "ensure_stream(",
    )
    assert not any(token in source for token in forbidden)
    assert '"entry_authority_changed": False' in source
    assert '"alert_authority_changed": False' in source
