from __future__ import annotations
from datetime import datetime, timedelta, timezone
import math
import re
import pandas as pd
import numpy as np

from .indicators import (
    ema,
    session_vwap,
    supertrend,
    resample_ohlcv,
    volume_acceleration,
    green_volume_ratio,
    higher_lows,
    proximity_pct,
    intraday_participation_metrics,
)
from .volume_pace import volume_pace_metrics
from .scoring import Evidence, score
from .flight_recorder import prefilter_decision
from .timeframe_alignment import alignment_summary

# Fourteen calendar days reliably covers at least five completed U.S. trading
# sessions across weekends and ordinary exchange holidays.
VOLUME_PROFILE_LOOKBACK_DAYS = 14


def _value(obj, *path, default=None):
    cur = obj
    for key in path:
        if cur is None:
            return default
        cur = cur.get(key) if isinstance(cur, dict) else None
    return default if cur is None else cur


_US_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.-]{0,14}$")


def is_valid_us_symbol(symbol):
    symbol = str(symbol or "").strip().upper()
    return bool(_US_SYMBOL_RE.fullmatch(symbol)) and ":" not in symbol


def snapshot_identity_records(snapshots):
    """Extract only the reference fields needed by the Stage 2 identity gate."""
    records = []
    for symbol, snap in snapshots.items():
        trade = snap.get("latestTrade") or {}
        daily = snap.get("dailyBar") or {}
        reference = snap.get("reference") or {}
        record = {
            "symbol": symbol,
            "tradable": snap.get("tradable", True),
            "halted": snap.get("halted", False),
            "asset_type": snap.get("asset_type") or snap.get("type"),
            "exchange": snap.get("exchange"),
            "asset_status": snap.get("asset_status") or snap.get("status", "active"),
            "price": float(trade.get("p") or daily.get("c") or 0),
        }
        if snap.get("free_float_source"):
            record["free_float_source"] = snap["free_float_source"]
        for key in ("float_shares", "shares_float", "free_float", "float_millions"):
            value = snap.get(key)
            location = "snapshot"
            if value is None:
                value = reference.get(key)
                location = "snapshot.reference"
            if value is not None:
                record[key] = value
                provider = reference.get("provider") or reference.get("source")
                record["free_float_source"] = snap.get("free_float_source") or (
                    f"{provider} ({location}.{key})" if provider
                    else f"{location}.{key} (provider unspecified)"
                )
                break
        records.append(record)
    return records


