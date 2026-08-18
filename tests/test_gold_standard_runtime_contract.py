"""Gold Standard invariants for Walter's production runtime wiring."""

from pathlib import Path


def test_production_python_matches_ci_python():
    runtime = Path("runtime.txt").read_text(encoding="utf-8").strip()
    workflow = Path(".github/workflows/pr-tests.yml").read_text(encoding="utf-8")
    assert runtime == "python-3.13"
    assert "python-version: '3.13'" in workflow


def test_prefilter_patch_is_idempotent_and_preserves_or_semantics():
    from mide import flight_recorder
    from mide.config import Settings
    from mide.prefilter_compat import install

    install()
    patched = flight_recorder.prefilter_decision
    install()
    assert flight_recorder.prefilter_decision is patched

    settings = Settings()
    mover = {
        "latestTrade": {"p": 1.20},
        "dailyBar": {"v": 1_000},
        "prevDailyBar": {"c": 1.00},
    }
    participant = {
        "latestTrade": {"p": 1.01},
        "dailyBar": {"v": 250_000},
        "prevDailyBar": {"c": 1.00},
    }
    quiet = {
        "latestTrade": {"p": 1.01},
        "dailyBar": {"v": 1_000},
        "prevDailyBar": {"c": 1.00},
    }
    too_expensive = {
        "latestTrade": {"p": 50.01},
        "dailyBar": {"v": 1_000_000},
        "prevDailyBar": {"c": 40.00},
    }

    assert patched("MOVE", mover, settings)["passed"] is True
    assert patched("VOL", participant, settings)["passed"] is True
    assert patched("QUIET", quiet, settings)["passed"] is False
    assert patched("HIGH", too_expensive, settings)["passed"] is False


def test_entry_state_is_observer_only_by_contract():
    source = Path("mide/entry_state.py").read_text(encoding="utf-8")
    assert "does not discover or qualify symbols" in source
    assert "entry_actionable" in source
