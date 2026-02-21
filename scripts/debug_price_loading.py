
from data.price_cache import load_price_series
import pandas as pd

def debug_loading():
    symbol = "MSFT"
    # Load 10 years history
    start_date = "2015-01-01"
    end_date = "2025-12-31"
    df = load_price_series(symbol, start_date=start_date, end_date=end_date)
    
    print(f"Loaded {len(df)} records for {symbol}")
    if df.empty:
        print("Empty DataFrame")
        return

    print("--- Tail 5 ---")
    print(df.tail(5))
    
    print("\n--- Max Price Record ---")
    max_idx = df['close'].idxmax()
    print(df.loc[max_idx])
    
    print("\n--- Current Price ---")
    current = df.iloc[-1]
    print(current)

    # Check manual percentile
    prices = df['close']
    rank = prices.rank(pct=True).iloc[-1]
    print(f"\nCalculated Rank: {rank}")
    
    peak = prices.max()
    print(f"Series Peak: {peak}")
    print(f"Current < Peak? {current['close'] < peak}")

if __name__ == "__main__":
    debug_loading()
