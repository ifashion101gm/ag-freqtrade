"""
Phase 4 – POI – OB / FVG / Breaker
1BullBear D3
"""
from dataclasses import dataclass
import pandas as pd

@dataclass
class POI:
    type: str  # OB, FVG, BREAKER
    direction: str
    high: float
    low: float
    ce: float
    age_bars: int
    valid: bool
    reason: str

class POIFinder:
    def __init__(self, fvg_min_pips=4, point=0.01):
        self.fvg_min = fvg_min_pips * point

    def find_ob_fvg(self, df_5m: pd.DataFrame, mss_direction: str) -> POI:
        if len(df_5m) < 10:
            return POI("NONE","NONE",0,0,0,99,False,"short data")

        # FVG first – 3 candle imbalance
        # bullish FVG: low[0] > high[-2]
        a,b,c = df_5m.iloc[-3], df_5m.iloc[-2], df_5m.iloc[-1]
        if mss_direction.startswith("BULL"):
            # look for bullish FVG
            if c['low'] > a['high'] and (c['low']-a['high']) >= self.fvg_min:
                ce = a['high'] + (c['low']-a['high'])/2
                return POI("FVG","BULL",c['low'],a['high'],ce,1,True,
                    f"D3 5m Bull FVG {a['high']:.2f}-{c['low']:.2f} CE {ce:.2f}")
            # OB – last bear candle before MSS impulse
            # simplified: last red candle
            reds = df_5m[df_5m['close'] < df_5m['open']].tail(3)
            if not reds.empty:
                ob = reds.iloc[-1]
                ce = (ob['open']+ob['close'])/2
                return POI("OB","BULL",ob['high'],ob['low'],ce,2,True,
                    f"D3 5m Bull OB CE {ce:.2f}")
        else:  # BEAR
            if a['low'] > c['high'] and (a['low']-c['high']) >= self.fvg_min:
                ce = c['high'] + (a['low']-c['high'])/2
                return POI("FVG","BEAR",a['low'],c['high'],ce,1,True,
                    f"D3 5m Bear FVG {c['high']:.2f}-{a['low']:.2f} CE {ce:.2f}")
            greens = df_5m[df_5m['close'] > df_5m['open']].tail(3)
            if not greens.empty:
                ob = greens.iloc[-1]
                ce = (ob['open']+ob['close'])/2
                return POI("OB","BEAR",ob['high'],ob['low'],ce,2,True,
                    f"D3 5m Bear OB CE {ce:.2f}")

        return POI("NONE","NONE",0,0,0,99,False,"no POI – wait D3 pullback")
