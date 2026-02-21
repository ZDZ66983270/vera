
import pandas as pd
import sqlite3
from datetime import datetime

DB_PATH = "vera.db"
CSV_PATH = "import/marketdatadaily_2025-12-21.csv"
SYMBOL = "00005.HK"

def import_hsbc_data():
    # Read CSV
    print(f"Reading {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH)
    
    # Filter for symbol
    symbol_df = df[df['symbol'] == SYMBOL].copy()
    if symbol_df.empty:
        print(f"No data found for {SYMBOL} in CSV.")
        return
        
    # Convert timestamp to date
    symbol_df['trade_date'] = pd.to_datetime(symbol_df['timestamp']).dt.strftime('%Y-%m-%d')
    
    # Sort and get latest 30 days
    symbol_df = symbol_df.sort_values('trade_date', ascending=False).head(30)
    
    print(f"Found {len(symbol_df)} days for {SYMBOL}. Importing...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for _, row in symbol_df.iterrows():
        cursor.execute("""
            INSERT OR IGNORE INTO vera_price_cache 
            (symbol, trade_date, open, high, low, close, volume, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            SYMBOL,
            row['trade_date'],
            row['open'],
            row['high'],
            row['low'],
            row['close'],
            int(row['volume']) if not pd.isna(row['volume']) else 0,
            'CSV_IMPORT'
        ))
    
    conn.commit()
    conn.close()
    print("Import complete.")

if __name__ == "__main__":
    import_hsbc_data()
