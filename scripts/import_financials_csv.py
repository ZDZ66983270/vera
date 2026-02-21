
import pandas as pd
import sqlite3
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import get_connection
from utils.canonical_resolver import resolve_canonical_symbol

CSV_PATH = "imports/financials_overview.csv"

def import_csv():
    if not os.path.exists(CSV_PATH):
        print(f"File not found: {CSV_PATH}")
        return

    print(f"Reading {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    inserted = 0
    updated = 0
    skipped = 0
    errors = 0
    
    for _, row in df.iterrows():
        try:
            raw_symbol = str(row['symbol']).strip()
            # Handle date
            report_date = str(row['as_of_date']).strip()
            if not report_date or pd.isna(report_date):
                skipped += 1
                continue
                
            # Resolve ID
            asset_id = resolve_canonical_symbol(conn, raw_symbol)
            if not asset_id:
                # Try fallback or just use raw if it looks valid?
                # The resolve_canonical_symbol logic is strict.
                # If it's "00005.HK", it should resolve to "HK:STOCK:00005".
                # If it fails, maybe log it.
                print(f"Warning: Could not resolve {raw_symbol}")
                asset_id = raw_symbol # Fallback but might be risky
            
            # Metrics (Convert 亿 -> Raw by * 100,000,000)
            def parse_yi(val):
                try:
                    if pd.isna(val) or val == '': return None
                    return float(val) * 100_000_000
                except:
                    return None
            
            revenue = parse_yi(row.get('revenue (亿)'))
            net_profit = parse_yi(row.get('net_income (亿)'))
            currency = str(row.get('currency')).strip() if not pd.isna(row.get('currency')) else 'CNY'
            
            # Check existence
            cursor.execute("SELECT 1 FROM financial_history WHERE asset_id = ? AND report_date = ?", (asset_id, report_date))
            exists = cursor.fetchone()
            
            if exists:
                # Update
                cursor.execute("""
                    UPDATE financial_history
                    SET revenue_ttm = COALESCE(?, revenue_ttm),
                        net_profit_ttm = COALESCE(?, net_profit_ttm),
                        currency = ?
                    WHERE asset_id = ? AND report_date = ?
                """, (revenue, net_profit, currency, asset_id, report_date))
                updated += 1
            else:
                # Insert
                cursor.execute("""
                    INSERT INTO financial_history (asset_id, report_date, revenue_ttm, net_profit_ttm, currency)
                    VALUES (?, ?, ?, ?, ?)
                """, (asset_id, report_date, revenue, net_profit, currency))
                inserted += 1
                
        except Exception as e:
            print(f"Error processing row {row.get('symbol')}: {e}")
            errors += 1
            
    conn.commit()
    conn.close()
    print(f"Import Complete. Inserted: {inserted}, Updated: {updated}, Skipped: {skipped}, Errors: {errors}")

if __name__ == "__main__":
    import_csv()
