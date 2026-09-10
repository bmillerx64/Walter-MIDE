from pathlib import Path

from mide import gs367_browser_audio_broker as broker
from mide import gs402_critical_only_audio as gs402
from mide import gs418_restore_routine_scan_audio as gs418


def test_gs418_restores_only_gs402_tier1_early_return():
    base = broker.browser_broker_markup("scan-418", 1)
    silenced = gs402._critical_only_markup(base)
    assert "if (tier === 1) return;" in silenced

    restored = gs418.restore_routine_tier(silenced)
    assert "if (tier === 1) return;" not in restored
    assert "const AudioContextCtor =" in restored
    assert "GS418: tier 1 is audible again" in restored


def test_gs418_preserves_one_two_three_note_semantic_patterns():
    assert len(broker.TONE_PATTERNS[1]) == 1
    assert len(broker.TONE_PATTERNS[2]) == 2
    assert len(broker.TONE_PATTERNS[3]) == 3


def test_gs418_installs_after_gs402_inside_final_audio_chain():
    source = Path("mide/gs399_attention_audio_envelope.py").read_text(encoding="utf-8")
    gs402_call = source.index("install_gs402()")
    gs418_call = source.index("install_gs418()")
    assert gs402_call < gs418_call


def test_gs418_does_not_touch_trading_authority():
    source = Path("mide/gs418_restore_routine_scan_audio.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "participation_score =",
        "expansion_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "opportunity_state =",
    )
    assert not any(token in source for token in forbidden)
