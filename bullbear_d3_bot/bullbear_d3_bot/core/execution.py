"""
ExecutionEngine – Code Agent entry
Wraps all 8 D3 phases
"""
from dataclasses import dataclass
from typing import Optional
from .bias import HTFBias
from .liquidity import LiquiditySweep
from .structure import MarketStructure
from .poi import POIFinder
from .trigger import LTFTrigger
from .risk import RiskManager
from .manager import TradeManager
from .journal import Journal
from .prop_firm_guard import PropFirmGuard
try:
    from utils.logger import get_logger as _get_logger
except ImportError:
    _get_logger = None

@dataclass
class Signal:
    action: str
    phase: int
    entry: float
    sl: float
    tp1: float
    tp2: float
    size_lots: float
    rr: float
    reason: str
    metadata: dict

class ExecutionEngine:
    def __init__(self, strategy):
        self.s = strategy
        cfg = strategy.config
        self.bias_m = HTFBias(lookback=cfg['bias']['premium_discount_lookback'])
        self.liq_m = LiquiditySweep(
            equal_tolerance_pips=cfg['liquidity']['equal_high_low_tolerance_pips'].get(strategy.symbol,5),
            min_sweep_pips=cfg['liquidity']['min_sweep_pips'].get(strategy.symbol,8),
            point=strategy.point
        )
        self.mss_m = MarketStructure(displacement_body_pct=cfg['structure']['displacement_body_pct'])
        self.poi_m = POIFinder(
            fvg_min_pips=cfg['poi']['fvg_min_pips'].get(strategy.symbol,4),
            point=strategy.point
        )
        self.trig_m = LTFTrigger(time_stop_bars=cfg['trigger']['time_stop_bars'])
        self.risk_m = RiskManager(balance=cfg['account']['balance'], risk_pct=cfg['account']['risk_pct'])
        self.mgr_m  = TradeManager(tp1_r=cfg['manage']['tp_r']['tp1'], tp2_r=cfg['manage']['tp_r']['tp2'], be_at_r=cfg['manage']['be_at_r'])
        self.journal = Journal(path=cfg['journal']['path'])
        self.guard   = PropFirmGuard(cfg)   # Prop Firm daily loss guard
        self.log     = _get_logger(f"D3Engine.{strategy.symbol}") if _get_logger else None
        self.position = None

    def on_bar_1m(self, bar_1m, bar_5m, bar_15m, bar_1h, bar_4h):
        # convert dict bars to DataFrames – strategy helper does this
        dfs = self.s.build_dfs(bar_1m, bar_5m, bar_15m, bar_1h, bar_4h)

        # if in position – manage
        if self.position:
            sig = self._manage_position(dfs['1m'].iloc[-1]['close'])
            return sig

        # Prop Firm guard check BEFORE phase evaluation
        can_trade, guard_reason = self.guard.check(self.risk_m.balance)
        if not can_trade:
            if self.log:
                self.log.prop_firm_guard("HALT", guard_reason, self.guard.status()["daily_pnl_r"])
            return Signal("FLAT",0,0,0,0,0,0,0,f"PropFirmGuard: {guard_reason}",{})

        # Phase 1
        bias = self.bias_m.evaluate(dfs['4h'], dfs['1h'])
        if not bias.valid:
            return Signal("FLAT",1,0,0,0,0,0,0,bias.reason,{})
        # Phase 2
        sweep = self.liq_m.detect(dfs['15m'])
        # D3 allows internal liquidity if strong MSS – so sweep is preferred not hard required
        # Phase 3
        mss = self.mss_m.detect_mss(dfs['15m'])
        if not mss.valid:
            return Signal("FLAT",3,0,0,0,0,0,0,mss.reason,{"bias":bias.direction})
        # check bias/MSS alignment
        if bias.direction == "BULL" and not mss.direction.startswith("BULL"):
            return Signal("FLAT",3,0,0,0,0,0,0,"MSS против HTF bias – D3 skip",{})
        if bias.direction == "BEAR" and not mss.direction.startswith("BEAR"):
            return Signal("FLAT",3,0,0,0,0,0,0,"MSS против HTF bias – D3 skip",{})

        # Phase 4
        poi = self.poi_m.find_ob_fvg(dfs['5m'], mss.direction)
        if not poi.valid:
            return Signal("FLAT",4,0,0,0,0,0,0,poi.reason,{})

        # Phase 5
        trig = self.trig_m.check(dfs['1m'], poi, mss.direction)
        if trig.time_stop:
            return Signal("EXIT",5,0,0,0,0,0,0,trig.reason,{})
        if not trig.triggered:
            return Signal("FLAT",5,0,0,0,0,0,0,trig.reason,{"poi":poi.ce})

        # Phase 6 – risk
        direction = "BUY" if trig.direction=="BUY" else "SELL"
        sl_buf = self.s.config['execution']['sl_buffer_pips'].get(self.s.symbol,1.5)
        risk_plan = self.risk_m.size(
            self.s.symbol, direction, trig.entry_price,
            poi.low, poi.high, sl_buf, pip_value=self.s.pip_value, point=self.s.point
        )
        if not risk_plan.valid:
            return Signal("FLAT",6,0,0,0,0,0,0,risk_plan.reason,{})

        # TP levels
        risk_dist = abs(trig.entry_price - risk_plan.sl_price)
        tp1 = trig.entry_price + risk_dist* self.mgr_m.tp1_r if direction=="BUY" else trig.entry_price - risk_dist* self.mgr_m.tp1_r
        tp2 = trig.entry_price + risk_dist* self.mgr_m.tp2_r if direction=="BUY" else trig.entry_price - risk_dist* self.mgr_m.tp2_r
        rr = self.mgr_m.tp1_r

        # journal pre-trade
        can, why = self.journal.can_trade(
            max_daily_loss_r=self.s.config['account']['max_daily_loss_r'],
            max_daily_trades=self.s.config['account']['max_daily_trades']
        )
        if not can:
            return Signal("FLAT",6,0,0,0,0,0,0,why,{})

        # open position state
        self.position = {
            "direction": direction,
            "entry": trig.entry_price,
            "sl": risk_plan.sl_price,
            "tp1": tp1,
            "tp2": tp2,
            "size": risk_plan.lots
        }
        # reset manager
        self.mgr_m.tp1_done=False; self.mgr_m.tp2_done=False; self.mgr_m.be_moved=False

        reason = f"D3 EXEC {direction} – {bias.reason} | {sweep.reason} | {mss.reason} | {poi.reason} | {trig.reason}"
        entry_signal = Signal(direction,6,trig.entry_price,risk_plan.sl_price,tp1,tp2,risk_plan.lots,rr,reason,{
            "bias":bias.direction, "sweep":sweep.side, "mss":mss.direction, "poi":poi.type
        })
        self.journal.log_signal({
            "phase":6, "action":direction, "entry":trig.entry_price,
            "sl":risk_plan.sl_price, "tp1":tp1, "tp2":tp2,
            "size":risk_plan.lots, "reason":reason, "symbol":self.s.symbol
        })
        # Structured log + Telegram alert
        if self.log:
            self.log.signal(
                action=direction, symbol=self.s.symbol,
                entry=trig.entry_price, sl=risk_plan.sl_price,
                tp1=tp1, tp2=tp2, size=risk_plan.lots, rr=rr,
                reason=reason, phase=6
            )
        return entry_signal

    def _manage_position(self, current_price: float):
        p = self.position
        mg = self.mgr_m.update(p["direction"], p["entry"], p["sl"], current_price)
        if mg.action in ("TP1","TP2","BE_MOVE","TRAIL","EXIT"):
            self.journal.log_signal({"phase":7, "action":mg.action, "price":mg.price, "r":mg.r_multiple, "reason":mg.reason})
            if mg.action == "TP2":
                # Close position – register R in guard + log result
                self.journal.register_fill(self.mgr_m.tp2_r)
                self.guard.register_trade_result(self.mgr_m.tp2_r)
                if self.log:
                    self.log.trade_result(
                        action=p["direction"], symbol=self.s.symbol,
                        entry=p["entry"], exit_price=mg.price,
                        pnl_r=mg.r_multiple, pnl_usd=0,   # USD calculated by risk module
                    )
                self.position = None
                return Signal("EXIT",7,mg.price,p["sl"],p["tp1"],p["tp2"],p["size"],mg.r_multiple,mg.reason,{})
            return Signal("MANAGE",7,mg.price,p["sl"],p["tp1"],p["tp2"],p["size"],mg.r_multiple,mg.reason,{})
        return Signal("HOLD",7,current_price,p["sl"],p["tp1"],p["tp2"],p["size"],mg.r_multiple,mg.reason,{})
