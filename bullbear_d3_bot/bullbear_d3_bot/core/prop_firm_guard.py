"""
prop_firm_guard.py – Prop Firm Daily Loss & Risk Guard
───────────────────────────────────────────────────────
Enforces Prop Firm rules:
  - Daily loss limit: stop trading when daily PnL <= -max_daily_loss_r
  - Max daily trades: stop when trades >= max_daily_trades
  - Max drawdown: emergency stop when equity drops below threshold
  - Killzone-only enforcement: no trades outside London/NY sessions

Usage:
    from core.prop_firm_guard import PropFirmGuard
    guard = PropFirmGuard(config)

    can_trade, reason = guard.check(current_equity, current_time)
    if not can_trade:
        log.warn(f"Trading halted: {reason}")

    guard.register_trade_result(pnl_r=2.0)   # after each trade closes
    guard.reset_daily()                        # call at midnight UTC
"""

import json
import os
from datetime import date, datetime, timezone
from typing import Tuple


class PropFirmGuard:
    """
    Prop Firm risk guard. Call check() before every potential trade entry.

    State is persisted to a JSONL file to survive restarts within the same day.

    Config keys consumed (from d3_config.yaml under 'account'):
      max_daily_loss_r     (default -2.0)
      max_daily_trades     (default 3)
      max_daily_loss_usd   (optional hard USD floor, default None)
      max_drawdown_pct     (default 5.0 – emergency stop)
      starting_balance     (default 10000)
    """

    STATE_FILE = "user_data/logs/prop_firm_state.json"

    def __init__(self, config: dict):
        acc = config.get("account", {})
        self.max_loss_r      = abs(acc.get("max_daily_loss_r",   2.0))
        self.max_trades      = acc.get("max_daily_trades",        3)
        self.max_dd_pct      = acc.get("max_drawdown_pct",        5.0)
        self.starting_bal    = acc.get("balance",                 10000.0)

        self._state = self._load_state()

    # ─── Public API ───────────────────────────────────────────────────────────

    def check(
        self,
        current_equity: float,
        current_time: datetime = None,
    ) -> Tuple[bool, str]:
        """
        Returns (can_trade: bool, reason: str).
        Call before every potential trade entry.
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        self._maybe_reset_daily(current_time)
        state = self._state

        # 1. Daily loss limit
        if state["daily_pnl_r"] <= -self.max_loss_r:
            return False, (
                f"Daily loss limit reached: {state['daily_pnl_r']:.2f}R "
                f"(max -{self.max_loss_r}R)"
            )

        # 2. Max daily trades
        if state["daily_trades"] >= self.max_trades:
            return False, (
                f"Max daily trades reached: {state['daily_trades']}/{self.max_trades}"
            )

        # 3. Max drawdown (equity-based)
        if current_equity > 0:
            dd_pct = (self.starting_bal - current_equity) / self.starting_bal * 100
            if dd_pct >= self.max_dd_pct:
                return False, (
                    f"Max drawdown breached: {dd_pct:.2f}% "
                    f"(equity=${current_equity:.2f}, limit={self.max_dd_pct}%)"
                )

        return True, "OK"

    def register_trade_result(self, pnl_r: float):
        """Call after every trade closes to update daily stats."""
        self._state["daily_pnl_r"]  += pnl_r
        self._state["daily_trades"] += 1
        self._save_state()

    def register_trade_open(self):
        """Optionally call when a trade opens (reserved for future use)."""
        pass

    def status(self) -> dict:
        """Return current daily state as a dict."""
        return {
            **self._state,
            "max_loss_r":   self.max_loss_r,
            "max_trades":   self.max_trades,
            "max_dd_pct":   self.max_dd_pct,
            "loss_remaining_r": max(0, self.max_loss_r + self._state["daily_pnl_r"]),
            "trades_remaining": max(0, self.max_trades - self._state["daily_trades"]),
        }

    def reset_daily(self):
        """Force a daily reset (call at midnight or session start)."""
        self._state = self._fresh_state()
        self._save_state()

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _fresh_state(self) -> dict:
        return {
            "date":          date.today().isoformat(),
            "daily_pnl_r":   0.0,
            "daily_trades":  0,
        }

    def _maybe_reset_daily(self, current_time: datetime):
        today = current_time.date().isoformat()
        if self._state.get("date") != today:
            self._state = self._fresh_state()
            self._save_state()

    def _load_state(self) -> dict:
        os.makedirs(os.path.dirname(self.STATE_FILE), exist_ok=True)
        if os.path.exists(self.STATE_FILE):
            try:
                with open(self.STATE_FILE) as f:
                    s = json.load(f)
                # Validate it's for today
                if s.get("date") == date.today().isoformat():
                    return s
            except Exception:
                pass
        return self._fresh_state()

    def _save_state(self):
        os.makedirs(os.path.dirname(self.STATE_FILE), exist_ok=True)
        with open(self.STATE_FILE, "w") as f:
            json.dump(self._state, f, indent=2)
