# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these libs ---
import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime, timezone
import talib.abstract as ta

from freqtrade.strategy import (
    BooleanParameter,
    CategoricalParameter,
    DecimalParameter,
    IStrategy,
    IntParameter,
)

import qtpylib.indicators as qt

class ProfitStrategy(IStrategy):
    """
    ProfitStrategy - Optimized for profit with EMA Crossovers, RSI triggers,
    and trailing stoploss controls.
    """
    INTERFACE_VERSION = 3

    # ROI table:
    minimal_roi = {
        "0": 0.05,       # 5% profit at start
        "30": 0.03,      # 3% profit after 30 mins
        "60": 0.015,     # 1.5% profit after 1 hour
        "120": 0.005     # 0.5% profit after 2 hours
    }

    # Stoploss designed for the strategy
    stoploss = -0.04

    # Trailing stoploss
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # Run "populate_indicators()" only for new candle
    process_only_new_candles = True

    # Standard settings
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Number of candles required before producing signals
    startup_candle_count: int = 50

    # Timeframe
    timeframe = '5m'

    # Order type configuration
    order_types = {
        "entry": "limit",
        "exit": "limit",
        "emergency_exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": False
    }

    # Time in force
    order_time_in_force = {
        "entry": "GTC",
        "exit": "GTC"
    }

    def informative_pairs(self):
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Calculate moving averages
        dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=9)
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=50)

        # Calculate RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # Calculate MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['ema_fast'] > dataframe['ema_slow']) &
                (dataframe['rsi'] < 65) &
                (dataframe['macdhist'] > 0) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['ema_fast'] < dataframe['ema_slow']) |
                (dataframe['rsi'] > 75)
            ),
            'exit_long'] = 1

        return dataframe
