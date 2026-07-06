#!/usr/bin/env python3
"""
Signal Receiver Integration Placeholder.
This module listens to external signal feeds (e.g. RSS feed, WebSockets, or a Telegram group parser)
and formats them for consumption by the execution layer.
"""

import sys
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SignalReceiver:
    def __init__(self):
        logging.info("Signal Receiver integration stub loaded.")

    def parse_raw_signal(self, raw_input):
        """
        Parses raw text or JSON signals from external sources.
        Example raw input: "BUY BTC/USDT at 31000" or {"type": "ALERT", "symbol": "BTC", "dir": "LONG"}
        """
        logging.info(f"Ingesting raw signal payload: {raw_input}")
        
        # Parse simple JSON format
        try:
            data = json.loads(raw_input)
            symbol = data.get("symbol")
            direction = data.get("dir")
            
            if symbol and direction:
                pair = f"{symbol}/USDT"
                action = "buy" if direction.upper() in ["LONG", "BUY"] else "sell"
                return {"pair": pair, "action": action}
        except json.JSONDecodeError:
            # Fallback to custom string parsing logic
            parts = raw_input.split()
            if len(parts) >= 2:
                action = parts[0].lower() # e.g. "buy" or "sell"
                pair = parts[1].upper()   # e.g. "BTC/USDT"
                return {"pair": pair, "action": action}
                
        logging.error("Failed to parse signal input.")
        return None

    def process_signal(self, raw_signal):
        parsed = self.parse_raw_signal(raw_signal)
        if parsed:
            logging.info(f"Formatted Signal: {parsed['action'].upper()} {parsed['pair']}")
            # Forward signal details to webhook_receiver or execution_adapter
            return parsed
        return None

if __name__ == "__main__":
    receiver = SignalReceiver()
    # Test JSON parse
    json_sig = '{"symbol": "SOL", "dir": "LONG"}'
    receiver.process_signal(json_sig)
    # Test Text parse
    text_sig = "buy ETH/USDT"
    receiver.process_signal(text_sig)
