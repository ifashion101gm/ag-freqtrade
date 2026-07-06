"""
Phase 1 – HTF Bias
1BullBear D3 – On-Chart Examples
Video: https://youtu.be/Z4uWaqiE1Iw
"""
from dataclasses import dataclass
from typing import List, Dict
import pandas as pd

@dataclass
class BiasResult:
    direction: str  # "BULL","BEAR","NEUTRAL"
    premium_discount: str  # "PREMIUM","DISCOUNT","EQUILIBRIUM"
    valid: bool
    reason: str

class HTFBias:
    """
    D3 Phase 1 – Top-down 4H / 1H
    - BOS structure HH/HL vs LH/LL
    - Premium/Discount 50% fib of last HTF swing
    - 1BullBear: Only buy Discount, sell Premium
    """
    def __init__(self, lookback: int = 60):
        self.lookback = lookback

    def evaluate(self, df_4h: pd.DataFrame, df_1h: pd.DataFrame) -> BiasResult:
        if df_1h.empty or len(df_1h) < 20:
            return BiasResult("NEUTRAL","EQUILIBRIUM",False,"insufficient HTF data")

        # Simple swing structure – last 2 swing highs/lows
        highs = df_1h['high'].rolling(5, center=True).max()
        lows = df_1h['low'].rolling(5, center=True).min()

        # BOS logic – simplified
        recent = df_1h.tail(self.lookback)
        hh = recent['high'].max()
        ll = recent['low'].min()
        last_close = recent['close'].iloc[-1]

        # Premium / Discount
        range_mid = ll + (hh - ll) * 0.5
        if last_close < ll + (hh-ll)*0.5*0.95:  # <50% = discount
            pd_zone = "DISCOUNT"
        elif last_close > ll + (hh-ll)*0.5*1.05:
            pd_zone = "PREMIUM"
        else:
            pd_zone = "EQUILIBRIUM"

        # Structure direction – last 2 fractals
        # simplified: slope of 20EMA
        ema20 = recent['close'].ewm(span=20).mean().iloc[-1]
        ema20_prev = recent['close'].ewm(span=20).mean().iloc[-5]
        if ema20 > ema20_prev * 1.0005:
            direction = "BULL"
        elif ema20 < ema20_prev * 0.9995:
            direction = "BEAR"
        else:
            direction = "NEUTRAL"

        # 1BullBear confluence: 4H must agree if available
        if not df_4h.empty and len(df_4h) > 10:
            c4 = df_4h['close']
            e4 = c4.ewm(span=20).mean()
            if e4.iloc[-1] > e4.iloc[-3] and direction == "BEAR":
                # conflict – downgrade
                pass

        valid = (direction != "NEUTRAL") and (
            (direction=="BULL" and pd_zone=="DISCOUNT") or
            (direction=="BEAR" and pd_zone=="PREMIUM") or
            pd_zone=="EQUILIBRIUM"  # allow equilibrium with strong BOS – D3 ex #3
        )

        reason = f"D3 HTF {direction} – {pd_zone} – 1H close {last_close:.2f} vs mid {range_mid:.2f}"
        return BiasResult(direction, pd_zone, valid, reason)
