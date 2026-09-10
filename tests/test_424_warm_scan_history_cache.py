from __future__ import annotations

from datetime import datetime, timedelta, timezone

from mide import gs424_warm_scan_history_cache as gs424


ANCHOR = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)  # 04:00 ET


def _row(minute: int, price: float = 1.0) -> dict:
    stamp = datetime(2026, 9, 10, 14, minute, tzinfo=timezone.utc)
    return {"t": stamp.isoformat(), "o": price, "h": price, "l": price,
            "c": price, "v": 1000 + minute}


class _Provider:
    def __init__(self):
        self.diagnostics = {}


def _stage6_kwargs(start=ANCHOR, reason="stage6_current_session"):
    return {
        "start": start,
        "timeframe": "1Min",
        "limit": 960,
        "force_batch": True,
        "history_reason": reason,
    }


def test_first_scan_seeds_full_history_then_warm_scan_requests_only_delta():
    provider = _Provider()
    calls = []
    first = [_row(0), _row(1), _row(2)]
    warm = [_row(0), _row(1), _row(2), _row(3)]

    def original(_provider, symbols, **kwargs):
        calls.append((list(symbols), kwargs["start"]))
        rows = first if kwargs["start"] == ANCHOR else warm[1:]
        return {symbol: list(rows) for symbol in symbols}

    seeded = gs424.cached_current_session_bars(
        provider, original, ["AAA"], **_stage6_kwargs()
    )
    refreshed = gs424.cached_current_session_bars(
        provider, original, ["AAA"], **_stage6_kwargs()
    )

    assert len(seeded["AAA"]) == 3
    assert len(refreshed["AAA"]) == 4
    assert calls[0] == (["AAA"], ANCHOR)
    assert calls[1][0] == ["AAA"]
    assert calls[1][1] == datetime(2026, 9, 10, 13, 59, tzinfo=timezone.utc)
    assert provider.diagnostics["gs424_warm_scan_history_cache"]["cache_hits"] == 1
    assert provider.diagnostics["gs424_warm_scan_history_cache"]["full_seed_symbols"] == 0


def test_new_symbol_gets_full_seed_while_existing_symbol_uses_incremental_overlap():
    provider = _Provider()
    calls = []
    aaa_seed = [_row(0), _row(1), _row(2)]
    aaa_delta = [_row(1), _row(2), _row(3)]
    bbb_seed = [_row(0, 2.0), _row(1, 2.0), _row(2, 2.0)]

    def original(_provider, symbols, **kwargs):
        calls.append((list(symbols), kwargs["start"]))
        out = {}
        for symbol in symbols:
            if symbol == "AAA":
                out[symbol] = list(aaa_seed if kwargs["start"] == ANCHOR else aaa_delta)
            elif symbol == "BBB":
                out[symbol] = list(bbb_seed)
        return out

    gs424.cached_current_session_bars(
        provider, original, ["AAA"], **_stage6_kwargs()
    )
    result = gs424.cached_current_session_bars(
        provider, original, ["AAA", "BBB"], **_stage6_kwargs()
    )

    assert calls[-2] == (["BBB"], ANCHOR)
    assert calls[-1][0] == ["AAA"]
    assert calls[-1][1] > ANCHOR
    assert len(result["AAA"]) == 4
    assert len(result["BBB"]) == 3


def test_overlap_merge_replaces_duplicate_timestamp_instead_of_double_counting_volume():
    provider = _Provider()
    base = [_row(0), _row(1), _row(2)]
    corrected = dict(_row(2))
    corrected["v"] = 9999
    delta = [corrected, _row(3)]
    call_count = 0

    def original(_provider, symbols, **kwargs):
        nonlocal call_count
        call_count += 1
        rows = base if call_count == 1 else delta
        return {symbol: list(rows) for symbol in symbols}

    gs424.cached_current_session_bars(
        provider, original, ["AAA"], **_stage6_kwargs()
    )
    result = gs424.cached_current_session_bars(
        provider, original, ["AAA"], **_stage6_kwargs()
    )

    assert len(result["AAA"]) == 4
    matching = [row for row in result["AAA"] if row["t"] == corrected["t"]]
    assert len(matching) == 1
    assert matching[0]["v"] == 9999


def test_new_session_anchor_invalidates_previous_day_cache():
    provider = _Provider()
    calls = []
    next_anchor = ANCHOR + timedelta(days=1)
    day1 = [_row(0), _row(1)]
    day2_stamp = datetime(2026, 9, 11, 14, 0, tzinfo=timezone.utc)
    day2 = [{"t": day2_stamp.isoformat(), "o": 3, "h": 3, "l": 3, "c": 3, "v": 2000}]

    def original(_provider, symbols, **kwargs):
        calls.append((list(symbols), kwargs["start"]))
        rows = day2 if kwargs["start"] == next_anchor else day1
        return {symbol: list(rows) for symbol in symbols}

    gs424.cached_current_session_bars(
        provider, original, ["AAA"], **_stage6_kwargs()
    )
    result = gs424.cached_current_session_bars(
        provider, original, ["AAA"], **_stage6_kwargs(start=next_anchor)
    )

    assert calls[-1] == (["AAA"], next_anchor)
    assert result["AAA"] == day2
    assert provider.diagnostics["gs424_warm_scan_history_cache"]["cache_hits"] == 0


def test_historical_profile_requests_are_not_cached_or_rewritten():
    provider = _Provider()
    calls = []

    def original(_provider, symbols, **kwargs):
        calls.append((list(symbols), kwargs["start"], kwargs["history_reason"]))
        return {symbol: [_row(0)] for symbol in symbols}

    kwargs = _stage6_kwargs(reason="stage6_historical_profile")
    gs424.cached_current_session_bars(provider, original, ["AAA"], **kwargs)
    gs424.cached_current_session_bars(provider, original, ["AAA"], **kwargs)

    assert calls == [
        (["AAA"], ANCHOR, "stage6_historical_profile"),
        (["AAA"], ANCHOR, "stage6_historical_profile"),
    ]
    assert not hasattr(provider, "_walter_gs424_history_cache")
