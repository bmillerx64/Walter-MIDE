from copy import deepcopy

from mide import gs309_current_attention_mission as gs309
from mide import gs378_live_vwap_st_crossover as gs378
from mide import gs396_live_30s_tripwire as gs396
from mide import gs397_canonical_30s_tripwire_truth as gs397
from mide import ui


def _fresh_record(**updates):
    record = {
        "symbol": "GCDT",
        "vwap_value": 0.6800,
        "qualified_for_watch": False,
        "qualified_for_entry": False,
        "qualified_for_alert": False,
        "trigger": "NO",
        "supertrend_flip": False,
        "supertrend_bullish": False,
        "supertrend_30s_available": True,
        "supertrend_30s_bullish": True,
        "supertrend_30s_flip": True,
        "supertrend_30s_flip_age_seconds": 45.0,
        "supertrend_30s_last_flip_age_seconds": 45.0,
        "supertrend_30s_last_flip_timestamp": "2026-09-08T19:48:30+00:00",
        "thirty_second_tripwire": {
            "available": True,
            "authority": gs396.AUTHORITY,
            "source": gs396.SOURCE,
            "bullish": True,
            "fresh_flip": True,
            "last_flip_age_seconds": 45.0,
            "last_flip_timestamp": "2026-09-08T19:48:30+00:00",
            "latest_closed_timestamp": "2026-09-08T19:49:00+00:00",
            "latest_close": 0.6900,
            "supertrend_value": 0.6700,
            "volume_acceleration_30s": 2.4,
            "dollar_flow_acceleration_30s": 2.6,
        },
        # This deliberately recreates the closing-session split-brain regression:
        # the real stream says bullish while canonical Stage-6 alignment says false.
        "timeframe_alignment": {
            "30s": {
                "above_vwap": False,
                "supertrend_bullish": False,
                "above_ema65": True,
                "higher_highs_higher_lows": True,
                "aligned": False,
            },
            "1m": {"aligned": True},
            "3m": {"aligned": False},
        },
        "alignment_score": 1,
        "alignment_total": 3,
        "alignment_label": "Weak",
        "timeframes": {
            "1m": {"above_vwap": True, "supertrend": False},
            "3m": {"above_vwap": True, "supertrend": False},
        },
        "discovery_reasons": ["Webull native: absolute_volume"],
    }
    record.update(updates)
    return record


def test_canonicalization_replaces_false_30s_alignment_with_live_stream_truth():
    record = _fresh_record()
    before = {
        "qualified_for_watch": record["qualified_for_watch"],
        "qualified_for_entry": record["qualified_for_entry"],
        "qualified_for_alert": record["qualified_for_alert"],
        "trigger": record["trigger"],
        "supertrend_flip": record["supertrend_flip"],
    }

    result = gs397.canonicalize_record(record)
    thirty = result["timeframe_alignment"]["30s"]

    assert thirty["above_vwap"] is True
    assert thirty["supertrend_bullish"] is True
    assert thirty["aligned"] is True
    assert thirty["authority"] == gs396.AUTHORITY
    assert thirty["source"] == gs396.SOURCE
    assert thirty["fresh_flip"] is True
    assert thirty["operator_investigation_tripwire"] is True
    assert thirty["investigation_authority"] == "ATTENTION_ONLY_NOT_ENTRY_AUTHORITY"
    assert thirty["latest_close"] == 0.69
    assert thirty["supertrend_10_3"] == 0.67
    assert result["timeframes"]["30s"]["supertrend"] is True
    assert result["alignment_score"] == 2
    assert result["alignment_label"] == "Good"

    # GS397 may elevate attention/visibility, never trade authority.
    for key, value in before.items():
        assert result[key] == value


def test_canonical_30s_tripwire_never_satisfies_legacy_entry_supertrend():
    record = gs397.canonicalize_record(_fresh_record())

    entry_view = gs396.entry_authority_record(record)

    assert "supertrend_30s_flip" not in entry_view
    assert "supertrend_30s_flip_age_seconds" not in entry_view
    assert entry_view["supertrend_flip"] is False
    assert entry_view["supertrend_bullish"] is False
    assert record["supertrend_30s_flip"] is True


def test_fresh_30s_flip_becomes_current_attention_provenance_only():
    gs397.install()
    record = _fresh_record()

    provenance = gs309.current_attention_provenance(record)

    assert "FRESH_30S_TRIPWIRE" in provenance
    assert record["qualified_for_watch"] is False
    assert record["qualified_for_entry"] is False
    assert record["trigger"] == "NO"


def test_fresh_30s_flip_can_enter_operator_investigation_without_qualification_mutation():
    gs397.install()
    record = _fresh_record()

    original = deepcopy(record)
    assert ui.is_actionable_candidate(record) is True
    assert record["qualified_for_watch"] is False
    assert record["qualified_for_entry"] is False
    assert record == original


def test_stale_30s_state_does_not_bypass_watch_qualification():
    gs397.install()
    record = _fresh_record(
        supertrend_30s_flip=False,
        supertrend_30s_flip_age_seconds=None,
        thirty_second_tripwire={
            "available": True,
            "authority": gs396.AUTHORITY,
            "source": gs396.SOURCE,
            "bullish": True,
            "fresh_flip": False,
            "last_flip_age_seconds": 420.0,
            "latest_close": 0.69,
            "supertrend_value": 0.67,
        },
    )

    assert gs397.fresh_30s_tripwire(record) is False
    assert "FRESH_30S_TRIPWIRE" not in gs309.current_attention_provenance(record)
    assert ui.is_actionable_candidate(record) is False
    assert record["qualified_for_watch"] is False


def test_installers_are_active_at_the_intended_boundaries():
    gs397.install()

    assert getattr(gs378.apply_live_vwap_truth, "_gs397_canonical_30s", False)
    assert getattr(gs309.current_attention_provenance, "_gs397_30s_attention", False)
    assert getattr(ui.is_actionable_candidate, "_gs397_30s_investigation", False)


def test_local_stream_capture_is_bounded_and_requires_no_provider_request_api():
    class Provider:
        def __init__(self):
            self.calls = []

        def stream_30s_bars(self, symbol):
            self.calls.append(symbol)
            if symbol == "BAD":
                raise RuntimeError("local cache unavailable")
            return [{"timestamp_ms": 1, "close": 1.0}]

    provider = Provider()
    captured = gs397._capture_stream_rows(
        [{"symbol": "GCDT"}, {"symbol": "BAD"}, {"symbol": ""}],
        provider,
    )

    assert captured == {"GCDT": [{"timestamp_ms": 1, "close": 1.0}]}
    assert provider.calls == ["GCDT", "BAD"]
