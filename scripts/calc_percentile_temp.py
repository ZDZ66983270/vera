
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from datetime import datetime, timedelta
from db.connection import get_connection, init_db
from data.price_cache import load_price_series

def check_val(symbol):
    init_db()
    # 10 year window
    end_date = datetime.now()
    start_date = end_date - timedelta(days=10 * 365)
    
    print(f"Checking {symbol} from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

    prices = load_price_series(symbol, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))

    if prices.empty:
        print(f"No local data for {symbol}, trying to fetch via yfinance...")
        import yfinance as yf
        # Fetch 10y+ data
        df = yf.download(symbol, start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"), progress=False)
        if df.empty:
            print("yfinance returned no data.")
            return
        
        # Format for calculation (don't save to DB to avoid pollution if unwanted, just calc)
        # df index is Datetime
        # columns might be MultiIndex if yfinance updated, check structure
        
        # Flatten MultiIndex if necessary
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        prices = df.reset_index()
        # Rename columns to match expected
        prices = prices.rename(columns={"Date": "trade_date", "Close": "close", "Volume": "volume"})
        # Columns might be Title Case from yfinance
        prices.columns = [c.lower() for c in prices.columns]
        # Ensure 'close' exists
        if 'close' not in prices.columns and 'adj close' in prices.columns:
            prices['close'] = prices['adj close']
            
        print(f"Fetched {len(prices)} rows from yfinance.")
    
    if prices.empty:
        print("Still no data.")
        return

    if 'trade_date' in prices.columns:
        prices["trade_date"] = pd.to_datetime(prices["trade_date"])
        prices.set_index("trade_date", inplace=True)
    
    # Ensure numeric
    series = pd.to_numeric(prices["close"], errors='coerce').dropna()
    
    if series.empty:
        print("Series empty after cleaning")
        return

    current_price = series.iloc[-1]
    rank = series.rank(pct=True).iloc[-1]
    
    print(f"Symbol: {symbol}")
    print(f"Current Price: {current_price}")
    print(f"Data Points: {len(series)}")
    print(f"Percentile (10y): {rank:.4f}")
    print(f"Percentile %: {rank*100:.2f}%")
    print(f"Min (10y): {series.min()}")
    print(f"Max (10y): {series.max()}")
    print(f"Last Date: {series.index[-1]}")

if __name__ == "__main__":
    check_val("601919.SS")
