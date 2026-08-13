from types import SimpleNamespace

import mide.prefilter_compat as compat


SETTINGS = SimpleNamespace(
    min_price=0.05,
    max_price=5.0,
    min_pct_change=3.0,
    min_day_volume=100_000,
)


def test_closed_session_zero_uses_completed_session_volume(monkeypatch):
    import mide.time_service as clock
    monkeypatch.setattr(clock, "market_phase_at", lambda: "Market Closed")
    volume, fallback = compat._closed_session_volume(0.0, {"v": 250_000})
    assert volume == 250_000
    assert fallback is True


def test_live_market_real_zero_remains_zero(monkeypatch):
    import mide.time_service as clock
    monkeypatch.setattr(clock, "market_phase_at", lambda: "Live Market")
    volume, fallback = compat._closed_session_volume(0.0, {"v": 250_000})
    assert volume == 0
    assert fallback is False


def test_after_hours_real_zero_remains_zero(monkeypatch):
    import mide.time_service as clock
    monkeypatch.setattr(clock, "market_phase_at", lambda: "After-Hours")
    volume, fallback = compat._closed_session_volume(0.0, {"v": 250_000})
    assert volume == 0
    assert fallback is False


def test_closed_session_without_previous_volume_stays_zero(monkeypatch):
    import mide.time_service as clock
    monkeypatch.setattr(clock, "market_phase_at", lambda: "Market Closed")
    volume, fallback = compat._closed_session_volume(0.0, {})
    assert volume == 0
    assert fallback is False


def test_nonzero_current_volume_always_wins(monkeypatch):
    import mide.time_service as clock
    monkeypatch.setattr(clock, "market_phase_at", lambda: "Market Closed")
    volume, fallback = compat._closed_session_volume(123_456.0, {"v": 250_000})
    assert volume == 123_456
    assert fallback is False
