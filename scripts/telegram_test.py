#!/usr/bin/env python3
"""
telegram_test.py – Test Telegram Bot Connection
───────────────────────────────────────────────
Verifies TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from .env
by sending a test message.

Usage:
  cd freqtrade-server
  python scripts/telegram_test.py

Set in .env:
  TELEGRAM_BOT_TOKEN=1234567890:ABCDEFabcdef
  TELEGRAM_CHAT_ID=-1001234567890
"""

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"[OK] Loaded .env from {env_path}")
else:
    print(f"[WARN] .env not found at {env_path}. Using environment variables.")

TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

if not TOKEN or not CHAT_ID:
    print("[ERROR] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set.")
    print("        Set them in .env and re-run.")
    sys.exit(1)

MESSAGE = (
    "🤖 *D3 Bot – Telegram Test*\n"
    "✅ Connection successful!\n"
    "`1BullBear D3 × Vantage Forex`\n"
    "BUY/SELL signals, Prop Firm guard alerts, and health restarts will appear here."
)

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
resp = requests.post(url, json={
    "chat_id":    CHAT_ID,
    "text":       MESSAGE,
    "parse_mode": "Markdown",
}, timeout=10)

if resp.status_code == 200:
    print(f"[OK] Message sent successfully to chat_id={CHAT_ID}")
    print(f"     Check your Telegram now!")
else:
    print(f"[ERROR] Failed to send: {resp.status_code} {resp.text}")
    sys.exit(1)
