#!/usr/bin/env python3
"""
Webhook Receiver Integration Placeholder.
This script starts a pure Python HTTP server that listens for incoming trade signal alerts
(e.g., from TradingView or a master dashboard) and forwards them to the Freqtrade REST API.
"""

import os
import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.error

# Freqtrade API configurations (default local proxy)
FREQTRADE_API_URL = os.environ.get("FREQTRADE_API_URL", "http://localhost:8080")
API_USERNAME = os.environ.get("API_USERNAME", "admin")
API_PASSWORD = os.environ.get("API_PASSWORD", "password")

class WebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Override to log cleanly to stdout
        sys.stdout.write(f"[Webhook Server] - {format % args}\n")

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)

        try:
            payload = json.loads(post_data.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid JSON payload")
            return

        print(f"Received webhook signal: {payload}")

        # Parse signals. Expect: {"pair": "BTC/USDT", "action": "buy" or "sell"}
        pair = payload.get("pair")
        action = payload.get("action")

        if not pair or not action:
            self.send_response(422)
            self.end_headers()
            self.wfile.write(b"Missing required fields 'pair' and 'action'")
            return

        # Forward signal to Freqtrade bot (e.g. force entry/exit via API)
        success = self.forward_to_freqtrade(pair, action)

        if success:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "signal_forwarded", "pair": pair, "action": action}).encode())
        else:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(b"Failed to forward signal to Freqtrade bot")

    def forward_to_freqtrade(self, pair, action):
        """
        Interacts with Freqtrade's REST API.
        For example: POST /api/v1/forceentry or POST /api/v1/forceexit
        """
        # Map actions to Freqtrade API endpoints
        endpoint = "forcebuy" if action == "buy" else "forcesell"
        url = f"{FREQTRADE_API_URL}/api/v1/{endpoint}"
        
        # Payload for Freqtrade
        data = json.dumps({"pair": pair, "price": None}).encode('utf-8')
        
        # Setup basic auth handler
        password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        password_mgr.add_password(None, FREQTRADE_API_URL, API_USERNAME, API_PASSWORD)
        handler = urllib.request.HTTPBasicAuthHandler(password_mgr)
        opener = urllib.request.build_opener(handler)
        
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        
        try:
            response = opener.open(req, timeout=5)
            response_data = response.read().decode('utf-8')
            print(f"Freqtrade Response: {response_data}")
            return True
        except urllib.error.URLError as e:
            print(f"Error forwarding signal to Freqtrade: {e}", file=sys.stderr)
            return False

def run(port=5000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, WebhookHandler)
    print(f"Starting Webhook Receiver on port {port}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Webhook Receiver.")
        httpd.server_close()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    run(port=port)
