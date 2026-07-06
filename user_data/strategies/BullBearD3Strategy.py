"""
BullBearD3Strategy.py
─────────────────────
Freqtrade IStrategy wrapper for the 1BullBear D3 8-Phase SMC cycle.
Designed for Vantage Markets Forex/CFD (XAUUSD, EURUSD, NAS100).
Source: https://youtu.be/Z4uWaqiE1Iw
"""
# pragma pylint: disable=missing-docstring, invalid-name
import sys, logging
from pathlib import Path
from typing import Optional
from datetime import datetime
from pandas import DataFrame
from freqtrade.strategy import IStrategy

log = logging.getLogger("BullBearD3Strategy")

D3_BOT_PATH = Path("/freqtrade/bullbear_d3_bot/bullbear_d3_bot")
if str(D3_BOT_PATH) not in sys.path:
    sys.path.insert(0, str(D3_BOT_PATH))

try:
    from strategy.d3_cycle import BullBearD3Strategy as D3Core
    from core.execution import ExecutionEngine, Signal
    D3_AVAILABLE = True
except ImportError as e:
    log.error("D3 package not found: %s", e)
    D3_AVAILABLE = False

D3_CONFIG_PATH = "/freqtrade/configs/d3_config.yaml"


class BullBearD3Strategy(IStrategy):
    """1BullBear D3 8-Phase SMC – Freqtrade IStrategy wrapper for Vantage Forex."""

    INTERFACE_VERSION = 3
    timeframe = "1m"
    minimal_roi = {"0": 0.10}
    stoploss = -0.05
    use_exit_signal = True
    exit_profit_only = False
    trailing_stop = False
    process_only_new_candles = True
    startup_candle_count = 200
    order_types = {"entry": "market", "exit": "market", "emergency_exit": "market",
                   "stoploss": "market", "stoploss_on_exchange": False}
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._engines: dict = {}

    def _get_engine(self, symbol: str):
        if not D3_AVAILABLE:
            return None
        if symbol not in self._engines:
            try:
                self._engines[symbol] = ExecutionEngine(
                    D3Core(symbol=symbol, config_path=D3_CONFIG_PATH))
                log.info("D3 engine ready: %s", symbol)
            except Exception as e:
                log.error("D3 engine init failed %s: %s", symbol, e)
                return None
        return self._engines[symbol]

    def informative_pairs(self):
        return [(pair, tf) for pair in self.dp.current_whitelist()
                for tf in ["5m", "15m", "1h", "4h"]]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        symbol = pair.replace("/", "").replace(":USD", "").replace("_", "")
        engine = self._get_engine(symbol)
        if engine is None:
            dataframe["d3_signal"] = "FLAT"
            return dataframe

        def get_bar(tf):
            try:
                df = self.dp.get_pair_dataframe(pair=pair, timeframe=tf)
                if df is None or df.empty:
                    return None
                r = df.iloc[-2]
                return {"time": str(r["date"]), "open": float(r["open"]),
                        "high": float(r["high"]), "low": float(r["low"]),
                        "close": float(r["close"]), "volume": float(r.get("volume", 0))}
            except Exception:
                return None

        try:
            sig = engine.on_bar_1m(get_bar("1m"), get_bar("5m"),
                                   get_bar("15m"), get_bar("1h"), get_bar("4h"))
            dataframe["d3_signal"] = "FLAT"
            dataframe["d3_phase"]  = sig.phase
            dataframe["d3_sl"]     = sig.sl
            dataframe["d3_tp1"]    = sig.tp1
            dataframe["d3_tp2"]    = sig.tp2
            dataframe["d3_size"]   = sig.size_lots
            dataframe["d3_rr"]     = sig.rr
            dataframe["d3_reason"] = sig.reason
            dataframe.loc[dataframe.index[-1], "d3_signal"] = sig.action
            log.debug("D3 [%s] %s ph=%s %s", symbol, sig.action, sig.phase, sig.reason)
        except Exception as e:
            log.error("D3 error %s: %s", symbol, e)
            dataframe["d3_signal"] = "FLAT"
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["d3_signal"] == "BUY",  "enter_long"]  = 1
        dataframe.loc[dataframe["d3_signal"] == "SELL", "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["d3_signal"] == "EXIT", "exit_long"]  = 1
        dataframe.loc[dataframe["d3_signal"] == "EXIT", "exit_short"] = 1
        return dataframe

    def custom_stoploss(self, pair, trade, current_time, current_rate,
                        current_profit, after_fill, **kwargs) -> float:
        sym = pair.replace("/", "").replace(":USD", "").replace("_", "")
        eng = self._get_engine(sym)
        if eng and eng.position:
            sl = eng.position.get("sl", 0)
            op = trade.open_rate
            if op > 0 and sl > 0:
                return max((sl - op) / op, -0.10)
        return self.stoploss

    def custom_stake_amount(self, current_time, current_rate, current_profit,
                            proposed_stake, min_stake, max_stake, leverage,
                            entry_tag, side, **kwargs) -> float:
        return proposed_stake  # TODO M2: wire D3 risk_plan.lots
