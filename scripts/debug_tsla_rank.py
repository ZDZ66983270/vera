
from data.price_cache import load_price_series
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

symbol = "TSLA"
# Current DB is pruned to 2021-12-21.
# So "Now" is 2021-12-21.
end_date = "2021-12-21"
start_date = "2011-12-21"

print(f"Loading {symbol} from {start_date} to {end_date}...")
df = load_price_series(symbol, start_date, end_date)

if df.empty:
    print("Empty DataFrame!")
else:
    closes = df['close']
    current_price = 312.84
    
    print(f"Data Rows: {len(closes)}")
    print(f"Min Date: {df['trade_date'].min()}")
    print(f"Max Date: {df['trade_date'].max()}")
    print(f"Max Price: {closes.max()}")
    print(f"Min Price: {closes.min()}")
    
    # Calculate Percentile
    # The definition: Percentile rank of current_price within historical distribution
    # scipy.stats.percentileofscore(..., kind='rank')?
    # Or just manual: (count < curr) / total?
    
    less_count = (closes < current_price).sum()
    total = len(closes)
    percentile = less_count / total * 100
    
    print(f"Current Price: {current_price}")
    print(f"Less Count: {less_count}")
    print(f"Total: {total}")
    print(f"Calculated Percentile: {percentile:.4f}%")
