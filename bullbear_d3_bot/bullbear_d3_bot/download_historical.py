import ccxt
import pandas as pd
import argparse
import time
from datetime import datetime, timezone, timedelta

def download_data(symbol, days, exchange_name):
    # Initialize exchange
    ex_class = getattr(ccxt, exchange_name)
    exchange = ex_class({'enableRateLimit': True})
    
    print(f"Connecting to {exchange_name}...")
    exchange.load_markets()
    
    if symbol not in exchange.markets:
        print(f"Error: Symbol {symbol} not found on {exchange_name}.")
        return

    print(f"Downloading historical 1m data for {symbol} ({days} days)...")
    
    # Calculate timestamps
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=days)
    since = int(start_time.timestamp() * 1000)
    
    all_ohlcv = []
    limit = 1000  # standard fetch limit
    
    while since < int(end_time.timestamp() * 1000):
        try:
            print(f"Fetching candles since {datetime.fromtimestamp(since/1000, tz=timezone.utc).isoformat()}...")
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1m', since=since, limit=limit)
            if not ohlcv:
                print("No more candles returned.")
                break
            
            all_ohlcv.extend(ohlcv)
            # Update 'since' to timestamp of last candle + 1 minute (60000 ms)
            last_ts = ohlcv[-1][0]
            since = last_ts + 60000
            
            time.sleep(exchange.rateLimit / 1000.0)
        except Exception as e:
            print(f"Error fetching candles: {e}")
            time.sleep(5)
            
    if not all_ohlcv:
        print("No candles downloaded.")
        return
        
    print(f"Downloaded {len(all_ohlcv)} candles.")
    
    # Convert to DataFrame
    df = pd.DataFrame(all_ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    # Convert timestamp to ISO date string format expected by backtester
    df['time'] = pd.to_datetime(df['time'], unit='ms', utc=True)
    
    # Ensure directory exists
    import os
    os.makedirs('data', exist_ok=True)
    
    # Save to CSV
    filename = f"data/{symbol.replace('/', '')}_1m.csv"
    df.to_csv(filename, index=False)
    print(f"Data saved to {filename}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="CCXT Historical Data Downloader")
    parser.add_argument('--symbol', default='BTC/USDT', help='Trading symbol (e.g. BTC/USDT)')
    parser.add_argument('--days', type=int, default=30, help='Number of days of data to download')
    parser.add_argument('--exchange', default='kraken', help='Exchange name (e.g. kraken, bybit)')
    args = parser.parse_args()
    
    download_data(args.symbol, args.days, args.exchange)
