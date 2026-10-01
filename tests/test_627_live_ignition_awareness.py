from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from mide import gs396_live_30s_tripwire as gs396
from mide import gs627_live_ignition_awareness as gs627


NOW = datetime(2026, 10, 1, 15, 10, tzinfo=timezone.utc)


class FakeProvider:
    def __init__(self, prices):
        self.prices = dict(prices)

    def latest_trades(self, symbols, *, initialize=True):
        assert initialize is False
        return {symbol: self.prices[symbol] for symbol in symbols if symbol in self.prices}


def base_record(**updates):
    record = {
        "symbol": "GOGO",
        "price": 2.12,
        "vwap_value": 2.10,
        "participation_score": 93.0,
        "expansion_quality": 48.0,
        "candidate_status": "Developing",
        "qualified_for_entry": False,
        "qualified_for_alert": False,
    }
    record.update(updates)
    return record


def test_gs627_gogo_style_awareness_surfaces_before_entry_authority(monkeypatch):
    original = base_record()
    frozen = deepcopy(original)

    def enrich(record, provider, scan_time):
        enriched = dict(record)
        enriched["thirty_second_tripwire"] = {
            "bullish": True,
            "fresh_flip": True,
            "last_flip_age_seconds": 12.0,
            "latest_closed_timestamp": "2026-10-01T15:09:30+00:00",
            "volume_acceleration_30s": 1.8,
            "dollar_flow_acceleration_30s": 1.6,
        }
        return enriched

    monkeypatch.setattr(gs396, "enrich_record_with_live_30s", enrich)

    result = gs627._evaluate_record(
        original,
        FakeProvider({"GOGO": 2.14}),
        NOW,
    )

    assert result is not None
    assert result["symbol"] == "GOGO"
    assert result["boxes_checked"] == 4
    assert result["boxes"]["live_price_above_last_scan_vwap"] is True
    assert result["boxes"]["genuine_30s_st_bullish"] is True
    assert result["boxes"]["fresh_genuine_30s_st_flip"] is True
    assert result["boxes"]["last_scan_participation_at_trigger_floor"] is True
    assert result["boxes"]["last_scan_expansion_at_trigger_floor"] is False
    assert result["awareness_only"] is True
    assert result["qualified_for_entry_changed"] is False
    assert result["candidate_state_changed"] is False
    assert original == frozen


def test_gs627_requires_live_interest_without_loosening_thresholds(monkeypatch):
    def enrich(record, provider, scan_time):
        enriched = dict(record)
        enriched["thirty_second_tripwire"] = {
            "bullish": False,
            "fresh_flip": False,
            "volume_acceleration_30s": 0.8,
        }
        return enriched

    monkeypatch.setattr(gs396, "enrich_record_with_live_30s", enrich)

    result = gs627._evaluate_record(
        base_record(
            participation_score=20.0,
            expansion_quality=20.0,
            vwap_value=2.50,
        ),
        FakeProvider({"GOGO": 2.10}),
        NOW,
    )

    assert result is None


def test_gs627_reads_live_price_cache_without_initializing_network(monkeypatch):
    calls = []

    class Provider(FakeProvider):
        def latest_trades(self, symbols, *, initialize=True):
            calls.append(initialize)
            return super().latest_trades(symbols, initialize=initialize)

    def enrich(record, provider, scan_time):
        enriched = dict(record)
        enriched["thirty_second_tripwire"] = {
            "bullish": True,
            "fresh_flip": True,
            "last_flip_age_seconds": 5.0,
        }
        return enriched

    monkeypatch.setattr(gs396, "enrich_record_with_live_30s", enrich)
    gs627._evaluate_record(base_record(), Provider({"GOGO": 2.14}), NOW)

    assert calls == [False]


def test_gs627_runtime_boundary_has_no_scan_trade_audio_authority():
    source = Path("mide/gs627_live_ignition_awareness.py").read_text(encoding="utf-8")

    forbidden = (
        "apply_scanner_v2(",
        "qualified_for_entry(",
        "request_scan(",
        "play_alert(",
        "place_order(",
        "submit_order(",
        "cancel_order(",
        "snapshots(",
        ".bars(",
        "initialize_quotes(",
    )
    assert not any(token in source for token in forbidden)


def test_gs627_ui_is_fragment_owned_and_explicitly_awareness_only():
    source = Path("app.py").read_text(encoding="utf-8")

    assert '@st.fragment(run_every=timedelta(seconds=2))' in source
    assert "def render_live_ignition_watch()" in source
    assert "Awareness only — does not change Walter state" in source
    assert ".ensure_running()" in source
