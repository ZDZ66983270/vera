
import pandas as pd
import sqlite3
import os
import sys

# Add project root to path
sys.path.append('/Users/zhangzy/My Docs/Privates/22-AI编程/VERA')

from db.connection import get_connection
from utils.canonical_resolver import resolve_canonical_symbol

def compare_csv_and_db(csv_path):
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().lower() for c in df.columns]
    
    conn = get_connection()
    cursor = conn.cursor()
    # Get DB records and normalize
    cursor.execute("SELECT asset_id, report_date FROM financial_history")
    db_records = set((str(r[0]).strip(), str(r[1]).strip()) for r in cursor.fetchall())
    conn.close()
    
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
    
    print(f"Total rows in CSV: {len(df)}")
    
    matched = 0
    missing = []
    
    for i, row in df.iterrows():
        raw_symbol = str(row[sym_col]).strip()
        as_of_date = str(row[date_col]).strip()
        try:
            date_str = pd.to_datetime(as_of_date).strftime('%Y-%m-%d')
            # The CSV symbols are already in canonical format like HK:STOCK:09988
            rec = (raw_symbol, date_str)
            if rec in db_records:
                matched += 1
            else:
                missing.append((i+2, rec))
        except Exception as e:
            print(f"Error processing row {i+2}: {e}")
            
    print(f"Matched records in DB: {matched}")
    print(f"Missing records: {len(missing)}")
    
    if missing:
        print("\nFirst 10 missing records:")
        for m in missing[:10]:
            print(f"  - Row {m[0]}: {m[1][0]} @ {m[1][1]}")
    else:
        print("\n✅ All CSV records successfully verified in Database!")

if __name__ == "__main__":
    compare_csv_and_db('/Users/zhangzy/My Docs/Privates/22-AI编程/VERA/imports/all_financials.csv')
