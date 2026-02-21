
import pandas as pd
import sqlite3
import os

DB_PATH = "vera.db"
CSV_PATH = "import/marketdatadaily_2025-12-21.csv"
SYMBOL = "00005.HK"

def import_full_hsbc():
    if not os.path.exists(CSV_PATH):
        print(f"Error: {CSV_PATH} not found.")
        return

    print(f"Reading {CSV_PATH} for full {SYMBOL} import...")
    # Read CSV
    chunks = pd.read_csv(CSV_PATH, chunksize=100000)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    total_imported = 0
    for chunk in chunks:
        # Filter for symbol
        mask = chunk['symbol'] == SYMBOL
        if mask.any():
            symbol_df = chunk[mask].copy()
            # Convert timestamp to date (assuming format 'YYYY-MM-DD HH:MM:SS')
            symbol_df['trade_date'] = pd.to_datetime(symbol_df['timestamp']).dt.strftime('%Y-%m-%d')
            
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
                    'CSV_FULL_IMPORT'
                ))
                if cursor.rowcount > 0:
                    total_imported += 1
    
    conn.commit()
    conn.close()
    print(f"Success: Imported {total_imported} new records for {SYMBOL}.")

if __name__ == "__main__":
    import_full_hsbc()
