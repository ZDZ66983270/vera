
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from data.price_cache import load_price_series
from metrics.risk_engine import RiskEngine
from db.connection import init_db

def debug_volatility(symbol):
    print(f"--- Debugging Volatility for {symbol} ---")
    
    # Simulate the date range used in snapshot_builder
    end_date = datetime.now()
    start_date = end_date - timedelta(days=10 * 365)
    
    print(f"Loading data from {start_date.date()} to {end_date.date()}")
    
    try:
        prices = load_price_series(symbol, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
    except Exception as e:
        print(f"Error loading prices: {e}")
        return

    print(f"Loaded prices shape: {prices.shape}")
    
    if prices.empty:
        print("Prices DataFrame is empty.")
        return

    # Check Columns and Types
    print("\nColumn Dtypes:")
    print(prices.dtypes)
    
    # Force Numeric (replicating the fix I applied)
    prices["trade_date"] = pd.to_datetime(prices["trade_date"])
    prices.set_index("trade_date", inplace=True)
    
    for col in ["open", "high", "low", "close", "volume"]:
        if col in prices.columns:
            prices[col] = pd.to_numeric(prices[col], errors='coerce')
            
    prices.dropna(subset=["close"], inplace=True)
    
    print(f"\nAfter Numeric Conversion & DropNA, shape: {prices.shape}")
    print(f"First 5 rows of close:\n{prices['close'].head()}")
    print(f"Last 5 rows of close:\n{prices['close'].tail()}")
    
    # Calculate Metrics
    try:
        metrics = RiskEngine.calculate_risk_metrics(prices['close'])
        print("\nCalculated Metrics:")
        print(f"Annual Volatility: {metrics.get('annual_volatility')}")
        print(f"Volatility Period: {metrics.get('volatility_period')}")
        
        # Manually check returns
        returns = prices['close'].pct_change().dropna()
        print(f"\nManual Returns Check:")
        print(f"Returns count: {len(returns)}")
        print(f"Returns std: {np.std(returns)}")
        print(f"Returns head: {returns.head()}")
        
    except Exception as e:
        print(f"Error in RiskEngine: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    init_db()
    debug_volatility("TSLA")
