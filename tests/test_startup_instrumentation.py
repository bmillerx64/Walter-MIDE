import logging

from mide import startup


def test_startup_log_has_timestamp_elapsed_time_and_component(caplog):
    with caplog.at_level(logging.INFO, logger="walter.startup"):
        startup.log_startup("loading universe")

    assert "startup +" in caplog.text
    assert "component=loading universe starting" in caplog.text


def test_startup_step_logs_completion(caplog):
    with caplog.at_level(logging.INFO, logger="walter.startup"):
        with startup.startup_step("rendering Streamlit UI"):
            pass

    assert "component=rendering Streamlit UI starting" in caplog.text
    assert "component=rendering Streamlit UI complete in" in caplog.text


def test_webull_network_timeout_is_within_startup_budget():
    from mide.webull_live import NETWORK_TIMEOUT_SECONDS

    assert 5 <= NETWORK_TIMEOUT_SECONDS <= 10


def test_startup_checkpoint_logs_requested_label(caplog):
    with caplog.at_level(logging.INFO, logger="walter.startup"):
        startup.startup_checkpoint("START")

    assert "component=START checkpoint" in caplog.text


def test_full_traceback_logging_installs_excepthook():
    import sys

    startup.configure_full_traceback_logging()

    assert sys.excepthook.__name__ == "log_unhandled_exception"
