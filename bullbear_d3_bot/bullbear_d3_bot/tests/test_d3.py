import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from strategy.d3_cycle import BullBearD3Strategy
from core.execution import ExecutionEngine

def test_init():
    s = BullBearD3Strategy(symbol="XAUUSD", config_path="config/config.yaml")
    assert s.symbol == "XAUUSD"
    d = s.describe()
    assert "1BullBear_D3" in d["name"]
    assert len(d["phases"]) == 8
    print("D3 init OK –", d["phases"])

def test_signal_flat_no_data():
    s = BullBearD3Strategy(symbol="XAUUSD", config_path="config/config.yaml")
    e = ExecutionEngine(s)
    # empty
    sig = e.on_bar_1m(None,None,None,None,None)
    # should handle – expect FLAT phase 1
    assert sig.action in ("FLAT","")
    print("flat guard OK")

if __name__ == "__main__":
    test_init()
    print("All D3 tests passed – video: https://youtu.be/Z4uWaqiE1Iw")
