from mide.webull_native_radar import fetch_native_radar

class ErrorResponse:
    status_code=403
    def json(self): return {"code":"INSUFFICIENT_PERMISSION"}
class Screener:
    def get_gainers_losers(self,**_kwargs): return ErrorResponse()
    def get_most_active(self,**_kwargs): return ErrorResponse()

def test_native_radar_marks_http_permission_failures():
    report=fetch_native_radar(Screener())
    assert report["all_feeds_available"] is False
    for key in ("day_gainers","absolute_volume"):
        assert report["feeds"][key]["status"]=="FAIL"
        assert "HTTP 403" in report["feeds"][key]["error"]
    for key in ("five_minute_movers","relative_volume"):
        assert report["feeds"][key]["status"]=="NOT_SCANNED"
