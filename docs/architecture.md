# Architecture Overview

This project follows a multi-agent development workflow targeting
the **1BullBear D3 8-Phase SMC strategy** deployed on **Vantage Markets (Forex/CFD)**
via a hardened GCP e2-micro VM running Docker.

---

## Repository Structure

```
ag-freqtrade/
├── bullbear_d3_bot/            # Standalone D3 SMC strategy engine
│   └── bullbear_d3_bot/
│       ├── strategy/
│       │   └── d3_cycle.py     # Master 8-Phase orchestrator
│       ├── core/
│       │   ├── bias.py         # Phase 1: HTF Bias 4H/1H
│       │   ├── liquidity.py    # Phase 2: BSL/SSL sweep
│       │   ├── structure.py    # Phase 3: MSS/CHoCH 15m
│       │   ├── poi.py          # Phase 4: OB/FVG/Breaker
│       │   ├── trigger.py      # Phase 5: 1m LTF trigger
│       │   ├── risk.py         # Phase 6: Prop Firm sizing
│       │   ├── execution.py    # ExecutionEngine signal assembly
│       │   ├── manager.py      # Phase 7: TP/BE manager
│       │   └── journal.py      # Phase 8: JSONL journal
│       ├── backtest.py         # Vector backtester (stub)
│       └── bot.py              # Live loop stub
├── configs/
│   ├── config.json             # Freqtrade runtime config (Forex/Vantage)
│   ├── d3_config.yaml          # D3 strategy parameters
│   └── nginx.conf              # Nginx reverse proxy config
├── user_data/
│   └── strategies/
│       ├── BullBearD3Strategy.py  # Freqtrade IStrategy wrapper (D3)
│       └── SampleStrategy.py      # Reference / fallback
├── scripts/
│   ├── integrations/
│   │   ├── vantage_connector.py   # Vantage MT5 data + order bridge
│   │   ├── execution_adapter.py   # Risk-check → order execution
│   │   ├── api_client.py          # Freqtrade REST client
│   │   ├── webhook_receiver.py    # TradingView webhook receiver
│   │   ├── event_publisher.py     # Trade event publisher
│   │   └── signal_receiver.py     # Signal parser
│   ├── setup.sh                   # GCP VM bootstrap + hardening
│   ├── backup.sh                  # Daily automated backup
│   ├── restore.sh                 # Recovery script
│   └── upgrade.sh                 # Freqtrade upgrade
├── monitor/
│   ├── health.sh               # Health check + auto-restart
│   ├── restart.sh              # Systemd restart wrapper
│   └── status.sh               # System status dashboard
├── agents/                     # Multi-agent workflow definitions
│   ├── pm.md                   # Project Manager Agent
│   ├── coder.md                # Coder Agent
│   ├── strategy.md             # Strategy Agent
│   ├── risk.md                 # Risk Agent
│   ├── backtest.md             # Backtesting Agent
│   └── execution.md            # Execution Agent
├── docs/                       # Project documentation
│   ├── architecture.md         # This file
│   └── roadmap.md              # Development roadmap
├── .github/
│   ├── workflows/ci.yml        # CI: lint + Docker validate + secret scan
│   ├── ISSUE_TEMPLATE/
│   └── PULL_REQUEST_TEMPLATE.md
├── docker-compose.yml          # Freqtrade + Nginx containers
├── .env.example                # Environment variable template
├── .gitignore                  # Comprehensive ignore rules
├── README.md                   # Deployment guide
└── SECURITY.md                 # Vulnerability disclosure policy
```

---

## Data Flow

```
Vantage MT5 Terminal
        │
        ▼
vantage_connector.py  ──── OHLCV 1m/5m/15m/1h/4h ────►  BullBearD3Strategy (IStrategy)
                                                                    │
                                                          D3 ExecutionEngine
                                                          (8 phases all GREEN)
                                                                    │
                                                              Signal: BUY/SELL
                                                                    │
                                                          Freqtrade Engine
                                                                    │
                                              ┌─────────────────────┤
                                              ▼                     ▼
                                         MT5 Order            SQLite Journal
                                              │
                                              ▼
                                      Telegram Alert
```

---

## Missing / Planned Modules

| Module | Status | Milestone |
|--------|--------|-----------|
| Vantage MT5 connector | ✅ Built | M1 |
| D3 IStrategy (Freqtrade) | ✅ Built | M2 |
| Paper trading validation | 🔜 Next | M3 |
| Telegram alerts | ⬜ Pending | M4 |
| Backtesting (vector) | ⬜ Pending | M4 |
| Logging system | ⬜ Pending | M4 |
| Deployment scripts | ✅ Exists | M4 |
| Live trading activation | ⬜ Pending | M5 |

---

## Agent Workflow

The PM Agent coordinates all development using sub-agents:

```
User / Owner
     │
     ▼
PM Agent (pm.md)
     │
     ├──► Strategy Agent    → strategy logic decisions
     ├──► Risk Agent        → risk rule validation
     ├──► Backtesting Agent → backtest design + review
     ├──► Execution Agent   → order/broker logic review
     └──► Coder Agent       → implementation
```
