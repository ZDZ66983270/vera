
import pandas as pd
import sqlite3
import os
import sys

# Add project root to path
sys.path.append('/Users/zhangzy/My Docs/Privates/22-AI编程/VERA')

from db.connection import get_connection
from utils.canonical_resolver import resolve_canonical_symbol

def debug_import(csv_path):
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().lower() for c in df.columns]
    
    conn = get_connection()
    conn.isolation_level = None
    cursor = conn.cursor()
    cursor.execute("BEGIN")
    
    # Get actual columns like the real code
    cursor.execute("PRAGMA table_info(financial_history)")
    fh_actual_cols = [r[1] for r in cursor.fetchall()]
    
    mapping = {
        'symbol': ['symbol', 'ticker', 'code', '代码', '标的'],
        'date': ['as_of_date', 'date', 'report_date', '日期', '截止日期']
    }
    
    def find_col(keys):
        for c in df.columns:
            if any(k in c for k in keys): return c
        return None
        
    sym_col = find_col(mapping['symbol'])
    date_col = find_col(mapping['date'])
    
    errors = {}
    success_count = 0
    row_errors = []
    
    for i, row in df.iterrows():
        try:
            raw_symbol = str(row[sym_col]).strip()
            as_of_date = str(row[date_col]).strip()
            
            report_date_obj = pd.to_datetime(as_of_date)
            as_of_date_str = report_date_obj.strftime('%Y-%m-%d')
            
            asset_id = resolve_canonical_symbol(conn, raw_symbol)
            if not asset_id: asset_id = raw_symbol
            
            # Simulate fh_raw (simplified but with same fields)
            # This is where we might find why some rows have NO data (skipped)
            # vs some rows having BAD data (error)
            
            # Using a simplified version of the real sql construction
            # We don't need real values, just check if ANY data is found
            has_any_data = True # Simulate that most rows have data
            
            if has_any_data:
                # Let's try to actually EXECUTE a test insert
                sql = f"INSERT INTO financial_history (asset_id, report_date) VALUES (?, ?)"
                # Use a specific asset_id to avoid contamination even if rolled back
                # But wait, FK constraint might hit if asset_id is not in assets!
                # Ah! In the real app, PRAGMA foreign_keys is 0?
                # Let's check it in THIS connection.
                cursor.execute(sql, (asset_id, as_of_date_str))
                
                success_count += 1
            
        except sqlite3.IntegrityError as e:
            err_msg = f"IntegrityError: {str(e)}"
            errors[err_msg] = errors.get(err_msg, 0) + 1
            row_errors.append((i+2, raw_symbol, as_of_date, err_msg))
        except Exception as e:
            err_msg = str(e)
            errors[err_msg] = errors.get(err_msg, 0) + 1
            row_errors.append((i+2, raw_symbol, as_of_date, err_msg))
            
    cursor.execute("ROLLBACK")
    conn.close()
    
    print(f"Total Rows in CSV: {len(df)}")
    print(f"Simulation - Success: {success_count}, Errors: {len(row_errors)}")
    print("\nError Summary:")
    for msg, count in errors.items():
        print(f"  - {msg}: {count} occurrences")
    
    if row_errors:
        print("\nFirst 10 failed rows:")
        for r in row_errors[:10]:
            print(f"  Row {r[0]} ({r[1]}, {r[2]}): {r[3]}")

if __name__ == "__main__":
    debug_import('/Users/zhangzy/My Docs/Privates/22-AI编程/VERA/imports/all_financials.csv')
