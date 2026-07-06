#!/usr/bin/env python3
"""
backtest.py – 1BullBear D3 Full Backtester
─────────────────────────────────────────────
Feed 1m OHLCV CSV → auto-resample to 5m/15m/1h/4h → run D3 engine → produce reports.

Usage:
  python backtest.py --data data/XAUUSD_1m.csv --symbol XAUUSD --start 2024-01-01
  python backtest.py --data data/XAUUSD_1m.csv --symbol XAUUSD --report html

Outputs:
  reports/backtest_trades.jsonl     – raw trade log
  reports/backtest_summary.json     – PF, win%, expectancy, drawdown, killzone stats
  reports/equity_curve.csv          – equity per trade (for charting)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from tqdm import tqdm

# ─── Local D3 imports ────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from strategy.d3_cycle import BullBearD3Strategy
from core.execution import ExecutionEngine

# ─── MMT Killzone Definitions (UTC offsets) ───────────────────────────────────
# MMT = UTC+6:30. We apply offset to compare against UTC timestamps.
KILLZONE_UTC = {
    "asia":    ("01:30", "04:00"),   # 08:00–10:30 MMT
    "london":  ("08:30", "10:30"),   # 15:00–17:00 MMT
    "ny_am":   ("13:00", "15:30"),   # 19:30–22:00 MMT
    "ny_pm":   ("14:30", "17:00"),   # 21:00–23:30 MMT
}


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    ohlc = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    return df.resample(rule).apply(ohlc).dropna()


def get_killzone(ts: pd.Timestamp) -> str:
    t = ts.strftime("%H:%M")
    for kz, (start, end) in KILLZONE_UTC.items():
        if start <= t <= end:
            return kz
    return "off_session"


def bar_dict(row) -> dict:
    return {
        "time":   row.name.isoformat(),
        "open":   float(row["open"]),
        "high":   float(row["high"]),
        "low":    float(row["low"]),
        "close":  float(row["close"]),
        "volume": float(row.get("volume", 0)),
    }


def last_bar(df: pd.DataFrame, t: pd.Timestamp):
    sub = df[df.index <= t]
    return bar_dict(sub.iloc[-1]) if not sub.empty else None


# ─── Core backtest loop ───────────────────────────────────────────────────────

def run_backtest(csv_path: str, symbol: str, start: str = None,
                 config_path: str = "config/config.yaml") -> dict:

    print(f"\n[D3 Backtest] Loading {csv_path} …")
    df1m = pd.read_csv(csv_path, parse_dates=["time"])
    df1m = df1m.set_index("time").sort_index()
    if not df1m.index.tz:
        df1m.index = df1m.index.tz_localize("UTC")

    if start:
        df1m = df1m[df1m.index >= pd.Timestamp(start, tz="UTC")]

    print(f"  Bars loaded: {len(df1m)} (from {df1m.index[0]} to {df1m.index[-1]})")

    # Resample
    df5m  = resample(df1m, "5min")
    df15m = resample(df1m, "15min")
    df1h  = resample(df1m, "1h")
    df4h  = resample(df1m, "4h")

    # Init D3 engine
    strat  = BullBearD3Strategy(symbol=symbol, config_path=config_path)
    engine = ExecutionEngine(strat)

    trades        = []      # completed trades (entry + exit pair)
    open_trade    = None    # currently open position
    equity        = 10000.0 # starting equity USD
    equity_curve  = [{"time": df1m.index[0].isoformat(), "equity": equity}]
    peak_equity   = equity
    max_drawdown  = 0.0

    idx = df1m.index
    WARMUP = 300  # bars needed for HTF indicators

    print(f"  Running D3 engine ({len(idx) - WARMUP} bars) …")
    for i in tqdm(range(WARMUP, len(idx)), desc="D3 Backtest"):
        t  = idx[i]
        b1 = last_bar(df1m,  t)
        b5 = last_bar(df5m,  t)
        b15= last_bar(df15m, t)
        b1h= last_bar(df1h,  t)
        b4h= last_bar(df4h,  t)
        if not all([b1, b5, b15, b1h, b4h]):
            continue

        sig = engine.on_bar_1m(b1, b5, b15, b1h, b4h)

        # ── Entry ─────────────────────────────────────────────────────────────
        if sig.action in ("BUY", "SELL") and open_trade is None:
            kz = get_killzone(t)
            open_trade = {
                "entry_time": t.isoformat(),
                "action":     sig.action,
                "entry":      sig.entry,
                "sl":         sig.sl,
                "tp1":        sig.tp1,
                "tp2":        sig.tp2,
                "size":       sig.size_lots,
                "rr_target":  sig.rr,
                "reason":     sig.reason,
                "killzone":   kz,
                "phase":      sig.phase,
            }

        # ── Exit ──────────────────────────────────────────────────────────────
        elif sig.action in ("EXIT", "MANAGE") and open_trade is not None:
            close_price = sig.entry if sig.entry > 0 else b1["close"]
            direction   = open_trade["action"]
            entry_p     = open_trade["entry"]
            sl_p        = open_trade["sl"]
            tp2_p       = open_trade["tp2"]
            risk_dist   = abs(entry_p - sl_p)

            # Determine outcome
            if direction == "BUY":
                pnl_r = (close_price - entry_p) / risk_dist if risk_dist > 0 else 0
            else:
                pnl_r = (entry_p - close_price) / risk_dist if risk_dist > 0 else 0

            won = pnl_r > 0
            risk_usd = equity * strat.config["account"]["risk_pct"] / 100
            pnl_usd  = pnl_r * risk_usd

            equity      += pnl_usd
            peak_equity  = max(peak_equity, equity)
            dd           = (peak_equity - equity) / peak_equity * 100
            max_drawdown = max(max_drawdown, dd)

            completed = {
                **open_trade,
                "exit_time":  t.isoformat(),
                "exit_price": close_price,
                "pnl_r":      round(pnl_r, 2),
                "pnl_usd":    round(pnl_usd, 2),
                "equity":     round(equity, 2),
                "won":        won,
            }
            trades.append(completed)
            equity_curve.append({"time": t.isoformat(), "equity": round(equity, 2)})
            open_trade = None

    # ── Statistics ────────────────────────────────────────────────────────────
    total   = len(trades)
    wins    = [t for t in trades if t["won"]]
    losses  = [t for t in trades if not t["won"]]
    win_r   = len(wins) / total * 100 if total > 0 else 0

    gross_profit = sum(t["pnl_r"] for t in wins)
    gross_loss   = abs(sum(t["pnl_r"] for t in losses))
    pf           = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    expectancy   = sum(t["pnl_r"] for t in trades) / total if total > 0 else 0

    avg_win  = gross_profit / len(wins)   if wins   else 0
    avg_loss = gross_loss   / len(losses) if losses else 0

    # Killzone breakdown
    kz_stats = {}
    for t in trades:
        kz = t.get("killzone", "off_session")
        if kz not in kz_stats:
            kz_stats[kz] = {"trades": 0, "wins": 0, "total_r": 0}
        kz_stats[kz]["trades"]  += 1
        kz_stats[kz]["wins"]    += 1 if t["won"] else 0
        kz_stats[kz]["total_r"] += t["pnl_r"]

    for kz in kz_stats:
        s = kz_stats[kz]
        s["win_rate"] = round(s["wins"] / s["trades"] * 100, 1) if s["trades"] else 0
        s["avg_r"]    = round(s["total_r"] / s["trades"], 2) if s["trades"] else 0
        s["total_r"]  = round(s["total_r"], 2)

    summary = {
        "symbol":         symbol,
        "period":         f"{df1m.index[0].date()} → {df1m.index[-1].date()}",
        "total_trades":   total,
        "wins":           len(wins),
        "losses":         len(losses),
        "win_rate_pct":   round(win_r, 1),
        "profit_factor":  round(pf, 2),
        "expectancy_r":   round(expectancy, 2),
        "avg_win_r":      round(avg_win, 2),
        "avg_loss_r":     round(avg_loss, 2),
        "total_pnl_r":    round(sum(t["pnl_r"] for t in trades), 2),
        "total_pnl_usd":  round(sum(t["pnl_usd"] for t in trades), 2),
        "final_equity":   round(equity, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "killzone_stats": kz_stats,
        "benchmark": {
            "target_pf":          2.98,
            "target_expectancy":  1.84,
            "source": "1BullBear D3 https://youtu.be/Z4uWaqiE1Iw",
        },
    }

    # ── Save outputs ──────────────────────────────────────────────────────────
    os.makedirs("reports", exist_ok=True)

    with open("reports/backtest_trades.jsonl", "w") as f:
        for t in trades:
            f.write(json.dumps(t) + "\n")

    with open("reports/backtest_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    equity_df = pd.DataFrame(equity_curve)
    equity_df.to_csv("reports/equity_curve.csv", index=False)

    # ── Print report ──────────────────────────────────────────────────────────
    print("\n" + "═" * 60)
    print(f"  1BullBear D3 Backtest – {symbol}")
    print("═" * 60)
    print(f"  Period:           {summary['period']}")
    print(f"  Total trades:     {total}")
    print(f"  Win rate:         {win_r:.1f}%")
    print(f"  Profit Factor:    {pf:.2f}  (target ≥ 2.98)")
    print(f"  Expectancy:       {expectancy:.2f}R  (target ≥ 1.84R)")
    print(f"  Avg Win:          {avg_win:.2f}R   Avg Loss: {avg_loss:.2f}R")
    print(f"  Total PnL:        {summary['total_pnl_r']:.2f}R  (${summary['total_pnl_usd']:.2f})")
    print(f"  Max Drawdown:     {max_drawdown:.2f}%")
    print(f"  Final Equity:     ${equity:.2f}")
    print("\n  Killzone Breakdown:")
    for kz, s in kz_stats.items():
        print(f"    {kz:<14} trades={s['trades']}  win={s['win_rate']}%  avg={s['avg_r']}R  total={s['total_r']}R")
    print("═" * 60)
    print("  Reports saved to reports/")
    print("═" * 60 + "\n")

    return summary


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="1BullBear D3 Backtester")
    ap.add_argument("--data",   required=True, help="1m OHLCV CSV: time,open,high,low,close,volume")
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--start",  default=None,  help="Start date YYYY-MM-DD")
    ap.add_argument("--config", default="config/config.yaml")
    args = ap.parse_args()

    run_backtest(args.data, args.symbol, start=args.start, config_path=args.config)
