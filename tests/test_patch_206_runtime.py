import pandas as pd

from mide.arrow_diagnostics import _arrow_safe_frame
from mide.webull_live import LiveWebullProvider


def test_webull_bars_frame_parses_epoch_milliseconds_without_dateutil_fallback():
    rows = [
        {"t": "1786390200000", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10},
        {"t": "1786390260000", "o": 1.5, "h": 2.1, "l": 1.4, "c": 2, "v": 20},
    ]

    frame = LiveWebullProvider.bars_frame(rows)

    assert isinstance(frame.index, pd.DatetimeIndex)
    assert str(frame.index.tz) == "UTC"
    assert frame.index[0] == pd.Timestamp(1786390200000, unit="ms", tz="UTC")
    assert list(frame["close"]) == [1.5, 2]


def test_webull_bars_frame_accepts_mixed_iso_8601_timestamps():
    rows = [
        {"t": "2026-08-10T14:30:00Z", "c": 1, "v": 10},
        {"t": "2026-08-10 14:31:00+00:00", "c": 2, "v": 20},
    ]

    frame = LiveWebullProvider.bars_frame(rows)

    assert len(frame) == 2
    assert frame.index.is_monotonic_increasing
    assert str(frame.index.tz) == "UTC"


def test_arrow_safe_frame_serializes_only_violating_nested_diagnostic_column():
    rows = [
        {"stage": "Participation", "elapsed_ms": 10.5, "rejection_histogram": []},
        {
            "stage": "Participation",
            "elapsed_ms": 12.5,
            "rejection_histogram": [
                {
                    "reason": "Missing or insufficient intraday bars",
                    "failed_metrics": [
                        {"threshold": "provider/timeframe minimum", "measured": None}
                    ],
                }
            ],
        },
    ]

    safe = _arrow_safe_frame(rows, {"rejection_histogram"})

    assert list(safe["stage"]) == ["Participation", "Participation"]
    assert list(safe["elapsed_ms"]) == [10.5, 12.5]
    assert safe["rejection_histogram"].map(type).eq(str).all()
    assert "provider/timeframe minimum" in safe["rejection_histogram"].iloc[1]
