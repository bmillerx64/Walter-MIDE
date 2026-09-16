from pathlib import Path

import pandas as pd

from mide import gs464_session_aware_vwap_parity as gs464


def _frame(times, prices, volumes):
    index = pd.DatetimeIndex(times, tz="America/New_York")
    return pd.DataFrame(
        {
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "volume": volumes,
        },
        index=index,
    )


def test_premarket_keeps_0400_extended_anchor():
    frame = _frame(
        ["2026-09-16 08:00", "2026-09-16 09:00", "2026-09-16 09:29"],
        [0.20, 0.18, 0.16],
        [1_000_000, 1_000_000, 1_000_000],
    )
    context = gs464.session_aware_primary_vwap_context(frame)

    assert context["anchor_mode"] == gs464.PREMARKET_POLICY
    assert context["anchor_time"].hour == 4
    assert context["value"] == context["premarket_value"]
    assert context["value"] == context["extended_value"]
    assert context["rth_value"] is None


def test_regular_session_resets_primary_vwap_to_0930():
    frame = _frame(
        [
            "2026-09-16 08:00",
            "2026-09-16 09:00",
            "2026-09-16 09:29",
            "2026-09-16 09:30",
            "2026-09-16 09:31",
        ],
        [0.20, 0.18, 0.16, 0.14, 0.15],
        [5_000_000, 5_000_000, 5_000_000, 1_000_000, 1_000_000],
    )
    context = gs464.session_aware_primary_vwap_context(frame)

    assert context["anchor_mode"] == gs464.RTH_POLICY
    assert context["anchor_time"].hour == 9
    assert context["anchor_time"].minute == 30
    assert context["value"] == context["rth_value"]
    assert context["extended_value"] > context["value"]


def test_snyr_like_case_changes_false_below_vwap_to_chart_matched_above_vwap():
    # Mirrors the 2026-09-16 live failure: heavy/high premarket prints kept GS391's
    # all-day VWAP near 0.186 while Webull's post-open chart reset near 0.143.
    frame = _frame(
        [
            "2026-09-16 05:45",
            "2026-09-16 06:00",
            "2026-09-16 08:30",
            "2026-09-16 09:29",
            "2026-09-16 09:30",
            "2026-09-16 09:31",
            "2026-09-16 09:32",
            "2026-09-16 09:33",
        ],
        [0.245, 0.220, 0.190, 0.170, 0.140, 0.142, 0.145, 0.1554],
        [8_000_000, 8_000_000, 8_000_000, 8_000_000, 2_000_000, 2_000_000, 2_000_000, 2_000_000],
    )
    context = gs464.session_aware_primary_vwap_context(frame)
    price = 0.1554

    assert context["anchor_mode"] == gs464.RTH_POLICY
    assert context["value"] == context["rth_value"]
    assert price > context["value"]
    assert price < context["extended_value"]
    assert context["extended_value"] - context["value"] > 0.03


def test_session_policy_retains_both_diagnostic_vwaps_after_open():
    frame = _frame(
        ["2026-09-16 08:00", "2026-09-16 09:29", "2026-09-16 09:30", "2026-09-16 09:31"],
        [1.00, 1.00, 0.80, 0.82],
        [1_000_000, 1_000_000, 100, 100],
    )
    context = gs464.session_aware_primary_vwap_context(frame)

    assert context["session_policy"] == gs464.SESSION_POLICY
    assert context["premarket_value"] is not None
    assert context["rth_value"] is not None
    assert context["extended_value"] is not None
    assert context["value"] == context["rth_value"]


def test_gs464_installs_at_final_late_boundary_before_presentation_layers():
    source = Path("mide/gs414_final_enriched_opportunity_order.py").read_text(encoding="utf-8")
    assert "gs464_session_aware_vwap_parity" in source
    install_body = source.split('def install() -> None:', 1)[1]
    assert install_body.index("_install_gs464()") < install_body.index("_install_gs462()")
    assert install_body.index("_install_gs462()") < install_body.index("_install_gs463()")


def test_gs464_scope_lock_adds_no_provider_or_execution_path():
    source = Path("mide/gs464_session_aware_vwap_parity.py").read_text(encoding="utf-8")
    forbidden = (
        ".get_bars(",
        ".history(",
        "request_scan(",
        "place_order(",
        "submit_order(",
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "PARTICIPATION_MIN_",
    )
    for token in forbidden:
        assert token not in source
    assert '"additional_market_data_requests": 0' in source
