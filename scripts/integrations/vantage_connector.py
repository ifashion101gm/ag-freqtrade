"""
vantage_connector.py
────────────────────
Vantage Markets MT5 data + order bridge for BullBear D3 Bot.

Requires:
  pip install MetaTrader5 pandas pytz

Credentials (set in .env):
  VANTAGE_MT5_LOGIN   = your MT5 account number (integer)
  VANTAGE_MT5_PASSWORD= your MT5 password
  VANTAGE_MT5_SERVER  = e.g. "Vantage-Demo" or "Vantage-Live"

Usage (standalone test):
  python vantage_connector.py --symbol XAUUSD --test
"""

import os
import time
import argparse
import logging
from datetime import datetime, timezone
from typing import Optional, Dict

import pandas as pd
import pytz

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    print("[WARN] MetaTrader5 package not installed. Run: pip install MetaTrader5")

log = logging.getLogger("vantage_connector")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ─── MT5 Timeframe Map ───────────────────────────────────────────────────────
TF_MAP = {
    "1m":  mt5.TIMEFRAME_M1  if MT5_AVAILABLE else 1,
    "5m":  mt5.TIMEFRAME_M5  if MT5_AVAILABLE else 5,
    "15m": mt5.TIMEFRAME_M15 if MT5_AVAILABLE else 15,
    "1h":  mt5.TIMEFRAME_H1  if MT5_AVAILABLE else 60,
    "4h":  mt5.TIMEFRAME_H4  if MT5_AVAILABLE else 240,
    "1d":  mt5.TIMEFRAME_D1  if MT5_AVAILABLE else 1440,
}

# ─── Vantage Symbol Map ──────────────────────────────────────────────────────
# Map D3 strategy symbols to exact MT5 symbol names on Vantage
SYMBOL_MAP = {
    "XAUUSD":  "XAUUSD",     # Gold
    "EURUSD":  "EURUSD",     # Euro/Dollar
    "GBPUSD":  "GBPUSD",     # Cable
    "NAS100":  "NAS100",     # Nasdaq 100 (check exact Vantage symbol name)
    "US30":    "US30",       # Dow Jones
    "USDJPY":  "USDJPY",
    "GBPJPY":  "GBPJPY",
}


