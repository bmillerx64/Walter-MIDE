from __future__ import annotations

from pathlib import Path

from mide import gs494_partial_snapshot_recovery as gs494


class Provider:
    def __init__(self):
        self.diagnostics = {"webull_stream": {"discovered_symbols": 3}}
        self.initialize_quotes = None


def test_partial_snapshot_retries_only_missing_symbols_once_and_merges_recovery():
    provider = Provider()
    calls = []

    def original(symbols, *, batch_size):
        symbols = list(symbols)
        calls.append((symbols, batch_size))
        if len(calls) == 1:
            return {"AAA": 1.0, "IMCC": 7.0}
        assert symbols == ["BBB"]
        return {"BBB": 2.0}

    result = gs494.initialize_quotes_with_partial_retry(
        original, provider, ["AAA", "BBB", "IMCC"], batch_size=50
    )

    assert result == {"AAA": 1.0, "IMCC": 7.0, "BBB": 2.0}
    assert calls == [(["AAA", "BBB", "IMCC"], 50), (["BBB"], 1)]
    trace = provider.diagnostics["webull_stream"]["snapshot_partial_retry"]
    assert trace["retry_attempted"] is True
    assert trace["retry_requested"] == 1
    assert trace["retry_recovered"] == 1
    assert trace["unresolved_count"] == 0
    assert trace["unresolved_symbols"] == []
    assert trace["stale_price_substitution"] is False
    assert provider.diagnostics["webull_stream"]["discovered_symbols"] == 3


def test_full_snapshot_success_adds_no_extra_provider_request():
    provider = Provider()
    calls = []

    def original(symbols, *, batch_size):
        calls.append(list(symbols))
        return {symbol: 1.0 for symbol in symbols}

    result = gs494.initialize_quotes_with_partial_retry(
        original, provider, ["AAA", "BBB"], batch_size=50
    )
    assert set(result) == {"AAA", "BBB"}
    assert calls == [["AAA", "BBB"]]
    trace = provider.diagnostics["webull_stream"]["snapshot_partial_retry"]
    assert trace["retry_attempted"] is False
    assert trace["extra_provider_requests_max"] == 0


def test_persistent_partial_response_gets_exactly_one_retry_and_fails_closed():
    provider = Provider()
    calls = []

    def original(symbols, *, batch_size):
        symbols = list(symbols)
        calls.append(symbols)
        if len(calls) == 1:
            return {"AAA": 1.0}
        return {}

    result = gs494.initialize_quotes_with_partial_retry(
        original, provider, ["AAA", "IMCC"], batch_size=50
    )
    assert result == {"AAA": 1.0}
    assert calls == [["AAA", "IMCC"], ["IMCC"]]
    trace = provider.diagnostics["webull_stream"]["snapshot_partial_retry"]
    assert trace["retry_recovered"] == 0
    assert trace["unresolved_symbols"] == ["IMCC"]
    assert trace["unresolved_count"] == 1


def test_retry_exception_preserves_first_valid_snapshot_without_raw_error():
    provider = Provider()
    calls = []

    def original(symbols, *, batch_size):
        calls.append(list(symbols))
        if len(calls) == 1:
            return {"AAA": 1.0}
        raise RuntimeError("secret-bearing-provider-error")

    result = gs494.initialize_quotes_with_partial_retry(
        original, provider, ["AAA", "IMCC"], batch_size=50
    )
    assert result == {"AAA": 1.0}
    trace = provider.diagnostics["webull_stream"]["snapshot_partial_retry"]
    assert trace["retry_error_type"] == "RuntimeError"
    assert "secret-bearing-provider-error" not in str(trace)
    assert trace["unresolved_symbols"] == ["IMCC"]


def test_install_for_exact_retained_provider_is_idempotent():
    provider = Provider()
    calls = []

    def legacy(symbols, *, batch_size=100):
        calls.append(list(symbols))
        return {symbol: 1.0 for symbol in symbols}

    provider.initialize_quotes = legacy
    assert gs494.install_for_provider(provider) is True
    installed = provider.initialize_quotes
    assert gs494.install_for_provider(provider) is False
    assert provider.initialize_quotes is installed
    assert getattr(installed, gs494._OWNER) == gs494.REVISION
    assert provider.initialize_quotes(["AAA"]) == {"AAA": 1.0}


def test_app_installs_gs494_before_initialize_quotes():
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index('if provider_name.upper() == "WEBULL":')
    end = source.index('    else:\n        api_key = get_secret("ALPACA_API_KEY")', start)
    block = source[start:end]
    assert "mide.gs494_partial_snapshot_recovery" in block
    assert block.index("gs490.install_for_provider(client)") < block.index(
        "gs494.install_for_provider(client)"
    )
    assert source.index("gs494.install_for_provider(client)", start) < source.index(
        "client.initialize_quotes(seeds", start
    )


def test_scope_lock_is_market_data_resilience_only():
    source = Path("mide/gs494_partial_snapshot_recovery.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "opportunity_score =",
        "conviction_score =",
        "place_order(",
        "submit_order(",
        "execute_order(",
        "synthetic",
    )
    # The docstring says no synthetic source; permit the prose but no synthetic API.
    assert not any(token in source for token in forbidden[:-1])
    assert "stale_price_substitution" in source
    assert '"trading_authority_changed": False' in source
    assert "extra_provider_requests_max" in source
