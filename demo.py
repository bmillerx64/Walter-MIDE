from datetime import datetime, timezone
from .discovery import apply_attention_ranking


def demo_records():
    now = datetime.now(timezone.utc).isoformat()
    records = [
        {
            "symbol":"PMII","price":0.431,"pct_change":38.4,"volume":32700000,
            "dollar_volume":14093700,"spread_pct":0.8,"vwap_relation":"above",
            "vwap_distance_pct":0.4,"supertrend_bullish":True,"supertrend_flip":True,
            "ema65_relation":"above","ema65_distance_pct":0.7,"volume_acceleration":2.8,
            "green_volume_ratio":2.4,"rvol_proxy":6.8,"higher_lows":True,"near_hod":True,
            "catalyst_score":12,"headline":"Company announces strategic purchase order",
            "news_age_hours":1.2,"risk_flags":["purchase order"],"timeframe_confirmations":4,
            "discovery_reasons":["market mover","most active"],"opportunity_score":93.2,
            "conviction_score":91.0,"participation_score":96.0,"participation_tier":"DOMINANT","status":"ALERT",
            "reasons":["Above VWAP","SuperTrend bullish","Fresh SuperTrend flip","Above 65 EMA",
                       "Volume accelerating 2.8×","RVOL proxy 6.8×","Fresh corporate news"],
            "cautions":[],"previous_score":72.0,"velocity":21.2,"status_changed":True,
            "timestamp":now,"timeframes":{"1m":{"above_vwap":True,"supertrend":True},
            "3m":{"above_vwap":True,"supertrend":True},"5m":{"above_vwap":True,"supertrend":True},
            "10m":{"above_vwap":True,"supertrend":True}}
        },
        {
            "symbol":"NXXT","price":0.3498,"pct_change":24.8,"volume":32980000,
            "dollar_volume":11536404,"spread_pct":1.2,"vwap_relation":"below",
            "vwap_distance_pct":0.9,"supertrend_bullish":False,"supertrend_flip":False,
            "ema65_relation":"above","ema65_distance_pct":0.5,"volume_acceleration":1.9,
            "green_volume_ratio":1.7,"rvol_proxy":5.4,"higher_lows":True,"near_hod":False,
            "catalyst_score":0,"headline":"","news_age_hours":None,"risk_flags":[],
            "timeframe_confirmations":2,"discovery_reasons":["market mover","most active"],
            "opportunity_score":72.8,"conviction_score":69.0,"participation_score":88.0,
            "participation_tier":"EXCEPTIONAL","status":"MONITOR","reasons":["Testing VWAP","Above 65 EMA","Higher lows",
            "Volume accelerating 1.9×","RVOL proxy 5.4×"],"cautions":["No confirmed news catalyst"],
            "previous_score":61.3,"velocity":11.5,"status_changed":False,"timestamp":now,
            "timeframes":{"1m":{"above_vwap":False,"supertrend":False},
            "3m":{"above_vwap":True,"supertrend":True},"5m":{"above_vwap":True,"supertrend":True},
            "10m":{"above_vwap":False,"supertrend":False}}
        },
        {
            "symbol":"MSGM","price":0.431,"pct_change":10.5,"volume":67240,
            "dollar_volume":28982,"spread_pct":7.5,"vwap_relation":"below",
            "vwap_distance_pct":4.2,"supertrend_bullish":False,"supertrend_flip":False,
            "ema65_relation":"below","ema65_distance_pct":3.8,"volume_acceleration":0.7,
            "green_volume_ratio":0.6,"rvol_proxy":0.9,"higher_lows":False,"near_hod":False,
            "catalyst_score":0,"headline":"","news_age_hours":None,"risk_flags":[],
            "timeframe_confirmations":0,"discovery_reasons":["market mover"],
            "opportunity_score":31.4,"conviction_score":36.0,"participation_score":15.0,
            "participation_tier":"ORDINARY","status":"PASS","reasons":["Top-mover behavior: 10.5%"],
            "cautions":["4.2% from VWAP","No confirmed news catalyst","Wide spread: 7.5%",
            "Thin dollar volume"],"previous_score":34.1,"velocity":-2.7,
            "status_changed":False,"timestamp":now,"timeframes":{}
        }
    ]
    return apply_attention_ranking(records)
