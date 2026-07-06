"""
Phase 2 – Liquidity Sweep
1BullBear D3 – BSL / SSL Judas Raid
"""
from dataclasses import dataclass
import pandas as pd

@dataclass
class SweepResult:
    swept: bool
    side: str  # "BSL" / "SSL" / "NONE"
    level: float
    swept_bar_time: any
    valid: bool
    reason: str

class LiquiditySweep:
    def __init__(self, equal_tolerance_pips=5, min_sweep_pips=8, point=0.01):
        self.tol = equal_tolerance_pips * point
        self.min_sweep = min_sweep_pips * point
        self.point = point

    def detect(self, df: pd.DataFrame, lookback: int = 40) -> SweepResult:
        """
        Detect Asia / prev day high/low raid with wick close-back.
        D3 video: sweep wick must close back inside in 1-3 bars.
        """
        if len(df) < lookback+5:
            return SweepResult(False,"NONE",0,None,False,"too short")

        recent = df.tail(lookback)
        # find equal highs / lows – naive swing highs
        swing_high = recent['high'].max()
        swing_low = recent['low'].min()
        sh_time = recent['high'].idxmax()
        sl_time = recent['low'].idxmin()

        # check last 5 bars for sweep
        tail = df.tail(5)
        swept_bsl = (tail['high'] > swing_high + self.min_sweep).any()
        swept_ssl = (tail['low'] < swing_low - self.min_sweep).any()

        if swept_bsl:
            # close back inside?
            close_back = (tail['close'].iloc[-1] < swing_high)
            return SweepResult(True,"BSL",swing_high,tail.index[-1],close_back,
                f"D3 BSL sweep {swing_high:.2f} – close_back={close_back}")
        if swept_ssl:
            close_back = (tail['close'].iloc[-1] > swing_low)
            return SweepResult(True,"SSL",swing_low,tail.index[-1],close_back,
                f"D3 SSL sweep {swing_low:.2f} – close_back={close_back}")

        return SweepResult(False,"NONE",0,None,False,"no sweep – D3: No sweep, No trade")
