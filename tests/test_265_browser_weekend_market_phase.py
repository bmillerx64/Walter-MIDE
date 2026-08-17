from pathlib import Path


def test_browser_live_clock_respects_eastern_weekends():
    app_source = Path("app.py").read_text()

    assert "timeZone: 'America/New_York', weekday: 'short'" in app_source
    assert "const isWeekend = weekday === 'Sat' || weekday === 'Sun';" in app_source
    assert "if (!isWeekend && clockMinutes >= 240 && clockMinutes < 570) phase = 'Pre-Market';" in app_source
    assert "else if (!isWeekend && clockMinutes >= 570 && clockMinutes < 960) phase = 'Live Market';" in app_source
    assert "else if (!isWeekend && clockMinutes >= 960 && clockMinutes < 1200) phase = 'After-Hours';" in app_source
