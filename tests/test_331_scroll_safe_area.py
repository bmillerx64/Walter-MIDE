from mide import gs331_scroll_safe_area as scroll_safe
from mide import ui


def test_scroll_safe_area_is_installed():
    assert getattr(ui.inject_css, "_gs331_scroll_safe_area", False)
    assert callable(ui.inject_css._gs331_original)


def test_safe_top_css_overrides_legacy_main_padding_and_covers_sidebar():
    css = scroll_safe.SAFE_TOP_CSS
    assert ".block-container" in css
    assert '[data-testid="stMainBlockContainer"]' in css
    assert '[data-testid="stSidebarUserContent"]' in css
    assert "padding-top: 3.75rem !important" in css


def test_safe_area_does_not_use_hidden_dom_or_scroll_javascript():
    css = scroll_safe.SAFE_TOP_CSS.lower()
    assert "display:none" not in css
    assert "display: none" not in css
    assert "scrollto" not in css
    assert "position:fixed" not in css
    assert "position: fixed" not in css
