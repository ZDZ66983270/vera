
import pandas as pd
import sqlite3
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.connection import get_connection

CSV_PATH = "imports/market_data_daily_with_eps.csv"

def import_market_data_with_eps():
    """
    Import daily market data with EPS from CSV.
    Updates vera_price_cache with price data and creates/updates fundamentals_facts with EPS.
    """
    if not os.path.exists(CSV_PATH):
        print(f"File not found: {CSV_PATH}")
        return

    print(f"Reading {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    price_inserted = 0
    price_updated = 0
    eps_inserted = 0
    eps_updated = 0
    skipped = 0
    errors = 0
    
    for _, row in df.iterrows():
        try:
            symbol = str(row['symbol']).strip()
            timestamp = str(row['timestamp']).strip()
            
            if not timestamp or pd.isna(timestamp):
                skipped += 1
                continue
            
            # Parse date from timestamp
            try:
                trade_date = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
            except:
                trade_date = timestamp.split()[0]  # Take date part
            
            # Extract price data
            open_price = row.get('open')
            high = row.get('high')
            low = row.get('low')
            close = row.get('close')
            volume = row.get('volume')
            
            # Clean values
            def clean_value(val):
                return None if pd.isna(val) else float(val)
            
            open_price = clean_value(open_price)
            high = clean_value(high)
            low = clean_value(low)
            close = clean_value(close)
            volume = clean_value(volume)
            
            # Update price cache
            if close is not None:
                cursor.execute("""
                    SELECT 1 FROM vera_price_cache 
                    WHERE symbol = ? AND trade_date = ?
                """, (symbol, trade_date))
                
                if cursor.fetchone():
                    cursor.execute("""
                        UPDATE vera_price_cache
                        SET open = ?, high = ?, low = ?, close = ?, volume = ?
                        WHERE symbol = ? AND trade_date = ?
                    """, (open_price, high, low, close, volume, symbol, trade_date))
                    price_updated += 1
                else:
                    cursor.execute("""
                        INSERT INTO vera_price_cache (symbol, trade_date, open, high, low, close, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (symbol, trade_date, open_price, high, low, close, volume))
                    price_inserted += 1
            
            # Extract and update EPS data
            eps = clean_value(row.get('eps'))
            
            if eps is not None:
                # Use trade_date as as_of_date for EPS
                cursor.execute("""
                    SELECT 1 FROM fundamentals_facts 
                    WHERE asset_id = ? AND as_of_date = ?
                """, (symbol, trade_date))
                
                if cursor.fetchone():
                    cursor.execute("""
                        UPDATE fundamentals_facts
                        SET eps_ttm = ?
                        WHERE asset_id = ? AND as_of_date = ?
                    """, (eps, symbol, trade_date))
                    eps_updated += 1
                else:
                    cursor.execute("""
                        INSERT INTO fundamentals_facts (asset_id, as_of_date, eps_ttm)
                        VALUES (?, ?, ?)
                    """, (symbol, trade_date, eps))
                    eps_inserted += 1
                
        except Exception as e:
            print(f"Error processing row {row.get('symbol')}: {e}")
            errors += 1
    
    conn.commit()
    conn.close()
    
    print(f"\nImport Complete:")
    print(f"  Price Cache - Inserted: {price_inserted}, Updated: {price_updated}")
    print(f"  EPS Data - Inserted: {eps_inserted}, Updated: {eps_updated}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors: {errors}")

if __name__ == "__main__":
    import_market_data_with_eps()
