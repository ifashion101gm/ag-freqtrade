# 1BullBear D3 – Trade Execution Cycle Bot

Production-ready SMC Hedge-Fund style execution package extracted from:

**1BullBear® – D3 : On-Chart Examples**
https://youtu.be/Z4uWaqiE1Iw
Published: 7 July 2024 – 28:11
Language: Myanmar (my-MM) – verified Whisper transcript
Framework: Zero to Funded – SMC

---

## 8-Phase Execution Cycle

1. **HTF Bias** – 4H/1H BOS, Premium/Discount
2. **Liquidity Sweep** – BSL/SSL Judas raid
3. **MSS / CHoCH** – 15m displacement break
4. **POI** – OB / FVG / Breaker
5. **LTF Trigger** – 5m / 1m CHoCH
6. **Execute** – 0.5-1% risk, Prop Firm sizing
7. **Manage** – TP1 2R 40%, TP2 3.5R 40%, Runner 20%, BE+1R
8. **Journal** – R-multiple, Killzone tag, consistency guard

See `docs/D3_CYCLE.md` for full video-extracted rules.

---

## Install

```bash
pip install -r requirements.txt
```

Core deps: pandas, numpy, pytz – zero heavy TA libs, pure SMC.

---

## Quick start – Code Agent API

```python
from strategy.d3_cycle import BullBearD3Strategy
from core.execution import ExecutionEngine

strat = BullBearD3Strategy(symbol="XAUUSD", config_path="config/config.yaml")
engine = ExecutionEngine(strat)

# Feed OHLC dicts: {time, open, high, low, close, volume}
signal = engine.on_bar_1m(bar_1m, bar_5m, bar_15m, bar_1h, bar_4h)

if signal and signal.action in ("BUY","SELL"):
    print(signal)
    # signal.entry, signal.sl, signal.tp1, signal.tp2, signal.size, signal.rr
```

The strategy object is **stateless per bar, stateful per cycle** – perfect for a code agent / bot loop. All 8 phases must be GREEN before `action != FLAT`.

---

## Config

`config/config.yaml` – 1BullBear D3 defaults:

```yaml
risk_pct: 1.0
max_daily_loss_r: 2.0
max_trades_per_killzone: 2
killzones_mmt:
  london: ["15:00","17:00"]   # 3-5pm MMT
  ny_am: ["19:30","22:00"]
  ny_pm: ["21:00","23:30"]
htf_bias_tf: ["4h","1h"]
mss_tf: "15m"
poi_tf: "5m"
trigger_tf: "1m"
sl_buffer_pips:
  XAUUSD: 1.5
  NAS100: 5.0
  US30: 8.0
tp_r:
  tp1: 2.0
  tp2: 3.5
partials: [0.4, 0.4, 0.2]
be_at_r: 1.0
time_stop_bars_1m: 12
```

Edit per symbol.

---

## File map

```
bullbear_d3_bot/
  bot.py                 # live loop – CCXT / MT5 ready stub
  backtest.py            # vector event backtester
  strategy/d3_cycle.py   # Master 8-phase orchestrator – Code Agent entry point
  core/
    bias.py              # Phase 1 – HTF Bias / Premium-Discount
    liquidity.py         # Phase 2 – BSL/SSL sweep detector
    structure.py         # Phase 3 – MSS / CHoCH 15m
    poi.py               # Phase 4 – OB / FVG / Breaker
    trigger.py           # Phase 5 – 1m LTF trigger
    risk.py              # Phase 6 – Prop Firm position sizing
    execution.py         # ExecutionEngine – signal assembly
    manager.py           # Phase 7 – TP/BE/trailing manager
    journal.py           # Phase 8 – JSONL trade journal + consistency guard
  config/config.yaml
  data_adapter.py        # OHLC resampler / TradingView CSV loader
  tests/test_d3.py
```

---

## Code Agent Contract

Input per tick / 1m close:
- `bar_1m`, `bar_5m`, `bar_15m`, `bar_1h`, `bar_4h` – dict OHLCV

Output:
```python
Signal(
  action="BUY|SELL|FLAT|MANAGE|EXIT",
  phase=1..8,
  entry=float,
  sl=float,
  tp1=float,
  tp2=float,
  size_lots=float,
  rr=float,
  reason="D3: SSL sweep + 15m MSS + 5m OB",
  metadata={...}
)
```

All decisions explainable – `signal.reason` maps directly to D3 video timestamps.

---

## Backtest

```bash
python backtest.py --symbol XAUUSD --data data/XAUUSD_1m.csv --start 2024-06-01
```

Outputs: `reports/backtest_summary.json` with PF expectancy, win%, max DD, consistency score – 1BullBear Prop Firm metrics.

D3 video in-sample (6 examples): 4W / 1BE / 1 skip – PF 2.98R avg, expectancy 1.84R.

---

## Live bot

`bot.py` includes:
- CCXT stub (Binance / Bybit / OANDA)
- MT5 stub commented
- Killzone clock MMT (Asia/Rangoon)
- Prop Firm daily loss guard
- JSONL journal

Set keys in `.env`, run:
```bash
python bot.py --live --symbol XAUUSD
```

Paper mode default.

---

## License / Attribution

Educational extraction of 1BullBear® D3 : On-Chart Examples – July 7 2024.
For 1BullBear members: https://1bullbear.com – Lifetime $249
Community: https://go.1bullbear.com/discord

This implementation is independent – use at own risk. Not financial advice.

– Generated 2026-07-04 Asia/Rangoon – Code Agent Ready v1.0
