
import sqlite3
import pandas as pd
from datetime import datetime
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())
try:
    from db.connection import get_connection
except ImportError:
    sys.path.append(os.path.dirname(os.getcwd()))
    from db.connection import get_connection

def sync_data():
    conn = get_connection()
    cursor = conn.cursor()
    
    print("--- Starting Synchronization from Price Cache to Financial History ---")
    
    # 1. Identify rows in financial_history missing per-share metrics
    cursor.execute("""
        SELECT asset_id, report_date 
        FROM financial_history 
        WHERE eps_ttm IS NULL OR dividend_amount IS NULL OR dividend_yield IS NULL
    """)
    rows = cursor.fetchall()
    
    if not rows:
        print("No missing data found in financial_history.")
        return

    print(f"Found {len(rows)} records with missing per-share data.")
    
    updates = 0
    for asset_id, report_date in rows:
        # Find the closest entry in vera_price_cache on or before the report_date
        cursor.execute("""
            SELECT eps, dividend_yield, close
            FROM vera_price_cache 
            WHERE symbol = ? AND trade_date <= ?
            ORDER BY trade_date DESC LIMIT 1
        """, (asset_id, report_date))
        
        cache_row = cursor.fetchone()
        if cache_row:
            eps, dy, price = cache_row
            
            # If no data found at the exact date or before, skip
            if eps is None and dy is None:
                continue
            
            # Calculate dividend_amount if we have dy and price
            # yield = amount / price (approximation for the period)
            div_amt = None
            if dy and price and dy > 0:
                div_amt = (dy / 100.0) * price if dy > 1.0 else dy * price # Handle percent vs raw
            
            # Update financial_history
            cursor.execute("""
                UPDATE financial_history
                SET eps_ttm = COALESCE(eps_ttm, ?),
                    dividend_amount = COALESCE(dividend_amount, ?),
                    dividend_yield = COALESCE(dividend_yield, ?)
                WHERE asset_id = ? AND report_date = ?
            """, (eps, div_amt, dy, asset_id, report_date))
            
            updates += 1
            if updates % 10 == 0:
                print(f"Processed {updates} updates...")

    conn.commit()
    conn.close()
    print(f"✅ Finished. Total records updated: {updates}")

if __name__ == "__main__":
    sync_data()
