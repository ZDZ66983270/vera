import akshare as ak
from data.price_cache import save_daily_price
import pandas as pd
from datetime import datetime

def backfill():
    symbol = "512800"
    target_symbol = "CN:ETF:512800"
    
    print(f"Fetching {symbol} from AkShare...")
    try:
        # start from 2013 to ensure >10years if possible
        df = ak.fund_etf_hist_em(symbol=symbol, period="daily", start_date="20130101", end_date="20261231")
        
        if df.empty:
            print("No data fetched.")
            return

        print(f"Fetched {len(df)} rows.")
        
        count = 0
        for index, row in df.iterrows():
            trade_date = row['日期']
            
            record = {
                "symbol": target_symbol,
                "trade_date": trade_date,
                "open": float(row['开盘']),
                "high": float(row['最高']),
                "low": float(row['最低']),
                "close": float(row['收盘']),
                "volume": int(row['成交量']),
                "source": "akshare_backfill",
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
