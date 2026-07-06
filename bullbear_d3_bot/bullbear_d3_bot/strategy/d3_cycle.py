"""
BullBearD3Strategy – Master orchestrator
1BullBear D3 – On-Chart Examples
https://youtu.be/Z4uWaqiE1Iw
"""
import yaml, pandas as pd
from typing import Dict

class BullBearD3Strategy:
    """
    Code-Agent friendly SMC strategy.
    Feed multi-timeframe OHLC bars – get Signal back.
    
    8-Phase D3 Cycle:
    1 HTF Bias
    2 Liquidity Sweep
    3 MSS/CHoCH
    4 POI OB/FVG
    5 LTF Trigger 5m/1m
    6 Execute Risk 1%
    7 Manage TP1/TP2/BE
    8 Journal
    """
    def __init__(self, symbol="XAUUSD", config_path="config/config.yaml"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
        self.symbol = symbol
        # symbol specifics
        self.point = 0.01 if "JPY" not in symbol and symbol!="XAUUSD" else (0.01 if symbol!="XAUUSD" else 0.01)
        if symbol == "XAUUSD":
            self.point = 0.01
            self.pip_value = 1.0
        elif symbol == "NAS100":
            self.point = 0.1
            self.pip_value = 1.0
        else:
            self.pip_value = self.config['symbols'].get(symbol, {}).get('pip_value_per_lot',10.0)

        # internal buffers for building DataFrames
        self.buffers = {tf: [] for tf in ["1m","5m","15m","1h","4h"]}

    def build_dfs(self, bar_1m, bar_5m, bar_15m, bar_1h, bar_4h):
        """
        Code agent feeds latest closed bar per TF as dict:
        {time, open, high, low, close, volume}
        Returns dict of pandas DataFrames.
        """
        if not hasattr(self, 'dfs'):
            self.dfs = {tf: pd.DataFrame() for tf in ["1m","5m","15m","1h","4h"]}

        # append
        mapping = {"1m":bar_1m, "5m":bar_5m, "15m":bar_15m, "1h":bar_1h, "4h":bar_4h}
        out = {}
        for tf, bar in mapping.items():
            if bar:
                bar_time = pd.to_datetime(bar['time'])
                latest_df = self.dfs[tf]
                if not latest_df.empty and bar_time <= latest_df.index[-1]:
                    out[tf] = latest_df
                    continue

                # simple append – in production use ring buffer
                self.buffers[tf].append(bar)
                # keep last 500
                if len(self.buffers[tf]) > 500:
                    self.buffers[tf] = self.buffers[tf][-500:]

                df = pd.DataFrame(self.buffers[tf])
                if not df.empty and 'time' in df.columns:
                    df['time'] = pd.to_datetime(df['time'])
                    df = df.set_index('time').sort_index()
                self.dfs[tf] = df
            out[tf] = self.dfs[tf]
        return out

    def describe(self):
        return {
            "name": "1BullBear_D3_SMC",
            "source": "https://youtu.be/Z4uWaqiE1Iw",
            "phases": [
                "1 HTF Bias 4H/1H Premium-Discount",
                "2 Liquidity Sweep BSL/SSL",
                "3 MSS CHoCH 15m displacement",
                "4 POI OB/FVG/Breaker 5m",
                "5 LTF Trigger 1m",
                "6 Execute 0.5-1% risk Prop Firm",
                "7 Manage TP1 2R 40% TP2 3.5R 40% BE 1R",
                "8 Journal consistency"
            ],
            "killzones_mmt": self.config['killzones_mmt'],
            "risk_pct": self.config['account']['risk_pct'],
            "symbol": self.symbol
        }
