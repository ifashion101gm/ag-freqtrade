"""
MT5Adapter REST API
Runs inside Wine using Python for Windows.
Wraps the official MetaTrader5 Python package.
"""
import os
import json
import logging
from flask import Flask, request, jsonify
from waitress import serve
import pandas as pd

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    print("WARNING: MetaTrader5 package not found. Must run on Windows/Wine Python.")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("MT5Adapter")

def init_mt5():
    if not MT5_AVAILABLE:
        return False
    if not mt5.initialize():
        log.error("MT5 initialize failed: %s", mt5.last_error())
        return False
    return True

@app.before_request
def check_connection():
    if not MT5_AVAILABLE:
        return jsonify({"error": "MT5 library missing"}), 500
    if mt5.terminal_info() is None:
        if not init_mt5():
            return jsonify({"error": "Failed to connect to MT5"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    info = mt5.account_info()
    if info is None:
        return jsonify({"status": "error", "message": "Not logged in"}), 500
    
    return jsonify({
        "status": "ok",
        "account": info.login,
        "server": info.server,
        "balance": info.balance,
        "currency": info.currency
    })

@app.route('/ohlcv', methods=['GET'])
def get_ohlcv():
    symbol = request.args.get('symbol')
    tf_str = request.args.get('timeframe')
    n_bars = int(request.args.get('n_bars', 500))
    
    if not symbol or not tf_str:
        return jsonify({"error": "Missing symbol or timeframe"}), 400

    TF_MAP = {
        "1m": mt5.TIMEFRAME_M1,
        "5m": mt5.TIMEFRAME_M5,
        "15m": mt5.TIMEFRAME_M15,
        "1h": mt5.TIMEFRAME_H1,
        "4h": mt5.TIMEFRAME_H4,
        "1d": mt5.TIMEFRAME_D1,
    }
    
    tf = TF_MAP.get(tf_str)
    if not tf:
        return jsonify({"error": "Invalid timeframe"}), 400
        
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, n_bars)
    if rates is None or len(rates) == 0:
        return jsonify({"error": f"Failed to get rates for {symbol}", "mt5_error": mt5.last_error()}), 500
        
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    
    # Format to list of dicts: [{time, open, high, low, close, volume}]
    result = []
    for _, row in df.iterrows():
        result.append({
            "time": row['time'].isoformat(),
            "open": float(row['open']),
            "high": float(row['high']),
            "low": float(row['low']),
            "close": float(row['close']),
            "volume": float(row['tick_volume'])
        })
        
    return jsonify(result)

@app.route('/order', methods=['POST'])
def place_order():
    data = request.json
    symbol = data.get("symbol")
    direction = data.get("direction") # "BUY" or "SELL"
    lots = data.get("lots")
    sl = data.get("sl")
    tp1 = data.get("tp1")
    
    if not all([symbol, direction, lots]):
        return jsonify({"error": "Missing parameters"}), 400
        
    order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
    price = mt5.symbol_info_tick(symbol).ask if direction == "BUY" else mt5.symbol_info_tick(symbol).bid
    
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(lots),
        "type": order_type,
        "price": price,
        "deviation": 20,
        "magic": 101010,
        "comment": "D3_Bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    if sl: req["sl"] = float(sl)
    if tp1: req["tp"] = float(tp1)
    
    res = mt5.order_send(req)
    if res.retcode != mt5.TRADE_RETCODE_DONE:
        return jsonify({"error": "Order failed", "mt5_error": res.comment, "retcode": res.retcode}), 500
        
    return jsonify({
        "status": "success",
        "order_ticket": res.order,
        "price": res.price,
        "volume": res.volume
    })

if __name__ == '__main__':
    init_mt5()
    log.info("Starting MT5Adapter API on port 5000")
    serve(app, host='0.0.0.0', port=5000)
