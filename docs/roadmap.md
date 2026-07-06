# Development Roadmap – ag-freqtrade (1BullBear D3 × Vantage Forex)

---

## Phase 1 — Architecture Cleanup ✅ COMPLETE
- [x] Initialize Git repository + push to GitHub
- [x] Create `.gitignore`, `.env.example`, `SECURITY.md`
- [x] Set up CI pipeline (GitHub Actions: lint, Docker validate, secret scan)
- [x] Create Issue/PR templates
- [x] Set up multi-agent workflow (`/agents/`)
- [x] Document architecture (`/docs/architecture.md`)

---

## Phase 2 — Broker Connection (Vantage MT5) ✅ COMPLETE
- [x] Build `scripts/integrations/vantage_connector.py` (MT5 bridge)
- [x] Add Vantage credentials to `.env.example`
- [x] Update `configs/config.json` for Forex / Vantage (USD, XAUUSD/EURUSD/GBPUSD)
- [x] Update `docker-compose.yml`: mount D3 package, switch to `BullBearD3Strategy`
- [x] Create `configs/d3_config.yaml` (killzones MMT, risk, TP R-multiples)
- [x] Create `user_data/strategies/BullBearD3Strategy.py` (Freqtrade IStrategy)

---

## Phase 3 — Paper Trading Validation 🔜 IN PROGRESS
- [ ] Fill `.env` with real Vantage demo credentials
- [ ] Run `docker compose up -d` and test `vantage_connector.py`
- [ ] Run 5 trading sessions (London + NY killzones)
- [ ] Validate signals vs. D3 benchmark (4W/1BE/1skip)
- [ ] Review JSONL journal at `user_data/logs/d3_journal.jsonl`
- [ ] Confirm risk guard: ≤1% per trade, 2R daily loss stop
- [ ] Run backtest on 90 days Vantage XAUUSD data

---

## Phase 4 — Risk Module + Hardening ⬜ PENDING
- [ ] Wire Telegram notifications (`TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`)
- [ ] Add Prop Firm safeguards: 5% daily hard stop, 2 trades/killzone max
- [ ] Improve `backtest.py`: equity curve, PF, expectancy, killzone breakdown
- [ ] Add structured logging (JSON log format, log rotation)
- [ ] Configure `monitor/health.sh` for D3 bot health endpoint
- [ ] Set up daily backup cron via `scripts/backup.sh`
- [ ] Harden secrets: GCP Secret Manager or GitHub Actions Secrets
- [ ] HTTPS: Nginx + Let's Encrypt SSL

---

## Phase 5 — Execution Engine Improvements ⬜ PENDING
- [ ] Wire D3 `risk_plan.lots` → Freqtrade order volume (`custom_stake_amount`)
- [ ] Implement TP1 partial close (40% at 2R) via `custom_exit()`
- [ ] Implement runner management (20% trailing after TP2)
- [ ] Add MT5 position management to `vantage_connector.py`
- [ ] Validate no duplicate orders across sessions
- [ ] Add NAS100 and EURUSD to pair whitelist after XAUUSD validated

---

## Phase 6 — Improved Strategy Logic ⬜ PENDING
- [ ] Strategy Agent review: D3 phase alignment vs. video timestamps
- [ ] Improve `bias.py`: BOS confirmation + trend filter
- [ ] Improve `liquidity.py`: equal highs/lows cluster detection
- [ ] Improve `poi.py`: OB mitigation tracking, 50% CE entry
- [ ] Add session-specific strategy adjustments (Asia range, London raid)
- [ ] Backtest Phase 6 improvements, validate PF ≥ 2.5R

---

## Phase 7 — Live Trading Activation ⬜ PENDING
- [ ] Switch `BOT_DRY_RUN=false` in `.env`
- [ ] Switch `dry_run: false` in `configs/config.json`
- [ ] Start with 0.5% risk per trade
- [ ] Trade London + NY AM killzones only (MMT schedule)
- [ ] Monitor Freqtrade UI at `https://your-gcp-ip/`
- [ ] Weekly review: journal R-multiples vs. D3 benchmark (PF 2.98R)
- [ ] Scale to 1% risk after 20 consistent trades

---

## Benchmarks

| Metric | Target |
|--------|--------|
| Win rate | ≥ 55% |
| Profit Factor | ≥ 2.5R |
| Expectancy | ≥ 1.5R per trade |
| Max daily drawdown | ≤ 2R |
| Consistency score | ≥ 60% |
| Trades per week | 2–5 (quality over quantity) |

---

*Last updated: 2026-07-06 by Antigravity AI*
