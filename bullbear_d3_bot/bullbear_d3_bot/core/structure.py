"""
Phase 3 – MSS / CHoCH
1BullBear D3 – 15m Market Structure Shift
"""
from dataclasses import dataclass
import pandas as pd

@dataclass
class MSSResult:
    mss: bool
    direction: str  # "BULL_MSS" / "BEAR_MSS" / "NONE"
    break_level: float
    displacement: bool
    valid: bool
    reason: str

class MarketStructure:
    def __init__(self, displacement_body_pct=55):
        self.body_pct = displacement_body_pct / 100.0

    def detect_mss(self, df_15m: pd.DataFrame) -> MSSResult:
        if len(df_15m) < 20:
            return MSSResult(False,"NONE",0,False,False,"need 20 bars 15m")

        # last swing high / low – fractal 3
        highs = df_15m['high']
        lows = df_15m['low']
        closes = df_15m['close']
        opens = df_15m['open']

        # naive last lower high / higher low
        # find recent swing points
        # simplify: last 2 pivots
        last_swing_high = highs.rolling(3, center=True).max().dropna().tail(2)
        last_swing_low  = lows.rolling(3, center=True).min().dropna().tail(2)

        if last_swing_high.empty or last_swing_low.empty:
            return MSSResult(False,"NONE",0,False,False,"no swing")

        # CHoCH – break opposite
        # Bullish MSS: close above last lower high
        lsh = last_swing_high.iloc[-1]
        lsl = last_swing_low.iloc[-1]
        last = df_15m.iloc[-1]
        prev = df_15m.iloc[-2]

        body = abs(last['close'] - last['open'])
        rng = last['high'] - last['low'] + 1e-9
        displacement = (body / rng) >= self.body_pct

        # bullish break
        if last['close'] > lsh and closes.iloc[-3] < lsh:
            return MSSResult(True,"BULL_MSS",lsh,displacement,displacement,
                f"D3 15m BULL MSS break {lsh:.2f} disp={displacement}")
        # bearish break
        if last['close'] < lsl and closes.iloc[-3] > lsl:
            return MSSResult(True,"BEAR_MSS",lsl,displacement,displacement,
                f"D3 15m BEAR MSS break {lsl:.2f} disp={displacement}")

        return MSSResult(False,"NONE",0,False,False,"waiting MSS – D3 no displacement no trade")