def build_seed_symbols(client, settings, news_items, *, universe_verification=None):
    symbols: set[str] = set()
    why: dict[str, list[str]] = {}

    def add(symbol, reason):
        symbol = str(symbol or "").strip().upper()
        if is_valid_us_symbol(symbol):
            symbols.add(symbol)
            why.setdefault(symbol, []).append(reason)

    call = universe_verification.call if universe_verification else None
    movers = (call("Market movers", "movers", {"top": 50}, lambda: client.movers(50))
              if call else client.movers(50))
    for item in movers:
        add(item.get("symbol"), "market mover")

    actives = (call("Most active stocks", "most_actives", {"top": 100, "by": "volume"},
                    lambda: client.most_actives(100)) if call else client.most_actives(100))
    for item in actives:
        add(item.get("symbol"), "most active")

    # News is evidence for candidates already admitted by Universe Construction.
    # It must never expand the universe, even when callers provide prefetched news.
    client.diagnostics["news_symbols"] = 0

    # Add a rotating broad-market slice. Alpaca is preferred; a public symbol
    # directory is used only when the trading asset endpoint is unavailable.
    try:
        assets = (call("Alpaca active tradable assets", "assets",
                       {"status": "active", "asset_class": "us_equity"}, client.assets)
                  if call else client.assets())
        eligible_assets = [
            str(item.get("symbol") or "").strip().upper()
            for item in assets
            if item.get("tradable") and item.get("status") == "active"
        ]
        source = "Alpaca assets"
    except Exception as exc:
        client.warnings.append(f"Alpaca asset universe unavailable: {exc}")
        try:
            eligible_assets = (call("Nasdaq Trader symbol directory", "public_symbol_fallback", {},
                                    client.public_symbol_fallback)
                               if call else client.public_symbol_fallback())
            source = "Nasdaq Trader fallback"
        except Exception as fallback_exc:
            eligible_assets = []
            source = "none"
            client.warnings.append(f"Broad-market fallback unavailable: {fallback_exc}")

    eligible_assets = [s for s in eligible_assets if is_valid_us_symbol(s)]
    client.diagnostics["broad_source"] = source
    client.diagnostics["broad_eligible"] = len(eligible_assets)

    if eligible_assets:
        minute_bucket = int(datetime.now(timezone.utc).timestamp() // 60)
        window = min(settings.max_seed_symbols, len(eligible_assets))
        start_index = (minute_bucket * window) % len(eligible_assets)
        rotated = (eligible_assets[start_index:] + eligible_assets[:start_index])[
            :window
        ]
        for symbol in rotated:
            add(symbol, "broad market sweep")

    client.diagnostics["final_seed_count"] = len(symbols)
    return sorted(symbols), why


def prefilter_snapshots(snapshots, settings):
    selected = []
    for symbol, snap in snapshots.items():
        trade = snap.get("latestTrade") or {}
        quote = snap.get("latestQuote") or {}
        daily = snap.get("dailyBar") or {}
        previous = snap.get("prevDailyBar") or {}
        price = float(trade.get("p") or daily.get("c") or 0)
        prev_close = float(previous.get("c") or 0)
        volume = float(daily.get("v") or 0)
        pct = ((price / prev_close) - 1) * 100 if prev_close else 0
        bid = float(quote.get("bp") or 0)
        ask = float(quote.get("ap") or 0)
        spread = (
            ((ask - bid) / ((ask + bid) / 2) * 100)
            if bid and ask and ask >= bid
            else 99
        )
        dollar = price * volume
        # Keep filtering and recorder explanations on one exact rule definition.
        if not prefilter_decision(symbol, snap, settings)["passed"]:
            continue
        candidate = {
                "symbol": symbol,
                "tradable": snap.get("tradable", True),
                "halted": snap.get("halted", False),
                "asset_type": snap.get("asset_type") or snap.get("type"),
                "exchange": snap.get("exchange"),
                "asset_status": snap.get("asset_status") or snap.get("status", "active"),
                "price": price,
                "pct_change": pct,
                "volume": volume,
                "dollar_volume": dollar,
                "spread_pct": spread,
                "day_high": float(daily.get("h") or price),
                "prev_volume": float(previous.get("v") or 0),
            }
        # Preserve reference-data float fields for the authoritative Stage 2
        # gate.  Snapshot adapters may expose any of these established names.
        for key in ("float_shares", "shares_float", "free_float", "float_millions"):
            value = snap.get(key)
            if value is None:
                value = (snap.get("reference") or {}).get(key)
            if value is not None:
                candidate[key] = value
                if snap.get("free_float_source"):
                    candidate["free_float_source"] = snap["free_float_source"]
        selected.append(candidate)
    return sorted(
        selected, key=lambda x: (x["pct_change"], x["dollar_volume"]), reverse=True
    )


def _timeframe_confirmation(frame):
    confirmations = 0
    details = {}
    for label, rule in [
        ("1m", "1min"),
        ("3m", "3min"),
        ("5m", "5min"),
        ("10m", "10min"),
    ]:
        x = frame if label == "1m" else resample_ohlcv(frame, rule)
        if len(x) < 20:
            continue
        vw = session_vwap(x).iloc[-1]
        st, trend = supertrend(x, 10, 3)
        close = float(x["close"].iloc[-1])
        bullish = bool(trend.iloc[-1]) if len(trend) else False
        above_vwap = close >= vw if not pd.isna(vw) else False
        if bullish and above_vwap:
            confirmations += 1
        details[label] = {"above_vwap": above_vwap, "supertrend": bullish}
    return confirmations, details


def _percentile(values, value):
    if not values:
        return 0.0
    ordered = sorted(values)
    below = sum(v < value for v in ordered)
    equal = sum(v == value for v in ordered)
    return ((below + 0.5 * equal) / len(ordered)) * 100


def apply_attention_ranking(records):
    """Add cohort-relative market dominance and promote the true session leaders."""
    if not records:
        return records
    volumes = [max(0.0, float(r.get("volume", 0))) for r in records]
    dollars = [max(0.0, float(r.get("dollar_volume", 0))) for r in records]
    changes = [max(0.0, float(r.get("pct_change", 0))) for r in records]
    rvols = [max(0.0, float(r.get("rvol_proxy", 0))) for r in records]

    for r in records:
        cohort = (
            _percentile(volumes, float(r.get("volume", 0))) * 0.34
            + _percentile(dollars, float(r.get("dollar_volume", 0))) * 0.28
            + _percentile(changes, max(0.0, float(r.get("pct_change", 0)))) * 0.22
            + _percentile(rvols, float(r.get("rvol_proxy", 0))) * 0.16
        )
        # A hybrid score prevents dominance from collapsing to zero in a small
        # live cohort while still distinguishing the leader from its peers.
        volume_abs = min(
            100.0,
            math.log10(max(float(r.get("volume", 0)), 1) / 100_000 + 1)
            / math.log10(1001)
            * 100,
        )
        dollar_abs = min(
            100.0,
            math.log10(max(float(r.get("dollar_volume", 0)), 1) / 100_000 + 1)
            / math.log10(2501)
            * 100,
        )
        change_abs = min(100.0, max(0.0, float(r.get("pct_change", 0))) / 50 * 100)
        rvol_abs = min(100.0, max(0.0, float(r.get("rvol_proxy", 0))) / 10 * 100)
        absolute = (
            volume_abs * 0.34 + dollar_abs * 0.28 + change_abs * 0.22 + rvol_abs * 0.16
        )
        dominance = cohort * 0.55 + absolute * 0.45
        historical = (
            float(r.get("historical_strength", r.get("attention_score", 0))) * 0.54
            + float(r.get("participation_score", 0)) * 0.22
            + dominance * 0.24
        )
        r["market_dominance_score"] = round(dominance, 1)
        r["historical_strength"] = round(min(100.0, historical), 1)
        r["attention_score"] = r["historical_strength"]
        r.setdefault("current_momentum", r.get("opportunity_score", 0))

        if r["status"] != "PASS":
            if (
                r["attention_score"] >= 82
                and r["participation_score"] >= 60
                and dominance >= 78
            ):
                r["status"] = "EXCEPTIONAL"
                r["participation_tier"] = (
                    "DOMINANT" if dominance >= 92 else "EXCEPTIONAL"
                )
            elif r["attention_score"] >= 72 and r["status"] in {"MONITOR", "WATCH NOW"}:
                r["status"] = "WATCH NOW"
        if dominance >= 85:
            r["reasons"] = [f"Market dominance {dominance:.0f}/100"] + r.get(
                "reasons", []
            )
    from mide.opportunity import enrich_opportunity

    for record in records:
        enrich_opportunity(record)
    return sorted(
        records,
        key=lambda x: (
            x.get("current_momentum", x.get("opportunity_score", 0)),
            x.get("historical_strength", x.get("attention_score", 0)),
            x.get("market_dominance_score", 0),
        ),
        reverse=True,
    )


def analyze_candidates(client, candidates, news_index, discovery_reasons):
    if not candidates:
        return []
    start = datetime.now(timezone.utc) - timedelta(days=VOLUME_PROFILE_LOOKBACK_DAYS)
    symbols = [
        x["symbol"] for x in candidates if is_valid_us_symbol(x.get("symbol"))
    ]
    raw = client.bars(symbols, start=start, timeframe="1Min", limit=10_000)
    try:
        raw_30s = client.bars(symbols, start=start, timeframe="30Sec", limit=10_000)
    except Exception as exc:
        raw_30s = {}
        if hasattr(client, "warnings"):
            client.warnings.append(f"30-second trend confirmation unavailable: {exc}")
    from mide.relative_strength import benchmark_for, relative_strength_metrics

    benchmark_symbols = sorted({benchmark_for(item) for item in candidates})
    try:
        benchmark_raw = client.bars(
            benchmark_symbols, start=start, timeframe="1Min", limit=10_000
        )
    except Exception as exc:
        benchmark_raw = {}
        if hasattr(client, "warnings"):
            client.warnings.append(f"Relative-strength benchmarks unavailable: {exc}")
    output = []

    for item in candidates:
        symbol = item["symbol"]
        frame = client.bars_frame(raw.get(symbol, []))
        if len(frame) < 20:
            continue
        # Current session approximation: use the latest calendar date present.
        latest_date = frame.index[-1].date()
        session = frame[frame.index.date == latest_date].copy()
        if len(session) < 12:
            session = frame.tail(150).copy()

        benchmark_symbol = benchmark_for(item)
        benchmark_frame = client.bars_frame(benchmark_raw.get(benchmark_symbol, []))
        benchmark_session = benchmark_frame[
            benchmark_frame.index.date == latest_date
        ].copy()
        if len(benchmark_session) < 2:
            benchmark_session = benchmark_frame.tail(150).copy()
        rs_metrics = relative_strength_metrics(session, benchmark_session)

        price = float(session["close"].iloc[-1])
        vw = float(session_vwap(session).iloc[-1])
        ema65 = (
            float(ema(session["close"], 65).iloc[-1])
            if len(session) >= 65
            else float("nan")
        )
        st_line, st_trend = supertrend(session, 10, 3)
        st_value = (
            float(st_line.iloc[-1])
            if len(st_line) and not pd.isna(st_line.iloc[-1])
            else 0.0
        )
        st_bull = bool(st_trend.iloc[-1]) if len(st_trend) else False
        st_flip = bool(
            len(st_trend) >= 2 and st_trend.iloc[-1] and not st_trend.iloc[-2]
        )
        tf_count, tf_details = _timeframe_confirmation(session)
        thirty_second_frame = client.bars_frame(raw_30s.get(symbol, []))
        if len(thirty_second_frame):
            thirty_second_frame = thirty_second_frame[
                thirty_second_frame.index.date == latest_date
            ].copy()
        alignment = alignment_summary(
            {
                "30s": thirty_second_frame,
                "1m": session,
                "5m": resample_ohlcv(session, "5min"),
            }
        )

        news = news_index.get(symbol)
        headline = news["headline"] if news else ""
        age_hours = None
        catalyst_score = 0
        flags = []
        if news:
            age_hours = (
                datetime.now(timezone.utc) - news["created_at"]
            ).total_seconds() / 3600
            catalyst_score = news["catalyst_score"]
            flags = news["flags"]

        day_high = max(item["day_high"], float(session["high"].max()))
        previous_volume = item["prev_volume"]
        elapsed_fraction = max(0.08, min(1.0, len(session) / 390))
        expected_so_far = previous_volume * elapsed_fraction
        rvol_proxy = item["volume"] / expected_so_far if expected_so_far > 0 else 1.0

        vwap_distance = (
            ((price - vw) / vw * 100.0) if vw and not math.isnan(vw) else 999.0
        )
        vwap_relation = (
            "above"
            if vwap_distance >= 0
            else ("testing" if vwap_distance >= -1.0 else "below")
        )
        last_bar_time = session.index[-1]
        bar_age_seconds = max(
            0.0,
            (
                datetime.now(timezone.utc) - last_bar_time.to_pydatetime()
            ).total_seconds(),
        )

        vpi = volume_pace_metrics(symbol, frame)
        surge_metrics = intraday_participation_metrics(session)
        ema5_value = float(ema(session["close"], 5).iloc[-1])
        ten_minute_start = (
            float(session["close"].iloc[-11]) if len(session) > 10 else price
        )
        price_change_10m_pct = (
            ((price / ten_minute_start) - 1) * 100 if ten_minute_start else 0
        )
        prior_15 = session.iloc[-16:-1] if len(session) >= 16 else session.iloc[:-1]
        recent_5 = session.tail(5)
        prior_15_pace = float(prior_15["volume"].mean()) if len(prior_15) else 0
        recent_pace = float(recent_5["volume"].mean()) if len(recent_5) else 0
        broke_15m_high = bool(
            len(prior_15)
            and price > float(prior_15["high"].max())
            and recent_pace > prior_15_pace
        )
        session_vwaps = session_vwap(session)
        recent_closes = session["close"].tail(11)
        recent_vwaps = session_vwaps.tail(11)
        reclaimed_10m = bool(
            len(recent_closes) > 1
            and (recent_closes.iloc[:-1] < recent_vwaps.iloc[:-1]).any()
            and price >= vw
        )
        reclaim_crosses = recent_closes >= recent_vwaps
        reclaim_age_bars = next(
            (
                age
                for age in range(min(5, len(reclaim_crosses) - 1) + 1)
                if bool(reclaim_crosses.iloc[-1 - age])
                and (
                    len(reclaim_crosses) - 1 - age == 0
                    or not bool(reclaim_crosses.iloc[-2 - age])
                )
            ),
            999,
        )

        evidence = Evidence(
            symbol=symbol,
            price=price,
            pct_change=item["pct_change"],
            volume=item["volume"],
            dollar_volume=item["dollar_volume"],
            spread_pct=item["spread_pct"],
            vwap_relation=vwap_relation,
            vwap_distance_pct=vwap_distance,
            supertrend_bullish=st_bull,
            supertrend_flip=st_flip,
            ema65_relation=(
                "above" if not math.isnan(ema65) and price >= ema65 else "below"
            ),
            ema65_distance_pct=proximity_pct(price, ema65),
            volume_acceleration=volume_acceleration(session),
            green_volume_ratio=green_volume_ratio(session),
            rvol_proxy=rvol_proxy,
            higher_lows=higher_lows(session),
            near_hod=(day_high - price) / max(day_high, 0.0001) * 100 <= 3,
            catalyst_score=catalyst_score,
            headline=headline,
            news_age_hours=age_hours,
            risk_flags=flags,
            timeframe_confirmations=tf_count,
            discovery_reasons=discovery_reasons.get(symbol, []),
        )
        decision = score(evidence)
        output.append(
            {
                **evidence.__dict__,
                **decision.__dict__,
                "timeframes": tf_details,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "last_bar_timestamp": last_bar_time.isoformat(),
                "bar_age_seconds": round(bar_age_seconds, 1),
                "vwap_value": round(vw, 6),
                "vwap_reclaim_age_bars": reclaim_age_bars,
                "supertrend_value": round(st_value, 6),
                "supertrend_distance_pct": (
                    round(abs(price - st_value) / price * 100, 3)
                    if price and st_value
                    else 999.0
                ),
                "vwap_bar_timeframe_source": "Alpaca 1Min current-session bars (same bars as primary SuperTrend)",
                "expected_volume_by_time": round(vpi.expected_volume),
                "volume_pace_ratio": round(vpi.volume_pace_ratio, 2),
                "five_minute_volume": round(vpi.recent_5m_volume),
                "expected_five_minute_volume": round(vpi.expected_5m_volume),
                "acceleration_ratio": round(vpi.acceleration_ratio, 2),
                "volume_pace_passed": vpi.passed,
                "volume_pace_status": vpi.status,
                "volume_pace_reason": vpi.reason,
                "ema5_relation": "above" if price >= ema5_value else "below",
                "above_ema5_and_ema60_65": bool(price >= ema5_value and price >= ema65),
                "price_change_10m_pct": round(price_change_10m_pct, 2),
                "volume_above_preceding_15m_pace": bool(
                    prior_15_pace and recent_pace >= prior_15_pace * 1.5
                ),
                "broke_previous_15m_high_with_volume": broke_15m_high,
                "vwap_reclaimed_last_10m": reclaimed_10m,
                "supertrend_flipped_last_10m": bool(st_flip),
                "crossed_vwap_and_supertrend": bool(reclaimed_10m and st_bull),
                "relative_strength_benchmark": benchmark_symbol,
                **rs_metrics,
                **surge_metrics,
                **alignment,
            }
        )
    return apply_attention_ranking(output)
