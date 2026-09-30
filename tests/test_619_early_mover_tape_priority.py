from pathlib import Path

from mide import gs310_unified_opportunity_state as unified
from mide import gs619_early_mover_tape_priority as gs619
from mide.webull_native_radar import fetch_native_radar


def _envl(**overrides):
    record = {
        "symbol": "ENLV",
        "discovery_reasons": ["Webull native: five_minute_movers"],
        "vwap_relation": "above",
        "vwap_distance_pct": 1.2,
        "source_bar_age_seconds": 15.0,
        "price_trajectory_available": True,
        "price_change_3m_pct": 2.4,
        "price_change_5m_path_pct": 4.1,
        "price_path_acceleration_pct_per_min": 0.35,
        "positive_close_ratio_5m": 0.8,
        "giveback_from_5m_high_pct": 0.25,
        "volume_acceleration_3m": 1.45,
        "volume_acceleration_5m": 1.25,
        "dollar_flow_acceleration_3m": 1.40,
        "dollar_flow_acceleration_5m": 1.30,
        "higher_lows": True,
        "near_hod": True,
        "qualified_for_watch": False,
        "qualified_for_entry": False,
        "qualified_for_alert": False,
    }
    record.update(overrides)
    return record


def _view(state):
    return {
        "state": state,
        "color": unified.STATE_COLORS[state],
        "reason": "baseline",
        "next_step": "baseline",
        "evidence": [],
    }


def test_envl_style_current_min5_trajectory_earns_early_attention_without_authority():
    detail = gs619.early_fast_mover_attention(_envl())

    assert detail["active"] is True
    assert detail["change_5m_pct"] == 4.1
    assert detail["supporting_flow"] is True
    assert detail["trading_authority_changed"] is False


def test_envl_style_fast_mover_is_injected_as_awareness_only_when_scanner_not_actionable():
    source = _envl()
    rows = gs619.augment_visible_records([source], [])

    assert len(rows) == 1
    assert rows[0]["symbol"] == "ENLV"
    assert rows[0]["early_fast_mover_awareness"] is True
    assert rows[0]["qualified_for_entry"] is False
    assert rows[0]["qualified_for_alert"] is False
    assert "early_fast_mover_awareness" not in source


def test_envl_style_developing_card_becomes_look_now_but_extended_move_stays_chase():
    fast = gs619.opportunity_state(
        _envl(),
        lambda _record: _view(unified.DEVELOPING),
    )
    assert fast["state"] == unified.LOOK_NOW
    assert "5-minute mover" in fast["reason"]

    extended = gs619.opportunity_state(
        _envl(vwap_distance_pct=4.0),
        lambda _record: _view(unified.CHASE_WAIT),
    )
    assert extended["state"] == unified.CHASE_WAIT


def test_news_only_watch_for_entry_is_demoted_when_broad_tape_and_sustained_flow_are_absent():
    pusa = {
        "symbol": "PUSA",
        "discovery_reasons": ["FMP material news seed: TipRanks"],
        "volume_session_diagnostics": {
            "volume_passed": False,
            "dollar_volume_passed": True,
            "rvol_passed": False,
        },
        "volume_acceleration_3m": 1.25,
        "volume_acceleration_5m": 1.15,
        "dollar_flow_acceleration_3m": 1.30,
        "dollar_flow_acceleration_5m": 1.20,
    }

    detail = gs619.news_tape_confirmation(pusa)
    view = gs619.opportunity_state(
        pusa,
        lambda _record: _view(unified.WATCH_FOR_ENTRY),
    )

    assert detail["news_only"] is True
    assert detail["confirmed"] is False
    assert view["state"] == unified.DEVELOPING
    assert "live tape has not confirmed" in view["reason"]


def test_news_watch_for_entry_survives_when_three_and_five_minute_flow_are_sustained():
    pusa = {
        "symbol": "PUSA",
        "discovery_reasons": ["FMP material news seed: Reuters"],
        "volume_session_diagnostics": {
            "volume_passed": False,
            "dollar_volume_passed": True,
            "rvol_passed": False,
        },
        "volume_acceleration_3m": 1.85,
        "volume_acceleration_5m": 1.75,
        "dollar_flow_acceleration_3m": 1.90,
        "dollar_flow_acceleration_5m": 1.80,
    }

    detail = gs619.news_tape_confirmation(pusa)
    view = gs619.opportunity_state(
        pusa,
        lambda _record: _view(unified.WATCH_FOR_ENTRY),
    )

    assert detail["sustained_flow"] is True
    assert detail["confirmed"] is True
    assert view["state"] == unified.WATCH_FOR_ENTRY


def test_news_plus_current_day_gainer_is_not_treated_as_news_only():
    row = {
        "symbol": "HOT",
        "discovery_reasons": [
            "FMP material news seed: Reuters",
            "Webull native: day_gainers",
        ],
        "volume_session_diagnostics": {
            "volume_passed": False,
            "dollar_volume_passed": False,
            "rvol_passed": False,
        },
    }

    detail = gs619.news_tape_confirmation(row)
    view = gs619.opportunity_state(
        row,
        lambda _record: _view(unified.WATCH_FOR_ENTRY),
    )

    assert detail["news_only"] is False
    assert view["state"] == unified.WATCH_FOR_ENTRY


class Screener:
    def get_gainers_losers(self, **kwargs):
        if kwargs["rank_type"] == "DAY_1":
            return [
                {
                    "symbol": "ENLV",
                    "price": 0.52,
                    "change_ratio": 15.0,
                    "volume": 300_000,
                }
            ]
        return [
            {
                "symbol": "ENLV",
                "price": 0.52,
                "change_ratio": 4.1,
                "volume": 65_000,
            }
        ]

    def get_most_active(self, **kwargs):
        return [
            {
                "symbol": "ENLV",
                "price": 0.52,
                "change_ratio": 15.0,
                "volume": 300_000,
                "relative_volume_10d": 2.2,
            }
        ]


class Client:
    screener = Screener()


def test_native_radar_retains_day_and_five_minute_measurements_separately(monkeypatch):
    # Keep the day-gainer contract on DAY_1 regardless of wall-clock test time.
    from mide import webull_native_radar as radar
    monkeypatch.setattr(radar, "_day_gainers_rank_type", lambda: "DAY_1")

    report = fetch_native_radar(Client())
    row = next(item for item in report["symbols"] if item["symbol"] == "ENLV")

    assert row["change_ratio"] == 15.0
    assert row["feed_metrics"]["day_gainers"]["change_ratio"] == 15.0
    assert row["feed_metrics"]["five_minute_movers"]["change_ratio"] == 4.1
    assert row["feed_metrics"]["five_minute_movers"]["rank"] == 1


def test_gs619_installs_after_gs563_and_scope_is_presentation_only():
    startup = Path("mide/startup.py").read_text(encoding="utf-8")
    body = startup.split("def ensure_late_runtime_installers() -> None:", 1)[1]
    assert body.index("install_gs563()") < body.index("install_gs619()")

    source = Path("mide/gs619_early_mover_tape_priority.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        ".bars(",
        ".get_bars(",
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "place_order(",
        "submit_order(",
        "execute_order(",
    )
    assert not any(token in source for token in forbidden)
