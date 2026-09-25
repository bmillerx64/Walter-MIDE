from pathlib import Path

from mide.authorities import market_evidence, presentation_audio
from mide.gs375_operator_awareness import reference_data_blocked_mover
from mide.webull_live import WebullOpenAPIClient


def _native(
    symbol,
    pct,
    rank,
    *,
    price,
    volume=150_000,
    sources=None,
):
    return {
        "symbol": symbol,
        "change_ratio": pct,
        "price": price,
        "volume": volume,
        "sources": sources or ["five_minute_movers"],
        "ranks": {"five_minute_movers": rank},
    }


def test_rdgt_like_five_minute_mover_enters_attention_lane_without_trade_authority(
    monkeypatch,
):
    monkeypatch.setattr(
        market_evidence,
        "_native_fast_mover_stage_active",
        True,
    )
    rows = [
        _native("RDGT", 36.93, 2, price=1.24),
        _native("QUIET", 14.99, 1, price=1.10),
        _native("RANK11", 40.0, 11, price=1.00),
    ]

    events = market_evidence.market_event_rows(rows)
    rdgt = next(event for event in events if event["symbol"] == "RDGT")

    assert rdgt["event_type"] == "five_minute_fast_mover"
    assert rdgt["pct_change"] == 36.93
    assert rdgt["rank"] == 2
    assert rdgt["attention_only"] is True
    assert "qualified_for_entry" not in rdgt
    assert "qualified_for_alert" not in rdgt
    assert {event["symbol"] for event in events} == {"RDGT"}


def test_fast_mover_above_five_is_kept_when_it_launched_from_strategy_range():
    events = market_evidence.fast_mover_rows(
        [_native("MSGY", 202.03, 1, price=5.95, volume=23_270_000)]
    )

    assert [event["symbol"] for event in events] == ["MSGY"]
    assert events[0]["strategy_price_reference"] == "implied_previous_close"
    assert events[0]["implied_previous_close"] < 5.0


def test_extreme_event_keeps_fast_mover_provenance_when_feeds_overlap(
    monkeypatch,
):
    monkeypatch.setattr(
        market_evidence,
        "_native_fast_mover_stage_active",
        True,
    )
    rows = [
        _native(
            "MSGY",
            202.03,
            1,
            price=5.95,
            volume=23_270_000,
            sources=["day_gainers", "five_minute_movers"],
        )
    ]
    rows[0]["ranks"]["day_gainers"] = 1

    events = market_evidence.market_event_rows(rows)
    assert len(events) == 1
    assert events[0]["symbol"] == "MSGY"
    assert events[0]["pct_change"] == 202.03
    assert events[0]["native_fast_mover"] is True
    assert events[0]["five_minute_rank"] == 1


def test_unresolved_day_gainer_keeps_reference_data_awareness():
    row = {
        "symbol": "RDGT",
        "discovery_reasons": ["Webull native: day_gainers"],
        "terminal_stage": "Free-Float Gate",
        "terminal_outcome": "Rejected",
        "free_float_verified": False,
        "free_float_verification_status": "unavailable-reject",
        "free_float_source": "low-float live refresh unresolved; fail closed",
    }

    assert reference_data_blocked_mover(row) is True


def test_rdgt_native_audio_calls_for_chart_even_when_float_is_unresolved():
    presentation_audio.reset_native_market_event_audio_state()
    event = {
        "symbol": "RDGT",
        "pct_change": 36.93,
        "rank": 2,
        "price": 1.24,
        "attention_only": True,
        "event_type": "five_minute_fast_mover",
    }
    record = {
        "symbol": "RDGT",
        "reference_data_blocked_awareness": True,
        "qualified_for_entry": False,
        "qualified_for_alert": False,
    }

    phrase = presentation_audio.native_market_event_audio_phrase(
        [record],
        [event],
    )

    assert "RDGT. FAST MOVER. LOOK NOW." in phrase
    assert "reference data is unresolved" in phrase
    assert "entry remains locked" in phrase
    assert presentation_audio.native_market_event_audio_phrase(
        [record],
        [event],
    ) == ""

    # Leaving the native event set rearms a genuine later re-entry.
    assert presentation_audio.native_market_event_audio_phrase([], []) == ""
    assert "FAST MOVER" in presentation_audio.native_market_event_audio_phrase(
        [record],
        [event],
    )


def test_hot_mover_with_stale_source_print_gets_possible_pause_not_fake_halt():
    presentation_audio.reset_native_market_event_audio_state()
    event = {
        "symbol": "MSGY",
        "pct_change": 202.03,
        "rank": 1,
        "price": 5.95,
        "attention_only": True,
        "native_fast_mover": True,
    }
    record = {
        "symbol": "MSGY",
        "source_bar_age_seconds": 121.0,
    }

    phrase = presentation_audio.native_market_event_audio_phrase(
        [record],
        [event],
    )

    assert "CHECK TRADING STATUS. LOOK NOW." in phrase
    assert "Possible trading pause or halt" in phrase
    assert "verify in Webull" in phrase
    assert "is halted" not in phrase.lower()


def test_explicit_sdk_suspension_truth_is_preserved_when_provider_supplies_it():
    class SDK:
        def get_stock_snapshot(self, **_kwargs):
            return {
                "data": [
                    {
                        "symbol": "RDGT",
                        "price": "1.24",
                        "volume": "143200",
                        "trading_status": "Suspended",
                    }
                ]
            }

    snapshot = WebullOpenAPIClient(
        "k",
        "s",
        sdk_client=SDK(),
    ).snapshots(["RDGT"])["RDGT"]

    assert snapshot["halted"] is True
    assert snapshot["trading_status"] == "Suspended"


def test_no_status_field_does_not_manufacture_halt_truth():
    class SDK:
        def get_stock_snapshot(self, **_kwargs):
            return {
                "data": [
                    {
                        "symbol": "LIVE",
                        "price": "1.00",
                        "volume": "1000",
                    }
                ]
            }

    snapshot = WebullOpenAPIClient(
        "k",
        "s",
        sdk_client=SDK(),
    ).snapshots(["LIVE"])["LIVE"]

    assert "halted" not in snapshot
    assert "trading_status" not in snapshot


def test_gs563_late_install_runs_after_established_final_audio_chain():
    source = Path("mide/startup.py").read_text(encoding="utf-8")
    body = source.split("def ensure_late_runtime_installers() -> None:", 1)[1]
    assert body.index("install_final_order()") < body.index("install_gs563()")


def test_gs563_facade_scope_lock_adds_no_provider_or_trade_authority():
    source = Path("mide/gs563_native_fast_mover_attention.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        ".bars(",
        ".get_bars(",
        ".history(",
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "place_order(",
        "submit_order(",
        "execute_order(",
    )
    assert not any(token in source for token in forbidden)
