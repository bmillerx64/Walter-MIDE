import inspect

from mide import discovery


def test_installed_discovery_signature_exposes_universe_verification():
    """The app must be able to detect and pass the live universe verifier.

    GS315 historically wrapped build_seed_symbols with *args/**kwargs, which hid
    the keyword-only universe_verification parameter from inspect.signature().
    app.py therefore treated the installed function like a legacy callable and
    skipped provenance collection entirely, producing a false Universe
    verification: FAIL even while the live Webull universe was healthy.
    """
    parameters = inspect.signature(discovery.build_seed_symbols).parameters
    assert "universe_verification" in parameters
    assert parameters["universe_verification"].kind is inspect.Parameter.KEYWORD_ONLY
