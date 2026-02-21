import pandas as pd
import sys

def check_csv(path):
    print(f"Checking {path}...")
    try:
        # Read only specific columns to speed up, or read all
        df = pd.read_csv(path)
        
        # Filter for TSLA
        tsla = df[df['symbol'] == 'TSLA']
        print(f"Total TSLA rows: {len(tsla)}")
        
        if len(tsla) == 0:
            print("No TSLA data found.")
            return

        # Check 'pe' and 'market_cap' non-null counts
        pe_count = tsla['pe'].count() # count() excludes NaNs
        ps_count = tsla['ps'].count()
        cap_count = tsla['market_cap'].count()
        rev_count = 0
        if 'revenue' in tsla.columns:
            rev_count = tsla['revenue'].count()
            
        print(f"Rows with PE: {pe_count}")
        print(f"Rows with PS: {ps_count}")
        print(f"Rows with Market Cap: {cap_count}")
        print(f"Rows with Revenue (if exists): {rev_count}")
        
        # Show sample of dates with valid data
        if pe_count > 0:
            valid_pe = tsla[tsla['pe'].notna()]
            print(f"Date range for valid PE: {valid_pe['timestamp'].min()} to {valid_pe['timestamp'].max()}")
            
    except Exception as e:
        print(f"Error reading CSV: {e}")

if __name__ == "__main__":
    check_csv("imports/market_data_daily_full.csv")
