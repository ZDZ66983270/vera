
from data.price_cache import load_price_series
import pandas as pd
from datetime import datetime, timedelta

# Use .SH suffix explicitly
symbol = "600309.SH"
end_date = "2023-12-13"
start_date = "2013-12-13"

print(f"Loading {symbol} from {start_date} to {end_date}...")
df = load_price_series(symbol, start_date, end_date)

if df.empty:
    print("Empty DataFrame!")
else:
    # Fix Index for slicing
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df.set_index('trade_date', inplace=True)
    
    print(f"Loaded {len(df)} rows.")
    print(f"First Date: {df.index.min()}")
    print(f"Last Date: {df.index.max()}")
    
    # Check for 2015 crash
    df_2015 = df['2015-01-01':'2015-12-31']
    if not df_2015.empty:
        print(f"2015 High: {df_2015['close'].max()}")
        print(f"2015 Low: {df_2015['close'].min()}")
    else:
        print("2015 Data MISSING in DataFrame!")
