"""
logger.py – Structured JSON Logger for D3 Bot
───────────────────────────────────────────────
Provides a unified logging interface that writes:
  - Rotating JSON log files  → user_data/logs/d3_bot.jsonl
  - Telegram alerts          → on BUY/SELL/EXIT/ERROR/RESTART

Usage:
    from utils.logger import BotLogger
    log = BotLogger()
    log.signal("BUY", symbol="XAUUSD", entry=1920.5, sl=1915.0, tp1=1930.5, reason="D3 ph6")
    log.info("Engine started")
    log.error("Connection failed", exc="TimeoutError")
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Optional
import requests

# ─── Config ──────────────────────────────────────────────────────────────────

LOG_DIR       = os.environ.get("LOG_DIR",      "user_data/logs")
LOG_FILE      = os.path.join(LOG_DIR, "d3_bot.jsonl")
LOG_LEVEL     = os.environ.get("LOG_LEVEL",   "INFO")
MAX_BYTES     = 10 * 1024 * 1024   # 10 MB per file
BACKUP_COUNT  = 5                   # keep 5 rotated files

TG_TOKEN      = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID",   "")

# Emoji map for Telegram messages
_EMOJI = {
    "BUY":     "📈",
    "SELL":    "📉",
    "EXIT":    "✅",
    "MANAGE":  "🔄",
    "FLAT":    "⏸️",
    "INFO":    "ℹ️",
    "WARN":    "⚠️",
    "ERROR":   "🚨",
    "RESTART": "🔁",
    "START":   "🤖",
    "HEALTH":  "💓",
}


class JsonLineHandler(RotatingFileHandler):
    """Writes structured JSON Lines to a rotating log file."""

    def emit(self, record: logging.LogRecord):
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            msg = self.format(record)
            # Write raw JSON line (already formatted by JsonFormatter below)
            with open(self.baseFilename, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
            self.doRollover() if self.shouldRollover(record) else None
        except Exception:
            self.handleError(record)


class JsonFormatter(logging.Formatter):
    """Formats log records as JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts":      datetime.now(timezone.utc).isoformat(),
            "level":   record.levelname,
            "logger":  record.name,
            "msg":     record.getMessage(),
        }
        if hasattr(record, "extra"):
            payload.update(record.extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class BotLogger:
    """
    Unified bot logger.

    Methods:
      info(msg, **extra)
      warn(msg, **extra)
      error(msg, **extra)
      signal(action, symbol, entry, sl, tp1, tp2, reason, phase)
      trade_result(action, symbol, entry, exit_price, pnl_r, pnl_usd, killzone)
      health(status, disk_pct, mem_pct, cpu_pct)
      telegram(text, level)     – send raw Telegram message
    """

    def __init__(self, name: str = "D3Bot"):
        os.makedirs(LOG_DIR, exist_ok=True)

        self._log = logging.getLogger(name)
        self._log.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
        self._log.handlers.clear()

        # JSON file handler
        fh = JsonLineHandler(LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT)
        fh.setFormatter(JsonFormatter())
        self._log.addHandler(fh)

        # Console handler (human-readable)
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        self._log.addHandler(ch)

    # ─── Core log methods ─────────────────────────────────────────────────────

    def _emit(self, level: str, msg: str, notify: bool = False, **extra):
        record = self._log.makeRecord(
            self._log.name, getattr(logging, level.upper()),
            "(bot)", 0, msg, (), None
        )
        record.extra = extra
        self._log.handle(record)
        if notify and TG_TOKEN and TG_CHAT_ID:
            self._send_telegram(level, msg, extra)

    def info(self, msg: str, **extra):
        self._emit("INFO", msg, **extra)

    def warn(self, msg: str, **extra):
        self._emit("WARNING", msg, notify=True, **extra)

    def error(self, msg: str, notify: bool = True, **extra):
        self._emit("ERROR", msg, notify=notify, **extra)

    # ─── Structured event methods ─────────────────────────────────────────────

    def signal(
        self, action: str, symbol: str,
        entry: float = 0, sl: float = 0,
        tp1: float = 0, tp2: float = 0,
        size: float = 0, rr: float = 0,
        reason: str = "", phase: int = 0,
    ):
        """Log a D3 signal (BUY/SELL/FLAT/EXIT/MANAGE)."""
        msg = f"[{action}] {symbol} @ {entry:.5f}  SL={sl:.5f}  TP1={tp1:.5f}  TP2={tp2:.5f}  size={size}  rr={rr:.1f}R"
        notify = action in ("BUY", "SELL", "EXIT")
        self._emit("INFO", msg, notify=notify,
                   event="signal", action=action, symbol=symbol,
                   entry=entry, sl=sl, tp1=tp1, tp2=tp2,
                   size=size, rr=rr, reason=reason, phase=phase)
        if notify:
            emoji = _EMOJI.get(action, "•")
            text = (
                f"{emoji} *D3 Signal: {action}*\n"
                f"Symbol: `{symbol}`\n"
                f"Entry: `{entry:.5f}`\n"
                f"SL: `{sl:.5f}` | TP1: `{tp1:.5f}` | TP2: `{tp2:.5f}`\n"
                f"Size: `{size} lots` | RR: `{rr:.1f}R`\n"
                f"Phase: `{phase}` | Reason: _{reason}_"
            )
            self.telegram(text)

    def trade_result(
        self, action: str, symbol: str,
        entry: float, exit_price: float,
        pnl_r: float, pnl_usd: float, killzone: str = "",
    ):
        """Log a completed trade result."""
        outcome = "WIN" if pnl_r > 0 else ("BE" if pnl_r == 0 else "LOSS")
        msg = f"[{outcome}] {symbol} {action}  entry={entry:.5f} exit={exit_price:.5f}  pnl={pnl_r:+.2f}R  ${pnl_usd:+.2f}  kz={killzone}"
        self._emit("INFO", msg, notify=True,
                   event="trade_result", outcome=outcome, symbol=symbol,
                   action=action, entry=entry, exit_price=exit_price,
                   pnl_r=pnl_r, pnl_usd=pnl_usd, killzone=killzone)
        emoji = "✅" if pnl_r > 0 else ("🟡" if pnl_r == 0 else "❌")
        text = (
            f"{emoji} *Trade Closed: {outcome}*\n"
            f"Symbol: `{symbol}` | Direction: `{action}`\n"
            f"Entry: `{entry:.5f}` → Exit: `{exit_price:.5f}`\n"
            f"PnL: `{pnl_r:+.2f}R` (`${pnl_usd:+.2f}`)\n"
            f"Killzone: `{killzone}`"
        )
        self.telegram(text)

    def health(self, status: str, disk_pct: int = 0, mem_pct: int = 0,
               cpu_pct: int = 0, api_ok: bool = True):
        """Log a health check result."""
        msg = f"[HEALTH] status={status}  disk={disk_pct}%  mem={mem_pct}%  cpu={cpu_pct}%  api={'OK' if api_ok else 'FAIL'}"
        notify = status != "OK"
        self._emit("INFO" if status == "OK" else "WARNING", msg, notify=notify,
                   event="health", status=status, disk_pct=disk_pct,
                   mem_pct=mem_pct, cpu_pct=cpu_pct, api_ok=api_ok)

    def prop_firm_guard(self, action: str, reason: str, daily_r: float):
        """Log a Prop Firm daily loss guard event."""
        msg = f"[PROP_FIRM_GUARD] action={action}  reason={reason}  daily_r={daily_r:.2f}R"
        self._emit("WARNING", msg, notify=True,
                   event="prop_firm_guard", action=action,
                   reason=reason, daily_r=daily_r)
        text = f"🛑 *Prop Firm Guard*: {action}\n{reason}\nDaily PnL: `{daily_r:.2f}R`"
        self.telegram(text)

    # ─── Telegram ─────────────────────────────────────────────────────────────

    def telegram(self, text: str, parse_mode: str = "Markdown"):
        """Send a message to Telegram (silent if token not set)."""
        if not TG_TOKEN or not TG_CHAT_ID:
            return
        try:
            url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
            requests.post(url, json={
                "chat_id":    TG_CHAT_ID,
                "text":       text,
                "parse_mode": parse_mode,
            }, timeout=5)
        except Exception as e:
            self._log.warning("Telegram send failed: %s", e)

    def _send_telegram(self, level: str, msg: str, extra: dict):
        emoji = _EMOJI.get(level.upper(), "•")
        text  = f"{emoji} *{level.upper()}*\n`{msg}`"
        if extra:
            text += "\n" + "\n".join(f"`{k}`: `{v}`" for k, v in list(extra.items())[:5])
        self.telegram(text)


# ─── Convenience singleton ────────────────────────────────────────────────────
_default_logger: Optional[BotLogger] = None


def get_logger(name: str = "D3Bot") -> BotLogger:
    global _default_logger
    if _default_logger is None:
        _default_logger = BotLogger(name)
    return _default_logger
