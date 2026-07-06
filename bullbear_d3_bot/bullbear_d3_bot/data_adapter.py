"""
Data adapter – TradingView CSV / CCXT OHLCV → D3 bars
"""
import pandas as pd

def tv_csv_to_d3(csv_path: str) -> pd.DataFrame:
    """
    TradingView export: time,open,high,low,close,volume
    Returns 1m DataFrame indexed UTC
    """
    df = pd.read_csv(csv_path)
    # normalize columns lower
    df.columns = [c.lower() for c in df.columns]
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'], utc=True)
        df = df.set_index('time')
    return df[['open','high','low','close','volume']] if 'volume' in df.columns else df[['open','high','low','close']]

def ccxt_ohlcv_to_bar(ohlcv):
    """
    CCXT ohlcv: [timestamp, open, high, low, close, volume]
    → D3 bar dict
    """
    ts, o, h, l, c, v = ohlcv
    from datetime import datetime, timezone
    return {
        "time": datetime.fromtimestamp(ts/1000, tz=timezone.utc).isoformat(),
        "open": float(o), "high": float(h), "low": float(l), "close": float(c), "volume": float(v)
    }
