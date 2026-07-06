#!/usr/bin/env python3
"""
1BullBear D3 – Event backtester
Feed 1m CSV – auto resample to 5m/15m/1h/4h
"""
import pandas as pd, argparse, json, os
from tqdm import tqdm
from strategy.d3_cycle import BullBearD3Strategy
from core.execution import ExecutionEngine

def resample(df, rule):
    ohlc = {'open':'first','high':'max','low':'min','close':'last','volume':'sum'}
    return df.resample(rule).apply(ohlc).dropna()

def run_backtest(csv_path, symbol):
    df1m = pd.read_csv(csv_path, parse_dates=['time'])
    df1m = df1m.set_index('time').sort_index()
    # build higher TFs
    df5m = resample(df1m, '5min')
    df15m = resample(df1m, '15min')
    df1h = resample(df1m, '1h')
    df4h = resample(df1m, '4h')

    strat = BullBearD3Strategy(symbol=symbol, config_path="config/config.yaml")
    engine = ExecutionEngine(strat)

    trades = []
    # walk 1m
    idx1m = df1m.index
    for i in tqdm(range(300, len(idx1m)), desc="D3 backtest"):
        t = idx1m[i]
        # get latest closed bar per TF <= t
        def last_bar(df, t):
            sub = df[df.index <= t]
            if sub.empty: return None
            b = sub.iloc[-1]
            return {"time": b.name.isoformat(), "open": float(b.open), "high": float(b.high), "low": float(b.low), "close": float(b.close), "volume": float(b.volume if 'volume' in b else 0)}
        b1 = last_bar(df1m, t)
        b5 = last_bar(df5m, t)
        b15 = last_bar(df15m, t)
        b1h = last_bar(df1h, t)
        b4h = last_bar(df4h, t)
        if not all([b1,b5,b15,b1h,b4h]): continue
        sig = engine.on_bar_1m(b1,b5,b15,b1h,b4h)
        if sig.action in ("BUY","SELL","EXIT"):
            trades.append({"time":t.isoformat(), "action":sig.action, "phase":sig.phase, "entry":sig.entry, "sl":sig.sl, "tp1":sig.tp1, "rr":sig.rr, "reason":sig.reason})

    os.makedirs("reports", exist_ok=True)
    with open("reports/backtest_trades.json","w") as f:
        json.dump(trades, f, indent=2)
    print(f"Trades signals: {len(trades)}")
    # naive stats
    wins = [t for t in trades if t['action']=="EXIT"]
    print(json.dumps({"total_signals": len(trades), "symbol": symbol, "source": "1BullBear D3 https://youtu.be/Z4uWaqiE1Iw"}, indent=2))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="1m OHLC CSV with columns time,open,high,low,close,volume")
    ap.add_argument("--symbol", default="XAUUSD")
    args = ap.parse_args()
    run_backtest(args.data, args.symbol)
