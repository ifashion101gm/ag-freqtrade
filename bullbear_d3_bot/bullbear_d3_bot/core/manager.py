"""
Phase 7 – Trade Management
1BullBear D3 – TP1 2R 40%, TP2 3.5R 40%, Runner 20%, BE @1R
"""
from dataclasses import dataclass

@dataclass
class ManageSignal:
    action: str  # HOLD, TP1, TP2, BE_MOVE, TRAIL, EXIT
    price: float
    r_multiple: float
    reason: str

class TradeManager:
    def __init__(self, tp1_r=2.0, tp2_r=3.5, be_at_r=1.0):
        self.tp1_r = tp1_r
        self.tp2_r = tp2_r
        self.be_at_r = be_at_r
        self.tp1_done = False
        self.tp2_done = False
        self.be_moved = False

    def update(self, direction: str, entry: float, sl: float, current: float):
        risk = abs(entry - sl)
        if risk == 0:
            return ManageSignal("HOLD", current, 0, "no risk")
        if direction == "BUY":
            r = (current - entry) / risk
            tp1_price = entry + risk * self.tp1_r
            tp2_price = entry + risk * self.tp2_r
        else:
            r = (entry - current) / risk
            tp1_price = entry - risk * self.tp1_r
            tp2_price = entry - risk * self.tp2_r

        # BE
        if r >= self.be_at_r and not self.be_moved:
            self.be_moved = True
            return ManageSignal("BE_MOVE", entry, r, f"D3 BE @ {self.be_at_r}R")
        # TP1
        if r >= self.tp1_r and not self.tp1_done:
            self.tp1_done = True
            return ManageSignal("TP1", tp1_price, r, f"D3 TP1 {self.tp1_r}R – scale 40%")
        # TP2
        if r >= self.tp2_r and not self.tp2_done:
            self.tp2_done = True
            return ManageSignal("TP2", tp2_price, r, f"D3 TP2 {self.tp2_r}R – scale 40%")
        # trail runner after TP2
        if self.tp2_done:
            return ManageSignal("TRAIL", current, r, "D3 runner trail 15m structure")

        return ManageSignal("HOLD", current, r, f"D3 hold {r:.2f}R")