class VantageConnector:
    """
    MT5 data + order bridge for Vantage Markets.

    Provides:
    - fetch_ohlcv(symbol, timeframe, n_bars) → list of OHLCV dicts
    - get_latest_bar(symbol, timeframe) → single OHLCV dict
    - place_order(symbol, direction, lots, sl, tp1, tp2) → order result
    - close_position(symbol) → close result
    - get_account_info() → dict
    - is_killzone(tz="Asia/Rangoon") → bool (MMT killzone check)
    """

    def __init__(self):
        self.login    = int(os.environ.get("VANTAGE_MT5_LOGIN", "0"))
        self.password = os.environ.get("VANTAGE_MT5_PASSWORD", "")
        self.server   = os.environ.get("VANTAGE_MT5_SERVER", "Vantage-Demo")
        self._connected = False

    # ─── Connection ──────────────────────────────────────────────────────────

    def connect(self) -> bool:
        """Initialize and log in to MT5 terminal."""
        if not MT5_AVAILABLE:
            raise RuntimeError("MetaTrader5 package not installed.")
        if not mt5.initialize():
            log.error("MT5 initialize() failed: %s", mt5.last_error())
            return False

        authorized = mt5.login(self.login, password=self.password, server=self.server)
        if not authorized:
            log.error("MT5 login failed: %s", mt5.last_error())
            mt5.shutdown()
            return False

        info = mt5.account_info()
        log.info("Connected to Vantage MT5 | Server: %s | Account: %s | Balance: %.2f %s",
                 self.server, info.login, info.balance, info.currency)
        self._connected = True
        return True

    def disconnect(self):
        if MT5_AVAILABLE and self._connected:
            mt5.shutdown()
            self._connected = False
            log.info("MT5 disconnected.")

    def ensure_connected(self):
        if not self._connected:
            self.connect()

    # ─── Market Data ─────────────────────────────────────────────────────────

    def fetch_ohlcv(self, symbol: str, timeframe: str, n_bars: int = 500) -> list:
        """
        Fetch historical OHLCV bars from MT5.
        Returns list of dicts: {time, open, high, low, close, volume}
        """
        self.ensure_connected()
        mt5_sym = SYMBOL_MAP.get(symbol, symbol)
        tf_code = TF_MAP[timeframe]

        rates = mt5.copy_rates_from_pos(mt5_sym, tf_code, 0, n_bars)
        if rates is None or len(rates) == 0:
            log.warning("No data for %s %s: %s", symbol, timeframe, mt5.last_error())
            return []

        bars = []
        for r in rates:
            bars.append({
                "time":   pd.Timestamp(r["time"], unit="s", tz="UTC").isoformat(),
                "open":   float(r["open"]),
                "high":   float(r["high"]),
                "low":    float(r["low"]),
                "close":  float(r["close"]),
                "volume": float(r["tick_volume"]),
            })
        return bars

    def get_latest_bar(self, symbol: str, timeframe: str) -> Optional[Dict]:
        """Return the most recently closed bar as OHLCV dict."""
        bars = self.fetch_ohlcv(symbol, timeframe, n_bars=2)
        if len(bars) < 2:
            return None
        return bars[-2]  # -2 = last closed; -1 = current forming

    def get_multi_tf_bars(self, symbol: str) -> Dict[str, Optional[Dict]]:
        """
        Convenience: fetch latest closed bar for all D3 timeframes at once.
        Returns: {"1m": bar_dict, "5m": bar_dict, "15m": bar_dict, "1h": bar_dict, "4h": bar_dict}
        """
        return {tf: self.get_latest_bar(symbol, tf) for tf in ["1m", "5m", "15m", "1h", "4h"]}

    # ─── Account ─────────────────────────────────────────────────────────────

    def get_account_info(self) -> Dict:
        """Return account balance, equity, margin info."""
        self.ensure_connected()
        info = mt5.account_info()
        if info is None:
            return {}
        return {
            "login":    info.login,
            "server":   info.server,
            "balance":  info.balance,
            "equity":   info.equity,
            "margin":   info.margin,
            "free_margin": info.margin_free,
            "currency": info.currency,
            "leverage": info.leverage,
        }

    # ─── Order Execution ─────────────────────────────────────────────────────

    def place_order(
        self,
        symbol: str,
        direction: str,          # "BUY" or "SELL"
        lots: float,
        sl_price: float,
        tp1_price: float,
        tp2_price: float,
        comment: str = "D3_BOT",
        dry_run: bool = True,     # True = paper mode (no real order sent)
    ) -> Dict:
        """
        Place a market order on Vantage MT5.
        In dry_run mode, logs the order without sending it.
        """
        mt5_sym  = SYMBOL_MAP.get(symbol, symbol)
        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL

        # Fetch current price
        tick = mt5.symbol_info_tick(mt5_sym)
        if tick is None:
            return {"success": False, "reason": f"No tick for {symbol}"}
        price = tick.ask if direction == "BUY" else tick.bid

        request = {
            "action":   mt5.TRADE_ACTION_DEAL,
            "symbol":   mt5_sym,
            "volume":   lots,
            "type":     order_type,
            "price":    price,
            "sl":       sl_price,
            "tp":       tp1_price,   # TP1 – partial; TP2 managed manually
            "comment":  comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        if dry_run:
            log.info("[DRY RUN] Would send order: %s", request)
            return {"success": True, "dry_run": True, "request": request, "price": price}

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            log.error("Order failed: %s | retcode=%s", result.comment, result.retcode)
            return {"success": False, "retcode": result.retcode, "reason": result.comment}

        log.info("Order placed: %s %s %s lots @ %.5f | sl=%.5f tp=%.5f",
                 direction, symbol, lots, result.price, sl_price, tp1_price)
        return {
            "success":  True,
            "order_id": result.order,
            "price":    result.price,
            "lots":     lots,
            "sl":       sl_price,
            "tp1":      tp1_price,
            "tp2":      tp2_price,
        }

    def close_position(self, symbol: str, dry_run: bool = True) -> Dict:
        """Close open position for a symbol."""
        mt5_sym = SYMBOL_MAP.get(symbol, symbol)
        positions = mt5.positions_get(symbol=mt5_sym)
        if not positions:
            return {"success": False, "reason": "No open position"}

        pos = positions[0]
        direction = "SELL" if pos.type == mt5.ORDER_TYPE_BUY else "BUY"
        tick = mt5.symbol_info_tick(mt5_sym)
        price = tick.bid if direction == "SELL" else tick.ask

        request = {
            "action":   mt5.TRADE_ACTION_DEAL,
            "symbol":   mt5_sym,
            "volume":   pos.volume,
            "type":     mt5.ORDER_TYPE_SELL if direction == "SELL" else mt5.ORDER_TYPE_BUY,
            "position": pos.ticket,
            "price":    price,
            "comment":  "D3_BOT_CLOSE",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        if dry_run:
            log.info("[DRY RUN] Would close position: %s", request)
            return {"success": True, "dry_run": True}

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {"success": False, "retcode": result.retcode, "reason": result.comment}
        return {"success": True, "order_id": result.order, "price": result.price}

    # ─── Killzone Helper ─────────────────────────────────────────────────────

    def is_killzone(self, killzones: dict, tz_str: str = "Asia/Rangoon") -> bool:
        """
        Check if current MMT time is within any defined killzone.
        killzones: {"london": ["15:00","17:00"], "ny_am": ["19:30","22:00"]}
        """
        tz = pytz.timezone(tz_str)
        now = datetime.now(tz).strftime("%H:%M")
        for name, (start, end) in killzones.items():
            if start <= now <= end:
                log.debug("In killzone: %s (%s – %s) MMT", name, start, end)
                return True
        return False


# ─── CLI Test ────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Vantage MT5 Connector Test")
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--test", action="store_true", help="Run connection and data test")
    args = ap.parse_args()

    connector = VantageConnector()
    try:
        connector.connect()
        acc = connector.get_account_info()
        print("Account info:", acc)

        bars = connector.get_multi_tf_bars(args.symbol)
        for tf, bar in bars.items():
            if bar:
                print(f"  [{tf}] {bar['time']}  O={bar['open']} H={bar['high']} L={bar['low']} C={bar['close']}")
            else:
                print(f"  [{tf}] No data")

        # Killzone test (MMT)
        killzones = {
            "london": ("15:00", "17:00"),
            "ny_am":  ("19:30", "22:00"),
            "ny_pm":  ("21:00", "23:30"),
        }
        in_kz = connector.is_killzone(killzones)
        print(f"\nCurrent MMT killzone active: {in_kz}")
    finally:
        connector.disconnect()


if __name__ == "__main__":
    main()
