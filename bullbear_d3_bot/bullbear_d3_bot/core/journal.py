"""
Phase 8 – Journal / Consistency Guard
1BullBear D3 – Prop Firm Level
"""
import json, os, time
from datetime import datetime

class Journal:
    def __init__(self, path="logs/trades.jsonl"):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.daily_r = 0.0
        self.daily_trades = 0
        self._day = datetime.utcnow().date()

    def _reset_day_if_needed(self):
        today = datetime.utcnow().date()
        if today != self._day:
            self._day = today
            self.daily_r = 0.0
            self.daily_trades = 0

    def log_signal(self, signal: dict):
        self._reset_day_if_needed()
        signal['ts_utc'] = datetime.utcnow().isoformat()
        signal['video_source'] = "https://youtu.be/Z4uWaqiE1Iw"
        signal['strategy'] = "1BullBear_D3"
        with open(self.path, "a") as f:
            f.write(json.dumps(signal) + "\n")

    def can_trade(self, max_daily_loss_r=2.0, max_daily_trades=4):
        self._reset_day_if_needed()
        if self.daily_r <= -abs(max_daily_loss_r):
            return False, f"Daily loss guard {self.daily_r:.2f}R – D3 stop"
        if self.daily_trades >= max_daily_trades:
            return False, "Max daily trades reached"
        return True, "OK"

    def register_fill(self, r_result: float):
        self.daily_r += r_result
        self.daily_trades += 1
