"""
Phase 5 – LTF Trigger 5m / 1m
1BullBear D3
"""
from dataclasses import dataclass
import pandas as pd

@dataclass
class TriggerResult:
    triggered: bool
    direction: str
    entry_price: float
    time_stop: bool
    reason: str

class LTFTrigger:
    def __init__(self, time_stop_bars=12):
        self.time_stop_bars = time_stop_bars
        self._tap_bar_index = None

    def check(self, df_1m: pd.DataFrame, poi, mss_direction: str) -> TriggerResult:
        if poi is None or not poi.valid:
            return TriggerResult(False,"NONE",0,False,"no POI")
        if df_1m.empty:
            return TriggerResult(False,"NONE",0,False,"no 1m")

        last = df_1m.iloc[-1]
        # price tapped POI?
        tapped = (last['low'] <= poi.high and last['high'] >= poi.low)
        if tapped and self._tap_bar_index is None:
            self._tap_bar_index = len(df_1m)-1

        # time stop
        if self._tap_bar_index is not None:
            bars_since = len(df_1m)-1 - self._tap_bar_index
            if bars_since > self.time_stop_bars:
                self._tap_bar_index = None
                return TriggerResult(False,"NONE",0,True,"D3 time stop 12×1m – scratch")

        if not tapped and self._tap_bar_index is None:
            return TriggerResult(False,"NONE",0,False,"waiting POI tap")

        # LTF CHoCH – simple: close break micro swing
        # bullish: close > prior 3-bar high
        if mss_direction.startswith("BULL"):
            micro_high = df_1m['high'].tail(5).max()
            if last['close'] > micro_high * 0.9995:  # allow
                # trigger long at close / FVG retest
                entry = last['close']
                self._tap_bar_index = None
                return TriggerResult(True,"BUY",entry,False,
                    f"D3 1m LTF BUY trigger @{entry:.2f} – {poi.type}")
        else:
            micro_low = df_1m['low'].tail(5).min()
            if last['close'] < micro_low * 1.0005:
                entry = last['close']
                self._tap_bar_index = None
                return TriggerResult(True,"SELL",entry,False,
                    f"D3 1m LTF SELL trigger @{entry:.2f} – {poi.type}")

        return TriggerResult(False, mss_direction.split("_")[0], 0, False, "LTF waiting displacement")
