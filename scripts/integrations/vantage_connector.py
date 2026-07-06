"""
vantage_connector.py
────────────────────
Vantage Markets MT5 REST Client for Freqtrade (Docker).

This connector communicates with the MT5Adapter (server.py) running on the host via HTTP,
bypassing the need to install Windows/Wine packages inside the Linux Docker container.
"""

import os
import time
import requests
import logging
from datetime import datetime, timezone
import pandas as pd
import pytz

log = logging.getLogger("vantage_connector")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Connect to the adapter running on the Docker host
# Default host IP from inside a Docker container is often 172.17.0.1 on Linux
# We allow overriding it via MT5_ADAPTER_URL
ADAPTER_URL = os.environ.get("MT5_ADAPTER_URL", "http://172.17.0.1:5000")

class VantageConnector:
    """
    MT5 REST API client.
    Replaces the direct MetaTrader5 python binding.
    """
    
    def __init__(self):
        self._connected = False
        
    def connect(self) -> bool:
        """Check if the MT5 Adapter is responsive."""
        try:
            resp = requests.get(f"{ADAPTER_URL}/health", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                log.info("Connected via Adapter | Server: %s | Account: %s | Balance: %.2f %s",
                         data['server'], data['account'], data['balance'], data['currency'])
                self._connected = True
                return True
            else:
                log.error("Adapter health check failed: %s", resp.text)
                return False
        except requests.RequestException as e:
            log.error("Cannot reach MT5 Adapter at %s: %s", ADAPTER_URL, e)
            return False

    def ensure_connected(self):
        if not self._connected:
            self.connect()

    def fetch_ohlcv(self, symbol: str, timeframe: str, n_bars: int = 500) -> list:
        """Fetch historical OHLCV bars via the Adapter API."""
        self.ensure_connected()
        
        try:
            resp = requests.get(f"{ADAPTER_URL}/ohlcv", params={
                "symbol": symbol,
                "timeframe": timeframe,
                "n_bars": n_bars
            }, timeout=10)
            
            if resp.status_code == 200:
                return resp.json()
            else:
                log.error("Failed to fetch OHLCV: %s", resp.text)
                return []
        except requests.RequestException as e:
            log.error("Error fetching OHLCV: %s", e)
            return []

    def get_latest_bar(self, symbol: str, timeframe: str) -> dict:
        bars = self.fetch_ohlcv(symbol, timeframe, n_bars=2)
        if len(bars) >= 2:
            return bars[-2] # Return the last CLOSED bar
        return None

    def place_order(self, symbol: str, direction: str, lots: float, sl: float=0.0, tp1: float=0.0, tp2: float=0.0) -> dict:
        """Place an order via the Adapter API."""
        self.ensure_connected()
        payload = {
            "symbol": symbol,
            "direction": direction,
            "lots": lots,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2
        }
        
        try:
            resp = requests.post(f"{ADAPTER_URL}/order", json=payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                log.info("Order %s SUCCESS: Ticket %s", direction, data.get('order_ticket'))
                return data
            else:
                log.error("Order %s FAILED: %s", direction, resp.text)
                return {}
        except requests.RequestException as e:
            log.error("Error placing order: %s", e)
            return {}

    def is_killzone(self, tz="Asia/Rangoon") -> bool:
        """Check if current time is within a valid MMT Killzone."""
        now = datetime.now(pytz.timezone(tz))
        t = now.time()
        
        # Asia (08:00 - 10:30 MMT)
        if t >= datetime.strptime("08:00", "%H:%M").time() and t <= datetime.strptime("10:30", "%H:%M").time():
            return True
        # London (15:00 - 17:00 MMT)
        if t >= datetime.strptime("15:00", "%H:%M").time() and t <= datetime.strptime("17:00", "%H:%M").time():
            return True
        # NY AM (19:30 - 22:00 MMT)
        if t >= datetime.strptime("19:30", "%H:%M").time() and t <= datetime.strptime("22:00", "%H:%M").time():
            return True
            
        return False

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()

    conn = VantageConnector()
    if conn.connect():
        print(f"Testing {args.symbol} M1 data...")
        bars = conn.fetch_ohlcv(args.symbol, "1m", 5)
        for b in bars:
            print(b)
        print(f"In Killzone? {conn.is_killzone()}")
