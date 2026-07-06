"""
Phase 6 – Risk / Position Sizing
1BullBear D3 – Prop Firm 0.5-1%
"""
from dataclasses import dataclass

@dataclass
class RiskPlan:
    risk_pct: float
    risk_amount: float
    sl_price: float
    sl_pips: float
    lots: float
    valid: bool
    reason: str

class RiskManager:
    def __init__(self, balance=100000, risk_pct=1.0):
        self.balance = balance
        self.risk_pct = risk_pct

    def size(self, symbol: str, direction: str, entry: float, poi_low: float, poi_high: float, sl_buffer_pips: float, pip_value: float=10.0, point=0.01):
        # SL beyond POI swing
        if direction == "BUY":
            sl_raw = poi_low - sl_buffer_pips * point
            sl_pips = (entry - sl_raw) / point
        else:
            sl_raw = poi_high + sl_buffer_pips * point
            sl_pips = (sl_raw - entry) / point

        if sl_pips <= 0:
            return RiskPlan(self.risk_pct,0,sl_raw,sl_pips,0,False,"invalid SL")

        risk_amount = self.balance * self.risk_pct / 100.0
        # lots = risk / (sl_pips * pip_value)
        # XAU: pip_value ~1 per 0.01 per 1 lot (100 oz)
        # simplify: use pip_value passed
        lots = risk_amount / max(sl_pips * pip_value, 1e-6)
        # prop firm cap – max 5 lots per 100k example
        lots = min(lots, 5.0)
        lots = round(lots,2)

        return RiskPlan(self.risk_pct, risk_amount, sl_raw, sl_pips, lots, True,
            f"D3 Risk {self.risk_pct}% = ${risk_amount:.0f} | SL {sl_pips:.1f} pips | {lots} lots")
