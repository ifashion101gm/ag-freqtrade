# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these libs ---
import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime, timezone

from freqtrade.strategy import (
    BooleanParameter,
    CategoricalParameter,
    DecimalParameter,
    IStrategy,
    IntParameter,
)

# --- Import technical libraries ---
import qtpylib.indicators as qt

class SampleStrategy(IStrategy):
    """
    This is a stable, open-source Sample Strategy suitable for testing.
    It utilizes simple SMA crossovers and RSI thresholds to make entry/exit decisions.
    """
    # Strategy interface version
    INTERFACE_VERSION = 3

    # Minimal ROI designed for the strategy
    minimal_roi = {
        "60": 0.01,
        "30": 0.02,
        "0": 0.04
    }

    # Optimal stoploss designed for the strategy
    stoploss = -0.10

    # Trailing stoploss
    trailing_stop = False

    # Run "populate_indicators()" only for new candle
    process_only_new_candles = True

    # Standard settings
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Number of candles required before producing signals
    startup_candle_count: int = 30

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
        """
        Define additional, informative pairs of candles that can be useful for analysis.
        """
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Calculates indicators needed for buying and selling.
        """
        # Calculate moving averages
        dataframe['sma_fast'] = qt.sma(dataframe['close'], window=9)
        dataframe['sma_slow'] = qt.sma(dataframe['close'], window=50)

        # Calculate RSI
        # Fallback to pandas rolling if qtpylib calculation behaves unexpectedly
        delta = dataframe['close'].diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ema_up = up.ewm(com=13, adjust=False).mean()
        ema_down = down.ewm(com=13, adjust=False).mean()
        rs = ema_up / (ema_down + 1e-10)
        dataframe['rsi'] = 100 - (100 / (1.0 + rs))

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Defines buy/entry signals based on RSI and SMA indicators.
        """
        dataframe.loc[
            (
                (dataframe['rsi'] < 30) &
                (dataframe['sma_fast'] > dataframe['sma_slow'])
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Defines sell/exit signals based on RSI indicator.
        """
        dataframe.loc[
            (
                (dataframe['rsi'] > 70)
            ),
            'exit_long'] = 1

        return dataframe
