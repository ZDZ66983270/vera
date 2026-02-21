import pandas as pd
import sqlite3
import os
from db.connection import get_connection

def import_csv_to_cache(file_path):
    print(f"Reading {file_path}...")
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # Process Columns
    required_cols = ['symbol', 'timestamp', 'open', 'high', 'low', 'close', 'volume']
    for col in required_cols:
        if col not in df.columns:
            print(f"Missing required column: {col}")
            return

    # Transform
    # 1. Timestamp to Date string (YYYY-MM-DD)
    df['trade_date'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d')
    
    # 2. Add source
    df['source'] = 'import_csv'
    
    # 3. Select and Renaming check
    # We need: symbol, trade_date, open, high, low, close, volume, source
    data_to_insert = df[['symbol', 'trade_date', 'open', 'high', 'low', 'close', 'volume', 'source']].copy()
    
    # Clean data (drop rows with NaNs in PK or critical price fields if necessary, 
    # but here we assume CSV is relatively clean or let DB handle it)
    data_to_insert.dropna(subset=['symbol', 'trade_date', 'close'], inplace=True)
    
    # Insert logic
    conn = get_connection()
    cursor = conn.cursor()
    
    rows = data_to_insert.to_dict('records')
    inserted_count = 0
    
    print(f"Processing {len(rows)} rows...")
    
    # Using Transaction for speed
    try:
        cursor.execute("BEGIN TRANSACTION;")
        for row in rows:
            cursor.execute("""
                INSERT OR REPLACE INTO vera_price_cache 
                (symbol, trade_date, open, high, low, close, volume, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row['symbol'],
                row['trade_date'],
                row['open'],
                row['high'],
                row['low'],
                row['close'],
                row['volume'],
                row['source']
            ))
        conn.commit()
        inserted_count = len(rows)
        print(f"Successfully imported {inserted_count} records to vera_price_cache.")
    except Exception as e:
        conn.rollback()
        print(f"Error during database insertion: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    # Auto-detect file in import/
    import_dir = "import"
    files = [f for f in os.listdir(import_dir) if f.endswith(".csv")]
    
    if not files:
        print("No CSV files found in 'import/' directory.")
    else:
        # Pick the first one or specific logic. User mentioned "a csv file".
        target_file = os.path.join(import_dir, files[0])
        import_csv_to_cache(target_file)
