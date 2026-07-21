from __future__ import annotations
from datetime import datetime, timedelta, timezone
import math
import re
import pandas as pd
import numpy as np

from .indicators import (
    ema, session_vwap, supertrend, resample_ohlcv, volume_acceleration,
    green_volume_ratio, higher_lows, proximity_pct
)
from .scoring import Evidence, score

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

def build_seed_symbols(client, settings, news_items):
    symbols, why = set(), {}
    for item in client.movers(50):
        symbol = item.get("symbol")
        if is_valid_us_symbol(symbol):
            symbols.add(symbol); why.setdefault(symbol, []).append("market mover")
    for item in client.most_actives(100):
        symbol = item.get("symbol")
        if is_valid_us_symbol(symbol):
            symbols.add(symbol); why.setdefault(symbol, []).append("most active")
    for item in news_items:
        for symbol in item.get("symbols", []) or []:
            if is_valid_us_symbol(symbol):
                symbols.add(symbol); why.setdefault(symbol, []).append("recent news")

    # Broad low-priced universe: snapshot batches are subsequently filtered.
    # Capped per refresh to remain practical on the first cloud version.
    try:
        eligible_assets = [
            x["symbol"] for x in client.assets()
            if x.get("tradable") and x.get("status") == "active"
        ]

        client.warnings.append(
            f"Loaded {len(eligible_assets)} tradable assets"
        )

            # Stable rotation by minute means the whole universe is revisited over time.
            minute_bucket = int(datetime.now(timezone.utc).timestamp() // 60)
            start = (minute_bucket * settings.max_seed_symbols) % max(1, len(eligible_assets))
            rotated = eligible_assets[start:start + settings.max_seed_symbols]
            if len(rotated) < settings.max_seed_symbols:
                rotated += eligible_assets[:settings.max_seed_symbols - len(rotated)]
            for symbol in rotated:
                if is_valid_us_symbol(symbol):
                    symbols.add(symbol); why.setdefault(symbol, []).append("broad market sweep")
    except Exception as exc:
    client.warnings.append(f"Broad market sweep unavailable: {exc}")
    return list(symbols), why

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
        spread = ((ask - bid) / ((ask + bid) / 2) * 100) if bid and ask and ask >= bid else 99
        dollar = price * volume
        if not settings.min_price <= price <= settings.max_price:
            continue
        # Candidate if meaningful gain OR meaningful participation.
        if pct < settings.min_pct_change and volume < settings.min_day_volume:
            continue
        if dollar < 50_000:
            continue
        selected.append({
            "symbol": symbol, "price": price, "pct_change": pct,
            "volume": volume, "dollar_volume": dollar, "spread_pct": spread,
            "day_high": float(daily.get("h") or price),
            "prev_volume": float(previous.get("v") or 0),
        })
    return sorted(selected, key=lambda x: (x["pct_change"], x["dollar_volume"]), reverse=True)

def _timeframe_confirmation(frame):
    confirmations = 0
    details = {}
    for label, rule in [("1m","1min"), ("3m","3min"), ("5m","5min"), ("10m","10min")]:
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
        volume_abs = min(100.0, math.log10(max(float(r.get("volume", 0)), 1) / 100_000 + 1) / math.log10(1001) * 100)
        dollar_abs = min(100.0, math.log10(max(float(r.get("dollar_volume", 0)), 1) / 100_000 + 1) / math.log10(2501) * 100)
        change_abs = min(100.0, max(0.0, float(r.get("pct_change", 0))) / 50 * 100)
        rvol_abs = min(100.0, max(0.0, float(r.get("rvol_proxy", 0))) / 10 * 100)
        absolute = volume_abs * 0.34 + dollar_abs * 0.28 + change_abs * 0.22 + rvol_abs * 0.16
        dominance = cohort * 0.55 + absolute * 0.45
        attention = (
            float(r.get("opportunity_score", 0)) * 0.42
            + float(r.get("participation_score", 0)) * 0.34
            + dominance * 0.24
        )
        r["market_dominance_score"] = round(dominance, 1)
        r["attention_score"] = round(min(100.0, attention), 1)

        if r["status"] != "PASS":
            if r["attention_score"] >= 82 and r["participation_score"] >= 60 and dominance >= 78:
                r["status"] = "EXCEPTIONAL"
                r["participation_tier"] = "DOMINANT" if dominance >= 92 else "EXCEPTIONAL"
            elif r["attention_score"] >= 72 and r["status"] in {"MONITOR", "WATCH NOW"}:
                r["status"] = "WATCH NOW"
        if dominance >= 85:
            r["reasons"] = [f"Market dominance {dominance:.0f}/100"] + r.get("reasons", [])
    return sorted(
        records,
        key=lambda x: (
            x.get("attention_score", 0),
            x.get("market_dominance_score", 0),
            x.get("participation_score", 0),
        ),
        reverse=True,
    )


def analyze_candidates(client, candidates, news_index, discovery_reasons):
    if not candidates:
        return []
    start = datetime.now(timezone.utc) - timedelta(days=2)
    symbols = [x["symbol"] for x in candidates[:80] if is_valid_us_symbol(x.get("symbol"))]
    raw = client.bars(symbols, start=start, timeframe="1Min", limit=10_000)
    output = []

    for item in candidates[:80]:
        symbol = item["symbol"]
        frame = client.bars_frame(raw.get(symbol, []))
        if len(frame) < 20:
            continue
        # Current session approximation: use the latest calendar date present.
        latest_date = frame.index[-1].date()
        session = frame[frame.index.date == latest_date].copy()
        if len(session) < 12:
            session = frame.tail(150).copy()

        price = float(session["close"].iloc[-1])
        vw = float(session_vwap(session).iloc[-1])
        ema65 = float(ema(session["close"], 65).iloc[-1]) if len(session) >= 65 else float("nan")
        st_line, st_trend = supertrend(session, 10, 3)
        st_bull = bool(st_trend.iloc[-1]) if len(st_trend) else False
        st_flip = bool(len(st_trend) >= 2 and st_trend.iloc[-1] and not st_trend.iloc[-2])
        tf_count, tf_details = _timeframe_confirmation(session)

        news = news_index.get(symbol)
        headline = news["headline"] if news else ""
        age_hours = None
        catalyst_score = 0
        flags = []
        if news:
            age_hours = (datetime.now(timezone.utc) - news["created_at"]).total_seconds() / 3600
            catalyst_score = news["catalyst_score"]
            flags = news["flags"]

        day_high = max(item["day_high"], float(session["high"].max()))
        previous_volume = item["prev_volume"]
        elapsed_fraction = max(0.08, min(1.0, len(session) / 390))
        expected_so_far = previous_volume * elapsed_fraction
        rvol_proxy = item["volume"] / expected_so_far if expected_so_far > 0 else 1.0

        vwap_distance = proximity_pct(price, vw)
        vwap_relation = "testing" if vwap_distance <= 1.0 else ("above" if price > vw else "below")
        last_bar_time = session.index[-1]
        bar_age_seconds = max(0.0, (datetime.now(timezone.utc) - last_bar_time.to_pydatetime()).total_seconds())

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
            ema65_relation="above" if not math.isnan(ema65) and price >= ema65 else "below",
            ema65_distance_pct=proximity_pct(price, ema65),
            volume_acceleration=volume_acceleration(session),
            green_volume_ratio=green_volume_ratio(session),
            rvol_proxy=rvol_proxy,
            higher_lows=higher_lows(session),
            near_hod=(day_high - price) / max(day_high, .0001) * 100 <= 3,
            catalyst_score=catalyst_score,
            headline=headline,
            news_age_hours=age_hours,
            risk_flags=flags,
            timeframe_confirmations=tf_count,
            discovery_reasons=discovery_reasons.get(symbol, []),
        )
        decision = score(evidence)
        output.append({
            **evidence.__dict__,
            **decision.__dict__,
            "timeframes": tf_details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "last_bar_timestamp": last_bar_time.isoformat(),
            "bar_age_seconds": round(bar_age_seconds, 1),
            "vwap_value": round(vw, 6),
        })
    return apply_attention_ranking(output)
