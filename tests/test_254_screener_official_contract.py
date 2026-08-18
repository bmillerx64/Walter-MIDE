from mide.webull_native_radar import fetch_native_radar

class Response:
    status_code=200
    def __init__(self,symbol): self.symbol=symbol
    def json(self): return {"data":[{"symbol":self.symbol,"change_ratio":10.0}]}
class Screener:
    def __init__(self): self.calls=[]
    def get_gainers_losers(self,**kwargs): self.calls.append(("gainers",kwargs)); return Response(kwargs["rank_type"])
    def get_most_active(self,**kwargs): self.calls.append(("active",kwargs)); return Response(kwargs["rank_type"])

def test_native_radar_uses_official_rank_contract():
    screener=Screener(); report=fetch_native_radar(screener)
    assert report["all_feeds_available"] is True
    calls={kwargs["rank_type"]:kwargs for _kind,kwargs in screener.calls}
    # Three-feed contract: DAY_1 (day gainers), VOLUME (absolute volume), RELATIVE_VOLUME_10D (rvol)
    assert set(calls)=={"DAY_1","VOLUME","RELATIVE_VOLUME_10D"}
    assert calls["DAY_1"]["sort_by"]=="CHANGE_RATIO"
    assert calls["VOLUME"]["sort_by"]=="VOLUME"
    assert calls["RELATIVE_VOLUME_10D"]["sort_by"]=="RELATIVE_VOLUME_10D"
    assert all(kwargs["page_size"]==20 for _kind,kwargs in screener.calls)
