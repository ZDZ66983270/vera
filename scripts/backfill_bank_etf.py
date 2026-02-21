import yfinance as yf
from data.price_cache import save_daily_price
import pandas as pd
import numpy as np

def backfill():
    ticker = "512800.SS"
    target_symbol = "CN:ETF:512800"
    
    print(f"Fetching {ticker} from Yahoo Finance...")
    try:
        df = yf.download(ticker, period="10y", progress=False)
        
        if df.empty:
            print("No data fetched.")
            return

        print(f"Fetched {len(df)} rows.")

        # Handle YFinance MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        count = 0
        for index, row in df.iterrows():
            trade_date = index.strftime("%Y-%m-%d")
            
            # Skip if close is NaN
            if pd.isna(row['Close']):
                continue
                
            record = {
                "symbol": target_symbol,
                "trade_date": trade_date,
                "open": float(row['Open']) if not pd.isna(row['Open']) else None,
                "high": float(row['High']) if not pd.isna(row['High']) else None,
                "low": float(row['Low']) if not pd.isna(row['Low']) else None,
                "close": float(row['Close']),
                "volume": int(row['Volume']) if not pd.isna(row['Volume']) else 0,
                "source": "yfinance_backfill",
                "source_note": "manual_fix_missing_sector_pos"
            }
            
            try:
                save_daily_price(record)
                count += 1
            except Exception as e:
                print(f"Error saving {trade_date}: {e}")
                
        print(f"Successfully backfilled {count} records for {target_symbol}")
        
    except Exception as e:
        print(f"Backfill failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    backfill()
